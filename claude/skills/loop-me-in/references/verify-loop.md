# Verify-loop recipes

Command recipes for the self-verifying brief. **Copy the resolved commands into the
brief itself** — a fresh session will not read this file, and a brief that links to it
fails the stand-alone test.

Which harness to pick, and why the loop is shaped this way, is in `../SKILL.md`. This
file is the operational half.

Placeholders: `$WORKTREE`, `$APP_URL`, `$PORT`,
`$CD` = `~/.claude/skills/chrome-devtools/references/chrome-devtools`, and:

```sh
RUN_DIR=~/.claude/plans/<YYYY-MM-DD>/<name>-run-evidence   # NOT /tmp
FINDINGS="$RUN_DIR/findings.md"
```

`$RUN_DIR` sits beside the brief in the plans vault, not in a temp directory a reboot
clears. Sweep verdicts, screenshots, and console logs are the only proof the night's work
happened; a run that leaves them in `/tmp` has verified nothing you can still read.
**Teardown kills processes. It never deletes `$RUN_DIR`.**

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

## 1. The dev server: reuse first, then start

One dev server and one browser for the entire run, started at most once, before phase 1 —
never per phase, never per sweep.

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

`dev.pid` gets torn down; `dev.pid.reused` does not. Killing a server the run reused takes
down whatever started it.

## 2. Chrome: reuse first, smoke-test, then trust it

```sh
CDP_PORT=9222
PROFILE="$RUN_DIR/chrome-profile"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
export CHROME_DEVTOOLS_STATE_DIR="$RUN_DIR/cd-state"   # per-run selected tab

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
  for _ in $(seq 30); do
    curl -sf -o /dev/null "http://127.0.0.1:$CDP_PORT/json/version" && break
    sleep 0.5
  done
  $CD navigate --new-tab --wait-until load "about:blank" >/dev/null 2>&1  # the run's one tab
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

- **`/json/version` answers from a Chrome whose renderer has died.** The smoke test
  navigates, evaluates, and writes a real screenshot file — the three things every sweep
  depends on. Passing it is what "the browser is up" means.
- **Two launch attempts, then stop.** The third failure is a stop condition, not a retry.
- **Never kill a foreign Chrome on the port** — it may be Ryan's. Step to the next port and
  set `CHROME_DEVTOOLS_URL`, which the `chrome-devtools` script honours.
- **`CHROME_DEVTOOLS_STATE_DIR` scoped to the run** keeps the selected tab out of the
  shared user state dir, so two runs don't drive each other's tabs.
- **One tab.** `start_chrome` opens it with `--new-tab`; everything afterwards navigates
  that same tab. A `--new-tab` per acceptance row leaves dozens of live renderers.
- Dedicated `--user-data-dir` is not optional: it keeps the run out of Ryan's logged-in
  profile, makes reuse detectable, and makes teardown precise. Drop `--headless=new` only
  when the app renders differently headless.

## 3. Build-identity gate — run before every sweep

Both parts must pass or the sweep result is void: rebuild, restart, re-gate. A failed gate
is recorded as "not verified", never as "not landed".

```sh
# (a) the process serving $PORT is rooted in this worktree
PID=$(lsof -ti tcp:$PORT -sTCP:LISTEN | head -1)
lsof -a -p "$PID" -d cwd -Fn | sed -n 's/^n//p'      # must equal $WORKTREE

# (b) the phase's sentinel reaches the served output — same tab, every time
$CD navigate --wait-until load "$APP_URL"
$CD evaluate 'document.querySelector("[data-testid=\"<sentinel>\"]") !== null'
```

The sentinel is a string that exists **only** after this phase's change — a new
`data-testid`, a new route, a new label. Name one per phase while writing the brief. A
phase with no observable sentinel has no browser verification: say so, and give it a
command gate instead.

## 4. Sweep agent

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
network by default and CDP on `127.0.0.1:$CDP_PORT` counts as network. Without it the
sweep reports a connection error that reads like a broken app.

Codex cannot invoke `/caveman:caveman`, so every codex prompt opens with the rules inline:

```
Style: terse. Drop articles, filler, hedging. Fragments fine. No preamble, no
narration, no restating the task, no summary paragraph. Reproduce EXACTLY, never
paraphrased or shortened: error strings, selectors, file paths, numbers, units,
code. Output the contract block and nothing else.
```

The contract block below is the whole response. A sweep that also writes three
paragraphs explaining what it did costs more than the sweep.

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

Evidence the sweep prompt must write, not just describe:

```sh
$CD screenshot --full-page --output "$RUN_DIR/p$N-<row>.png"
$CD logs --duration-ms 2000 --include-network > "$RUN_DIR/p$N-console.log" 2>&1
```

A console error paraphrased into the verdict cannot be debugged three days later. The raw
capture is cheap; write it every sweep, pass or fail.

## 5. Findings log — append after every sweep

The per-sweep files answer "what happened in phase 3". The findings log answers "what did
last night find", which is the question actually asked the next morning.

```sh
{
  echo "## P$N attempt $ATTEMPT — <phase name>"
  echo "identity: $(sed -n 's/^IDENTITY: //p' "$RUN_DIR/sweep-p$N.md")"
  sed -n '/^ACCEPTANCE:/,/^REGRESSIONS:/p' "$RUN_DIR/sweep-p$N.md"
  sed -n '/^REGRESSIONS:/,$p'              "$RUN_DIR/sweep-p$N.md"
  echo "evidence: $RUN_DIR/p$N-*.png, $RUN_DIR/p$N-console.log"
  echo
} >> "$FINDINGS"
```

Every sweep appends — including the ones that passed, and including void sweeps, whose
entry reads `identity: fail` and explains why nothing was verified. A findings log that
only records failures cannot show that phase 2 was green before phase 5 broke it.

**`OUT-OF-SCOPE` entries are the reason this file exists.** They are the bugs the run
found and was told not to fix; the completion post has 40–100 words and will not carry
them. The log is where they wait for Ryan.

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
red, and move to the next phase that does not depend on it.

One codex agent at a time — sweep or fix, never both, never two phases in parallel. Two
`codex exec` runs plus a browser tree is where an unattended night turns into swap.

## 8. Heartbeat — between every phase

```sh
curl -sf -o /dev/null "$APP_URL"    || echo "STUCK: dev server down"
chrome_works                        || echo "STUCK: browser unhealthy"
pgrep -f "codex exec" | wc -l       # expect 0 between phases
jobs -l                             # expect no stopped jobs

# memory: this run's browser tree, then the machine
ps -Ao rss=,command= | grep -F -- "--user-data-dir=$PROFILE" \
  | awk '{s+=$1} END {printf "run chrome tree: %d MB\n", s/1024}'
memory_pressure | awk -F': ' '/free percentage/{print "system free: " $2}'

# process count of this run's browser tree — a jump between phases means tabs are leaking
pgrep -fc -- "--user-data-dir=$RUN_DIR"
```

- **Unhealthy browser:** `ensure_chrome` reaps and relaunches. It never stacks a second
  instance beside the first.
- **Tree over ~1.5 GB, or system free under 15%:** recycle between phases — kill by ledger
  PID, `ensure_chrome` again. Restart is cheap and the identity gate re-runs anyway; a
  headless Chrome twenty sweeps deep is not.
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
to something else before the run began and still does.

**Never run a bare `pkill -f chrome` or `pkill -f node`** — that kills Ryan's own browser
and unrelated work. The dedicated profile, the claimed port, and the PID ledger exist so
teardown can be precise.
