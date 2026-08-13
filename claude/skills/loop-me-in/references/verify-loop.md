# Verify-loop recipes

Command recipes for the self-verifying brief. **Copy the resolved commands into the
brief itself** — a fresh session will not read this file, and a brief that links to it
fails the stand-alone test.

Placeholders: `$RUN_DIR` (scratch for this run), `$WORKTREE`, `$APP_URL`, `$PORT`,
`$CD` = `~/.claude/skills/chrome-devtools/references/chrome-devtools`.

## 0. `with_timeout` — macOS has no `timeout`

Neither `timeout` nor `gtimeout` is on this machine (no GNU coreutils). A brief that
writes `timeout 900 codex exec …` dies on `command not found` at the first phase. Define
this once, near the top of the brief, and use it for every long-running command:

```sh
with_timeout() {  # with_timeout <seconds> <command...>
  perl -e 'alarm shift; exec @ARGV' "$@"
}
```

`/usr/bin/perl` ships with macOS, and a pending `alarm` survives `exec`, so the command
itself takes the SIGALRM. Timed-out runs exit 142.

SIGALRM reaches only the process that was launched — a timed-out `codex exec` can leave
children behind, so run the heartbeat (section 8) after any 142.

## 1. Pick the harness

| Target | Harness | Why |
|---|---|---|
| Any web UI served from the worktree | `chrome-devtools` CDP script driven by a codex agent | Headless-capable, scriptable, no interactive consent, works on any localhost surface |
| OM Chat GUI | `~/.claude/skills/om-chat-web/scripts/om-chat.mjs` | Already carries `doctor` (is the daemon serving the working tree?), saved logins, and a cloud-vs-local pixel-diff report |
| Backend, CLI, library | A command with an expected value — no browser | A browser check that proves nothing is worse than admitting the check is a command |

Do **not** use `claude-in-chrome` for unattended runs: it needs per-site permission
grants and drives Ryan's real Chrome profile, so the run stalls waiting for consent.

## 2. The surface: reuse first, then start

One dev server and one browser for the entire run. Both are started at most once, before
phase 1 — never per phase, never per sweep.

```sh
mkdir -p "$RUN_DIR"
PORT=5173

ensure_dev_server() {
  local holder cwd
  holder=$(lsof -ti tcp:$PORT -sTCP:LISTEN | head -1)
  if [ -n "$holder" ]; then
    cwd=$(lsof -a -p "$holder" -d cwd -Fn | sed -n 's/^n//p')
    if [ "$cwd" = "$WORKTREE" ]; then
      echo "$holder" > "$RUN_DIR/dev.pid.reused"   # reuse; do NOT kill, do NOT relaunch
      return 0
    fi
    echo "STOP: :$PORT held by a foreign process ($holder, cwd $cwd)"
    return 1                                        # never kill someone else's server
  fi
  ( cd "$WORKTREE" && npm run dev -- --port "$PORT" --strictPort ) \
    >"$RUN_DIR/dev.log" 2>&1 &
  echo $! > "$RUN_DIR/dev.pid"
}
```

`--strictPort` (or the equivalent) matters: without it the dev server silently moves to
the next free port and the sweep verifies whatever was already on `$PORT`.

A server the run reused is **not** in the teardown list — killing it takes down whatever
started it. `dev.pid` gets torn down; `dev.pid.reused` does not.

## 3. Chrome: reuse first, smoke-test, then trust it

```sh
CDP_PORT=9222
PROFILE="$RUN_DIR/chrome-profile"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

chrome_is_ours() {   # a live CDP endpoint owned by this run's profile
  local holder
  holder=$(lsof -ti tcp:$CDP_PORT -sTCP:LISTEN | head -1) || return 1
  [ -n "$holder" ] || return 1
  ps -p "$holder" -o command= | grep -qF -- "--user-data-dir=$PROFILE"
}

chrome_works() {     # functional, not merely listening
  curl -sf -o /dev/null "http://127.0.0.1:$CDP_PORT/json/version" || return 1
  $CD navigate --wait-until load "about:blank" >/dev/null 2>&1 || return 1
  [ "$($CD evaluate '1+1' 2>/dev/null | tr -dc 0-9)" = "2" ] || return 1
  $CD screenshot --output "$RUN_DIR/smoke.png" >/dev/null 2>&1 || return 1
  [ -s "$RUN_DIR/smoke.png" ]
}

start_chrome() {
  "$CHROME" --remote-debugging-port=$CDP_PORT --user-data-dir="$PROFILE" \
    --headless=new --no-first-run --no-default-browser-check \
    --disable-extensions --disable-background-networking \
    about:blank >"$RUN_DIR/chrome.log" 2>&1 &
  echo $! > "$RUN_DIR/chrome.pid"
  for _ in $(seq 30); do curl -sf -o /dev/null \
    "http://127.0.0.1:$CDP_PORT/json/version" && return 0; sleep 0.5; done
  return 1
}

ensure_chrome() {                       # at most TWO launch attempts for the whole run
  chrome_is_ours && chrome_works && return 0
  if lsof -ti tcp:$CDP_PORT -sTCP:LISTEN >/dev/null 2>&1 && ! chrome_is_ours; then
    CDP_PORT=$((CDP_PORT+1)); export CHROME_DEVTOOLS_URL="http://127.0.0.1:$CDP_PORT"
  fi                                    # foreign Chrome on the port: step aside, never kill
  kill "$(cat "$RUN_DIR/chrome.pid" 2>/dev/null)" 2>/dev/null   # ours but broken: reap it
  start_chrome && chrome_works && return 0
  kill "$(cat "$RUN_DIR/chrome.pid" 2>/dev/null)" 2>/dev/null
  start_chrome && chrome_works && return 0
  echo "STOP: browser will not come up healthy after 2 attempts"; return 1
}
```

Points that matter:

- **A port that answers is not a working browser.** `/json/version` responds from a
  Chrome whose renderer has died. The smoke test navigates, evaluates, and writes a real
  screenshot file — those are the three things every sweep depends on.
- **Two launch attempts, then stop.** A relaunch loop is how a run ends the night with
  forty headless Chromes and no verification. The third failure is a stop condition.
- **Never kill a foreign Chrome on the port** — it may be Ryan's. Step to the next port
  and set `CHROME_DEVTOOLS_URL`, which the `chrome-devtools` script honours.
- Dedicated `--user-data-dir` is not optional: it keeps the run out of Ryan's logged-in
  profile, makes reuse detectable, and makes teardown precise. Drop `--headless=new` only
  when the app renders differently headless.
- **Reuse one tab.** Pass `--new-tab` once, at the start; navigate that same tab for every
  later check. A `--new-tab` per acceptance row leaves dozens of live tabs, each with its
  own renderer process.

## 4. Build-identity gate — run before every sweep

Two parts. Both must pass or the sweep result is void: rebuild, restart, re-gate. A
failed gate is never recorded as "not landed" — it is recorded as "not verified".

```sh
# (a) the process serving $PORT is rooted in this worktree
PID=$(lsof -ti tcp:$PORT -sTCP:LISTEN | head -1)
lsof -a -p "$PID" -d cwd -Fn | sed -n 's/^n//p'      # must equal $WORKTREE

# (b) the phase's sentinel reaches the served output — same tab, every time
$CD navigate --wait-until load "$APP_URL"
$CD evaluate 'document.querySelector("[data-testid=\"<sentinel>\"]") !== null'
```

The sentinel is a string that exists **only** after this phase's change — a new
`data-testid`, a new route, a new label. Name one per phase while writing the brief. If a
phase has no observable sentinel, it has no browser verification; say so and give it a
command gate instead.

## 5. Sweep agent

```sh
with_timeout 900 codex exec \
  -C "$WORKTREE" \
  -m gpt-5.6-sol \
  -c model_reasoning_effort="high" \
  -c sandbox_workspace_write.network_access=true \
  --sandbox workspace-write \
  --add-dir "$RUN_DIR" \
  --output-last-message "$RUN_DIR/sweep-p$N.md" \
  "$(cat "$RUN_DIR/sweep-prompt-p$N.md")"
```

`sandbox_workspace_write.network_access=true` is required — `workspace-write` blocks
network by default and CDP on `127.0.0.1:9222` counts as network. Without it the sweep
reports a connection error that reads like a broken app.

`with_timeout` is required. A codex run that hangs at 3am costs the whole night.

The sweep prompt carries: the app URL, the `$CD` path and its `--help` hint, the phase's
acceptance rows, the sentinel, the scope fence, and this output contract:

```
PHASE: <n>
IDENTITY: pass | fail — <cwd observed> / <sentinel found?>
ACCEPTANCE:
  - <row>: landed | not-landed — <selector or text observed> — <screenshot path>
REGRESSIONS: <console errors, 4xx/5xx, broken route> | none
GAPS: <in-scope defect> — <file:line best guess>
OUT-OF-SCOPE: <seen, left alone> | none
BLOCKED: <the single question that needs a human> | none
```

Screenshots go to `$RUN_DIR`: `$CD screenshot --full-page --output "$RUN_DIR/p$N-<row>.png"`.
Console and network for the same window: `$CD logs --duration-ms 2000 --include-network`.

## 6. Fix agent

```sh
with_timeout 1800 codex exec \
  -C "$WORKTREE" \
  -m gpt-5.6-sol \
  -c model_reasoning_effort="high" \
  --sandbox workspace-write \
  --output-last-message "$RUN_DIR/fix-p$N-a$ATTEMPT.md" \
  "$(cat "$RUN_DIR/fix-prompt-p$N-a$ATTEMPT.md")"
```

The fix prompt carries the sweep's `GAPS` verbatim, the scope fence, and the verification
command. Codex does not commit and does not stage — the run reviews the diff, then
`git add` plus the `/commit` skill.

## 7. Loop control

```
build → identity gate → sweep → all rows landed and no in-scope regressions? → commit, next phase
                                 ↓ no
                              fix agent → attempt += 1 → back to build
```

Cap at **3 sweeps per phase**. On the third failure, stop that phase, record what is still
red, and move to the next phase that does not depend on it. Two failures of the same class
means the model of the problem is wrong, not that a fourth patch is needed.

## 8. Heartbeat — between every phase

```sh
curl -sf -o /dev/null "$APP_URL"                                 || echo "STUCK: dev server down"
chrome_works                                                     || echo "STUCK: browser unhealthy"
pgrep -f "codex exec" | wc -l                                    # expect 0 between phases
jobs -l                                                          # expect no stopped jobs

# memory: this run's browser tree, and the machine
ps -Ao rss=,command= | grep -F -- "--user-data-dir=$PROFILE" \
  | awk '{s+=$1} END {printf "run chrome tree: %d MB\n", s/1024}'
memory_pressure | awk -F': ' '/free percentage/{print "system free: " $2}'

# process count of this run's browser tree — a jump between phases means tabs are leaking
pgrep -fc -- "--user-data-dir=$RUN_DIR"
```

Rules the numbers drive:

- **Unhealthy browser:** `ensure_chrome` reaps and relaunches once. It does not stack a
  second instance beside the first.
- **Run's Chrome tree over ~1.5 GB, or system free under 15%:** recycle the browser
  between phases — kill by ledger PID, `ensure_chrome` again. Restart is cheap and the
  identity gate re-runs anyway; a long-lived headless Chrome after twenty sweeps is not.
- **One codex agent at a time.** Sweep or fix, never both, never two phases in parallel.
  Two `codex exec` runs plus a browser tree is where an unattended night turns into swap.
- Anything stuck is killed and restarted, not waited on.

## 9. Teardown — runs on success, failure, and abort

```sh
for f in "$RUN_DIR"/*.pid; do kill "$(cat "$f")" 2>/dev/null; done   # *.pid.reused excluded
pkill -f -- "--user-data-dir=$PROFILE" 2>/dev/null                   # this run's chrome tree only
pgrep -fl -- "--user-data-dir=$RUN_DIR|codex exec"                   # confirm empty
```

Kill by recorded PID first. The one pattern kill that is safe is `--user-data-dir=$PROFILE`,
because that path exists only for this run — it reaps the renderer children the parent PID
leaves behind. The `pgrep` is a confirmation sweep, not the mechanism.

Anything the run **reused** rather than started (`*.pid.reused`) is left alone. It belonged
to someone else before the run began and still does.

**Never run a bare `pkill -f chrome` or `pkill -f node`** — that kills Ryan's own browser
and unrelated work. The dedicated profile, the claimed port, and the PID ledger exist so
teardown can be precise.
