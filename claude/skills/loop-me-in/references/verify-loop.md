# Verify-loop recipes

Command recipes for the self-verifying brief. **Copy the resolved commands into the
brief itself** — a fresh session will not read this file, and a brief that links to it
fails the stand-alone test.

Placeholders: `$RUN_DIR` (scratch for this run), `$WORKTREE`, `$APP_URL`, `$PORT`,
`$CD` = `~/.claude/skills/chrome-devtools/references/chrome-devtools`.

## 1. Pick the harness

| Target | Harness | Why |
|---|---|---|
| Any web UI served from the worktree | `chrome-devtools` CDP script driven by a codex agent | Headless-capable, scriptable, no interactive consent, works on any localhost surface |
| OM Chat GUI | `~/.claude/skills/om-chat-web/scripts/om-chat.mjs` | Already carries `doctor` (is the daemon serving the working tree?), saved logins, and a cloud-vs-local pixel-diff report |
| Backend, CLI, library | A command with an expected value — no browser | A browser check that proves nothing is worse than admitting the check is a command |

Do **not** use `claude-in-chrome` for unattended runs: it needs per-site permission
grants and drives Ryan's real Chrome profile, so the run stalls waiting for consent.

## 2. Start the surface, claim the port, record the PID

```sh
mkdir -p "$RUN_DIR"
PORT=5173
( cd "$WORKTREE" && npm run dev -- --port "$PORT" --strictPort ) \
  >"$RUN_DIR/dev.log" 2>&1 &
echo $! > "$RUN_DIR/dev.pid"
```

`--strictPort` (or the equivalent) matters: without it the dev server silently moves to
the next free port and the sweep verifies whatever was already on `$PORT`.

## 3. Start a dedicated Chrome

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$RUN_DIR/chrome-profile" \
  --headless=new --no-first-run --no-default-browser-check \
  about:blank >"$RUN_DIR/chrome.log" 2>&1 &
echo $! > "$RUN_DIR/chrome.pid"
```

Dedicated `--user-data-dir` is not optional. It keeps the run out of Ryan's logged-in
profile and makes the run's browser identifiable at teardown. Drop `--headless=new` only
when the app renders differently headless.

## 4. Build-identity gate — run before every sweep

Two parts. Both must pass or the sweep result is void: rebuild, restart, re-gate. A
failed gate is never recorded as "not landed" — it is recorded as "not verified".

```sh
# (a) the process serving $PORT is rooted in this worktree
PID=$(lsof -ti tcp:$PORT -sTCP:LISTEN | head -1)
lsof -a -p "$PID" -d cwd -Fn | sed -n 's/^n//p'      # must equal $WORKTREE

# (b) the phase's sentinel reaches the served output
$CD navigate --new-tab --wait-until load "$APP_URL"
$CD evaluate 'document.querySelector("[data-testid=\"<sentinel>\"]") !== null'
```

The sentinel is a string that exists **only** after this phase's change — a new
`data-testid`, a new route, a new label. Name one per phase while writing the brief. If a
phase has no observable sentinel, it has no browser verification; say so and give it a
command gate instead.

## 5. Sweep agent

```sh
timeout 900 codex exec \
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

`timeout` is required. A codex run that hangs at 3am costs the whole night.

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
timeout 1800 codex exec \
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
curl -sf -o /dev/null "$APP_URL"                          || echo "STUCK: dev server down"
curl -sf -o /dev/null http://127.0.0.1:9222/json/version  || echo "STUCK: chrome down"
pgrep -f "codex exec" | wc -l                             # expect 0 between phases
jobs -l                                                    # expect no stopped jobs
```

Anything stuck gets killed and restarted, not waited on.

## 9. Teardown — runs on success, failure, and abort

```sh
for f in "$RUN_DIR"/*.pid; do kill "$(cat "$f")" 2>/dev/null; done
lsof -ti tcp:$PORT -sTCP:LISTEN | xargs -r kill 2>/dev/null
pgrep -fl "remote-debugging-port=9222|codex exec|$WORKTREE"   # confirm empty
```

Kill by recorded PID first; the `pgrep` is a confirmation sweep, not the mechanism.

**Never run a bare `pkill -f chrome` or `pkill -f node`** — that kills Ryan's own browser
and unrelated work. The dedicated profile, the claimed port, and the PID ledger exist so
teardown can be precise.
