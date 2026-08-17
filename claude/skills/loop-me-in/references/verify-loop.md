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

`$RUN_DIR` contains spaces on this machine — the plans symlink resolves through
`Mobile Documents` and `Claude Plans`. **Quote every use of it**, and never build a file
list by word-splitting a path.

> [!important] **These helpers must run under `bash`, not `zsh`.**
> They use bash arrays (`declare -a`, `"${arr[@]}"`, `+=`) and `[[ ]]`, and Ryan's login
> shell is zsh. Put `#!/usr/bin/env bash` at the top of the brief's helper block, or invoke
> each gate as `bash -c '…'`, and state which in the brief.
>
> **Arrays, never space-joined strings.** File lists are carried as arrays and expanded
> quoted, so a path containing a space stays one argument. This is also why nothing here
> relies on word-splitting: zsh doesn't split unquoted expansions at all, so a helper built
> on splitting collapses its list into one bogus path under zsh and the runner reports
> "no tests found" — which a fix loop reads as green.

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
children behind, so run the heartbeat (section 9) after any 142.

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

Both parts must **assert**. Printing a value is not a gate: an earlier version of this
block printed the serving cwd without ever comparing it, and `$CD evaluate` exits 0 while
printing `false`, so a missing sentinel passed at the shell level.

```sh
identity_gate() {    # returns non-zero if the thing under test is not this worktree's build
  local pid cwd sentinel

  # (a) the process serving $PORT is rooted in this worktree
  pid=$(lsof -ti "tcp:$PORT" -sTCP:LISTEN | head -1)
  [ -n "$pid" ] || { echo "identity: nothing listening on $PORT" >&2; return 1; }
  cwd=$(lsof -a -p "$pid" -d cwd -Fn | sed -n 's/^n//p')
  # contract: the serving cwd is the worktree or a directory beneath it
  case "$cwd" in
    "$WORKTREE"|"$WORKTREE"/*) ;;
    *) echo "identity: port $PORT served from '$cwd', not under '$WORKTREE'" >&2; return 1 ;;
  esac

  # (b) the phase's sentinel reaches the served output — same tab, every time
  "$CD" navigate --wait-until load "$APP_URL" >/dev/null || {
    echo "identity: navigate failed" >&2; return 1; }
  sentinel=$("$CD" evaluate \
    'document.querySelector("[data-testid=\"<sentinel>\"]") !== null')
  [ "$sentinel" = "true" ] || {
    echo "identity: sentinel absent (evaluate returned '$sentinel')" >&2; return 1; }

  return 0
}
```

The sentinel is a string that exists **only** after this phase's change — a new
`data-testid`, a new route, a new label. Name one per phase while writing the brief. A
phase with no observable sentinel has no browser verification: say so, and give it a
command gate instead.

## 4. Agent configuration — effort, and prompt style

Applies to every codex call in this file: sweep, fix, and diagnose.

**`~/.codex/config.toml` sets `model_reasoning_effort = "xhigh"` globally.** Every agent
that does not override it runs at xhigh, including a sweep whose whole job is to click
four things and report what it saw. Always pass the flag explicitly.

```sh
effort_for() {   # effort_for <role> [attempt] — attempt defaults, so `effort_for diagnose`
                 # cannot abort under `set -u`
  local role="$1" attempt="${2:-1}"
  set -- "$role" "$attempt"
  case "$1:$2" in
    sweep:1)  echo low     ;;   # acceptance rows name a selector and expected text: a checklist
    sweep:2)  echo medium  ;;   # something didn't land — look harder
    sweep:3)  echo high    ;;   # last look before the cap, and the one Ryan reads
    fix:1)    echo medium  ;;   # named gap, file guess in hand, stated verification command
    fix:2)    echo high    ;;
    fix:3)    echo "effort_for: attempt 3 is the diagnose agent, not a third fix" >&2
              echo xhigh   ;;   # loud, not a silent fallthrough
    diagnose*) echo xhigh  ;;   # see below — matches with or without an attempt number
    *)        echo medium  ;;
  esac
}
```

Two adjustments on top of the ladder:

- **Behavioural acceptance rows start one rung higher.** "The panel reflows without
  clipping at 768px" is a judgement; "`[data-testid=save]` is enabled" is a lookup. Where
  a phase's rows are the former, start its sweeps at `medium`.
- **Fixes touching shared state, async ordering, or three-plus files start at `high`.**
  A one-string edit does not.

**There is no `fix:3`** — attempt 3 calls the `diagnose` agent (section 7) instead, at
`xhigh` and `--sandbox read-only`. It returns a root cause and a verdict on whether the
plan's premise still holds, writes no code, and the phase stops red with that entry in the
findings log.

Codex cannot invoke `/caveman:caveman`, so every codex prompt opens with the compression
rules inline:

```
Style: terse. Drop articles, filler, hedging. Fragments fine. No preamble, no
narration, no restating the task, no summary paragraph. Reproduce EXACTLY, never
paraphrased or shortened: error strings, selectors, file paths, numbers, units,
code. Output the contract block and nothing else.
```

An agent that also writes three paragraphs explaining what it did costs more than the work
it did.

## 5. Sweep agent

```sh
with_timeout 900 codex exec \
  -C "$WORKTREE" \
  -m gpt-5.6-sol \
  -c model_reasoning_effort="$(effort_for sweep "$ATTEMPT")" \
  -c sandbox_workspace_write.network_access=true \
  --sandbox workspace-write \
  --add-dir "$RUN_DIR" \
  --output-last-message "$RUN_DIR/sweep-p$N-a$ATTEMPT.md" \
  "$(cat "$RUN_DIR/sweep-prompt-p$N-a$ATTEMPT.md")"
```

`sandbox_workspace_write.network_access=true` is required — `workspace-write` blocks
network by default and CDP on `127.0.0.1:$CDP_PORT` counts as network. Without it the
sweep reports a connection error that reads like a broken app.

The sweep prompt carries the style preamble from section 4, the app URL, the `$CD` path
and its `--help` hint, the phase's acceptance rows, the sentinel, the scope fence, and
this output contract — which is the whole response:

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

## 6. Findings log — append after every sweep

The per-sweep files answer "what happened in phase 3". The findings log answers "what did
last night find", which is the question actually asked the next morning.

```sh
{
  echo "## P$N attempt $ATTEMPT — <phase name>"
  echo "identity: $(sed -n 's/^IDENTITY: //p' "$RUN_DIR/sweep-p$N-a$ATTEMPT.md")"
  sed -n '/^ACCEPTANCE:/,/^REGRESSIONS:/p' "$RUN_DIR/sweep-p$N-a$ATTEMPT.md"
  sed -n '/^REGRESSIONS:/,$p'              "$RUN_DIR/sweep-p$N-a$ATTEMPT.md"
  echo "evidence: $RUN_DIR/p$N-*.png, $RUN_DIR/p$N-console.log"
  echo
} >> "$FINDINGS"
```

Append after every sweep — passes included, and void sweeps too, whose entry reads
`identity: fail` and says why nothing was verified. The `OUT-OF-SCOPE` lines are the ones
that exist nowhere else: the post's word ceiling will not carry them.

## 7. Fix agent

```sh
with_timeout 1800 codex exec \
  -C "$WORKTREE" \
  -m gpt-5.6-sol \
  -c model_reasoning_effort="$(effort_for fix "$ATTEMPT")" \
  --sandbox workspace-write \
  --output-last-message "$RUN_DIR/fix-p$N-a$ATTEMPT.md" \
  "$(cat "$RUN_DIR/fix-prompt-p$N-a$ATTEMPT.md")"
```

The fix prompt carries the sweep's `GAPS` verbatim, the scope fence, and the verification
command. Codex does not commit and does not stage — the run reviews the diff, then
`git add` plus the `/commit` skill.

**The fix prompt states the specs are read-only**, naming this phase's spec files and the
earlier run specs as files it may read but never modify, and instructing it to report "spec
appears to misencode the requirement" as its answer rather than adjusting an assertion.
Without that sentence an agent told to make a test pass will eventually edit the test.

Check the diff before committing. This must **return non-zero on violation** — a guard that
prints a warning and exits 0 is not a guard:

```sh
# RUN_SPEC_FILES is a bash array, appended to as each spec is committed:
#   declare -a RUN_SPEC_FILES=(); RUN_SPEC_FILES+=("$spec")
assert_specs_untouched() {
  local -a changed=() protected=("${RUN_SPEC_FILES[@]}")
  # staged, unstaged AND untracked — an added file is a modification too
  while IFS= read -r -d '' f; do changed+=("$f"); done < <(
    { git diff --name-only -z; git diff --cached --name-only -z
      git ls-files -z --others --exclude-standard; } )
  local c p
  for c in "${changed[@]}"; do
    for p in "${protected[@]}"; do
      [ "$c" = "$p" ] && { echo "STOP: fix attempt modified spec $c" >&2; return 1; }
    done
  done
  return 0
}
```

Exact `=` comparison, not `grep` — substring matching lets `a.spec.ts` match
`not-a.spec.ts.bak`. NUL-delimited, so a path with spaces survives.

On attempt 3, this becomes the diagnosis agent instead:

```sh
with_timeout 1800 codex exec \
  -C "$WORKTREE" \
  -m gpt-5.6-sol \
  -c model_reasoning_effort="$(effort_for diagnose)" \
  --sandbox read-only \
  --output-last-message "$RUN_DIR/diagnose-p$N.md" \
  "$(cat "$RUN_DIR/diagnose-prompt-p$N.md")"
```

## 8. Loop control and gate tiers

```
spec commit (red, reason recorded)
   ↓
build → identity gate → spec + sweep → spec green, rows landed, no in-scope
                                 │      regressions? → commit, next phase
                                 ↓ no
                              fix agent (implementation only) → attempt += 1 → back to build
```

Cap at **3 sweeps per phase**. On the third failure, stop that phase, record what is still
red, and move to the next phase that does not depend on it.

**The fix agent may not touch the spec.** Its prompt says so explicitly (section 7). If the
spec itself looks wrong, that is a stop condition for Ryan, not a repair the run performs —
a run that edits its own acceptance criteria has stopped verifying anything.

One codex agent at a time — sweep or fix, never both, never two phases in parallel. Two
`codex exec` runs plus a browser tree is where an unattended night turns into swap.

### Which gate runs when

Every scheduled gate is scoped. The full suite is not one of them — see "Escalation" below.

**`PHASE_IMPACTED` is resolved during the spec session, not here.** Use the repo's own
test-selection or dependency tooling and write the resolved paths into the brief. The two
greps below are a *last-resort fallback* for a repo with no such tooling, and the brief must
say when it fell back to them — they miss single-quoted imports, path aliases, re-exports,
dynamic `import()`, and every extension they don't name, so a gate built on them reports
green over dependencies it never found.

```sh
# FALLBACK ONLY — see the caveat above. Prefer repo-native impacted-test selection.
tests_touching() {   # tests_touching channel-todos
  grep -rl -- "$1" test 2>/dev/null | grep -E '\.test\.tsx?$' | sort -u
}

importers_of() {     # importers_of channel-todos
  grep -rlE "from ['\"][./][^'\"]*$1['\"]" src 2>/dev/null | sort -u
}

# BEFORE implementing, for behavior-red specs only. A non-zero exit is NOT proof of red:
# a missing runner, syntax error, timeout, crash or zero-tests-executed all exit non-zero.
# Red means the NAMED test ran and failed at the PREDICTED assertion.
#   $1 = spec file   $2 = test name as the runner prints it   $3 = expected signature
gate_spec_red() {
  local spec="$1" name="$2" want="$3" rc
  local out="$RUN_DIR/spec-red-p$N-$(basename "$spec").txt"
  bun test "$spec" -t "$name" >"$out" 2>&1; rc=$?

  if [ "$rc" -eq 0 ]; then
    echo "PRE-IMPLEMENTATION PASS — classify before proceeding: requirement already met" >&2
    echo "(report and drop the phase), spec asserts the wrong thing, or spec never ran." >&2
    return 2
  fi
  # proof the named test actually executed — an empty run also exits non-zero
  grep -qE '([1-9][0-9]*) fail' "$out" || {
    echo "INFRASTRUCTURE FAILURE, not red: no test failure reported. See $out" >&2; return 3; }
  grep -qF -- "$name" "$out" || {
    echo "INFRASTRUCTURE FAILURE: named test '$name' never ran. See $out" >&2; return 3; }
  grep -qF -- "$want" "$out" || {
    echo "RED FOR THE WRONG REASON: expected signature '$want' absent. See $out" >&2; return 4; }

  echo "red as predicted; receipt: $(git rev-parse HEAD) / $out"
  return 0
}

# NEVER call the runner with an empty file list: `bun test` with no arguments runs the
# WHOLE SUITE, which is the one thing the tier scheme exists to avoid. Every gate below
# refuses to run rather than widen silently.
run_tests() {        # run_tests <file>...
  [ "$#" -gt 0 ] || { echo "GATE ERROR: empty test list — refusing to run" >&2; return 1; }
  bun test "$@"
}

gate_attempt() {     # seconds — runs on every build inside the fix loop
  run_tests "${PHASE_SPEC_FILES[@]}" && bun run typecheck
}

gate_phase() {       # tens of seconds — runs once, when gate_attempt goes green
  # every spec written so far this run, so a new phase cannot satisfy its own
  # requirement by breaking an earlier one, plus the impacted set
  local -a files=("${RUN_SPEC_FILES[@]}" "${PHASE_IMPACTED[@]}")
  local -a uniq=(); local f
  for f in "${files[@]}"; do
    [[ " ${uniq[*]} " == *" $f "* ]] || uniq+=("$f")
  done
  run_tests "${uniq[@]}" && bun run typecheck
}

gate_wave() {        # wave boundary — the union of this wave's phase tiers, NOT the suite
  # WAVE_TESTS is the accumulated union of every phase tier in this wave, built as each
  # phase completes — not rediscovered here, or it silently disagrees with what ran before
  run_tests "${WAVE_TESTS[@]}" || return 1
  with_timeout 900 bash -c \
    "$TYPECHECK && $LINT && $BUILD${DIST_CHECK:+ && $DIST_CHECK}"
}
```

Lint, typecheck, build and the dist check stay at the wave boundary because they are fast.
It is the test runner that is expensive, so the wave tier runs the union of its own phases'
tiers rather than everything in the repo.

`$LINT`, `$TYPECHECK`, `$BUILD`, `$DIST_CHECK` are the adapters resolved for this repo
during the spec session. `DIST_CHECK` is intentionally optional — a repo without one omits
the gate rather than inheriting `bun tools/check-dist.ts` from a project that has it. The
`bun test` / `bun run` spellings above are this stack's adapters too; a Go, Python or Rust
repo substitutes its own and the tier structure is unchanged.

**Arrays, not strings.** Every list here is a bash array (`PHASE_SPEC_FILES`,
`PHASE_IMPACTED`, `RUN_SPEC_FILES`, `WAVE_TESTS`), expanded as `"${arr[@]}"`. That is what
makes the earlier "quote every path, never word-split" rule and these helpers consistent —
the previous version relied on word-splitting and contradicted it. Initialise each as
`declare -a NAME=()` at the top of the brief's helper block and append with `NAME+=("$x")`.

`PHASE_IMPACTED` is resolved **before the run**, during the spec session, using the repo's
own dependency or test-selection tooling — not rediscovered at 3am with `grep`. A grep for
`from "…"` misses single-quoted imports, aliases, re-exports and dynamic imports, so a
gate built on it reports green over dependencies it never found.

### Reproducing one failure

The sweep's `GAPS` line carries the failing case's own command. Re-run **that**, never the
suite that contains it:

```sh
bun test "<the spec file>" -t "<the failing test name>"
```

Minutes per attempt disappear here. A fix loop that re-runs a 224-second suite to see one
assertion fail spends the night in the test runner.

### Escalation — the only two full-suite runs

```sh
gate_full() {        # minutes. Log WHY before calling this.
  echo "## ESCALATION $(printf '%s' "$1") — full suite" >> "$FINDINGS"
  with_timeout 900 bun test
}
```

1. **Phase 0**, once, to capture the baseline. Without it no later number is interpretable.
2. **When a failure will not localize** — the phase tier comes back green while the sweep
   still reports a regression, or the fix loop cannot find where a failure originates.

That is the whole list. Not per attempt, not per phase, not per wave, not "to be safe".
Every escalation run writes its reason to the findings log first and is named in the
report, so the one expensive run of the night is always accountable.

### Which baseline each tier is checked against

| Tier | Green means |
|---|---|
| spec-red | the phase's spec FAILS, for the reason the requirement predicts — recorded before any implementation |
| attempt | the phase's spec file passes, typecheck clean |
| phase | that spec, every earlier spec in the run, and every importer's suite pass, typecheck clean |
| wave | the union of the wave's phase tiers passes, plus lint, typecheck, build, dist check |
| escalation | the phase-0 full-suite baseline, with zero new failures and no new failing suite names |

A targeted run cannot be compared against a full-suite count. Recording "green" for a
subset against a whole-repo baseline is how a broken repo reads as a passing one.

## 9. Heartbeat — between every phase

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

## 10. Teardown — runs on success, failure, and abort

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
