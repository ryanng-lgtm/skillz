# Verify-loop recipes

The operational half of the self-verifying brief; the rules these implement are in `../SKILL.md`. **Copy the resolved code into the brief.** The run never reads this file, and a brief that links to it fails the stand-alone test.

## 0. run.sh — every helper runs through one bash dispatcher

An agent's shell tool starts a fresh shell for every call, and that shell may be zsh. Helpers sourced into it lose their arrays and state between calls, and a code block pasted into it runs with whatever variables are empty: `git -C ""` acts on the current repo, and an empty profile path matches every browser on the machine. So the brief carries one script and the run only ever executes it:

- **`run.sh` is every `bash` block in this file that has a `# run.sh:` header line, joined in the order they appear,** with the placeholders resolved. Nothing else goes in it. The brief carries it as one bash block, and `init` refuses to start if any verb is missing from it. Its only top-level commands are the guards, the state load and the dispatch; everything else is a function.
- The run's first action after cutting the worktree writes it to `"<evidence dir>/run.sh"`, then runs `init`.
- Every helper is called as `bash "<evidence dir>/run.sh" <verb> [args...]`, from any shell. **Never `source` run.sh, and never paste a block from this file into a shell.**
- Values that change during the run live in `"$RUN_DIR/state.sh"`. A verb that changes them holds a kernel lock from load to save and writes through `mktemp` and `mv`; every other verb reads without a lock.
- Give every run.sh call a shell-tool timeout above what it can take: a writer waits up to 60 s for the lock (Claude Code's 120 s default covers it). Every `codex_call` and `claude_call`, every `gate_*`, `run_tests` and `test_one`, and every `ensure_*` runs in the background, and the run waits for it to finish.

| Verb | Does | The run calls it |
|---|---|---|
| `init` | moves any earlier `state.sh`, `browser.launches` and `*.pid` files into `stale-<time>-<pid>/`, starts fresh state | once, as the first action of a new run |
| `resume` | keeps the saved state and prints it | instead of `init`, when continuing a run that stopped, on the same worktree |
| `state` | prints the saved state | any time |
| `start_phase <n> <gate spec files...>` | sets the phase, attempt 1, its gate specs | as each phase begins |
| `set_impacted <files...>` | the phase's impacted suites, from the brief; fails before `start_phase` | right after `start_phase` |
| `spec_committed <path>` | adds a committed spec to the run's protected list | after each spec commit |
| `next_attempt` | attempt + 1; refuses a fourth | after each fix, before rebuilding |
| `phase_done` | adds the phase tier to the wave's union | after the phase's implementation commit |
| `new_wave` | empties the wave's union | as each wave after the first begins |
| `with_timeout <secs> <cmd...>` | time-boxes a command | every long-running command outside run.sh |
| `ensure_dev_server`, `ensure_browser`, `browser_works` | section 2, 3 | before phase 1 and at each heartbeat |
| `b_nav`, `b_eval`, `b_shot`, `b_logs` | the script harness's browser verbs | in sweeps, by any worker |
| `identity_cwd`, `identity_gate <js>` | section 4 | before every sweep |
| `effort_for`, `codex_model`, `claude_model`, `codex_call`, `claude_call` | section 5 | every agent call |
| `log_sweep <phase name>`, `log_append <file>` | section 7 | after every sweep, receipt and verdict |
| `assert_specs_untouched` | section 8 | before every commit |
| `gate_spec_red`, `test_one`, `run_tests`, `gate_attempt`, `gate_phase`, `gate_wave`, `gate_full` | section 9 | per the gate tiers |
| `heartbeat`, `teardown` | sections 10, 11 | between phases; on success, failure and abort |
| `review_diff` | section 13 | before every diff review |

```bash
#!/usr/bin/env bash
# run.sh: configuration. Run as: bash "<evidence dir>/run.sh" <verb> [args]. Never source it.
WORKTREE="<absolute worktree path>"
RUN_DIR="<absolute evidence dir>"            # beside the brief, never /tmp
FINDINGS="$RUN_DIR/findings.md"
PORTS=(5173 5174 5175)                       # app ports to try, in order
APP_PATH="/<route>"
CDP_PORT_FIRST=9222                          # the run's browser debugging port
CHROME="<resolved Chrome or Chromium binary>" # script harness only
PROFILE="$RUN_DIR/browser-profile"

# Adapters: command strings bash runs in the worktree, arguments arriving as "$1",
# "$@". An example stack; resolve this repo's own. An empty adapter is skipped.
START='npm run dev -- --port "$1" --strictPort'
TEST_FILES='npx vitest run "$@"'
TEST_ONE='npx vitest run "$1" -t "$2"'
FULL_SUITE='npx vitest run'
FAIL_PATTERN='[1-9][0-9]* failed'            # the runner's line reporting a non-zero failure count
TYPECHECK='npm run typecheck'
LINT='npm run lint'
BUILD='npm run build'
DIST_CHECK=''                                # omitted: <why>

# Browser verbs for a script harness (Playwright, a CDP script), seeing $CDP_PORT in
# their environment. Leave all four empty with a browser MCP server.
B_NAV='<command that navigates the run tab to "$1" and waits for load>'
B_EVAL='<command that prints the value of the JS expression "$1">'
B_SHOT='<command that writes a screenshot to "$1">'
B_LOGS='<command that writes raw console and network output to "$1">'
```

```bash
# run.sh: guards. Nothing runs with an empty, relative or unresolved path.
_die() { echo "run.sh: $*" >&2; exit 2; }
: "${WORKTREE:?run.sh: WORKTREE is empty}" "${RUN_DIR:?run.sh: RUN_DIR is empty}"
case "$WORKTREE$RUN_DIR" in *'<'*) _die "unresolved placeholder in WORKTREE or RUN_DIR" ;; esac
case "$WORKTREE" in /*) ;; *) _die "WORKTREE is not absolute: $WORKTREE" ;; esac
case "$RUN_DIR" in /*) ;; *) _die "RUN_DIR is not absolute: $RUN_DIR" ;; esac

_need_worktree() {   # before anything that runs git or starts processes there
  local top gitdir common
  top=$(git -C "$WORKTREE" rev-parse --show-toplevel 2>/dev/null) || _die "no git repo at $WORKTREE"
  [ "$(cd "$top" && pwd -P)" = "$(cd "$WORKTREE" && pwd -P)" ] || _die "$WORKTREE is not a worktree root"
  gitdir=$(cd "$WORKTREE" && cd "$(git rev-parse --git-dir)" && pwd -P)
  common=$(cd "$WORKTREE" && cd "$(git rev-parse --git-common-dir)" && pwd -P)
  [ "$gitdir" != "$common" ] || _die "$WORKTREE is a main checkout, not the run's linked worktree"
}
_under_worktree() {  # is $1 the worktree or beneath it? (physical paths)
  local wt
  wt=$(cd "$WORKTREE" 2>/dev/null && pwd -P) || return 1
  case "$1" in "$wt"|"$wt"/*) return 0 ;; esac
  return 1
}
_has() {             # _has <item> <list...>: exact membership, safe for paths with spaces
  local x="$1" y; shift
  for y in "$@"; do [ "$x" = "$y" ] && return 0; done
  return 1
}
```

```bash
# run.sh: state, saved under a kernel lock
STATE_VARS=(PORT APP_URL CDP_PORT N ATTEMPT PHASE_SPEC_FILES PHASE_IMPACTED RUN_SPEC_FILES WAVE_TESTS)
_defaults() {
  PORT="${PORTS[0]}"; APP_URL="http://127.0.0.1:$PORT$APP_PATH"; CDP_PORT="$CDP_PORT_FIRST"
  N=0; ATTEMPT=0; PHASE_SPEC_FILES=(); PHASE_IMPACTED=(); RUN_SPEC_FILES=(); WAVE_TESTS=()
}
LOCK="$RUN_DIR/state.lock"; LOCK_WAIT=60
STARTED=; STARTED_FILE=   # a process this call started and has not saved yet, and its pid file
_lock() {            # flock on fd 9, which the kernel holds until this process exits, however it exits
  exec 9>>"$LOCK" || _die "cannot open the state lock $LOCK"
  perl -e 'use Fcntl ":flock"; $SIG{ALRM} = sub { exit 3 }; alarm shift;
           open(my $f, ">>&=", 9) or die "fd 9: $!\n"; flock($f, LOCK_EX) or die "flock: $!\n"' "$LOCK_WAIT"
  case $? in
    0) return 0 ;;
    3) [ -z "$STARTED" ] || { kill "$STARTED" 2>/dev/null; rm -f "$STARTED_FILE"
         echo "run.sh: killed PID $STARTED, which this call started and could not record" >&2; }
       _die "another run.sh call has held $LOCK for ${LOCK_WAIT}s: \`lsof \"$LOCK\"\` names it; wait for it or kill it (a dead holder releases the lock by itself)" ;;
    *) _die "could not take the state lock $LOCK" ;;
  esac
}
_unlock() { exec 9>&-; }   # only a slow verb releases early; a writer holds the lock until it exits
_save() {            # an atomic rename, so readers never see a half-written file
  local tmp
  tmp=$(mktemp "$RUN_DIR/.state.XXXXXX") || return 1
  declare -p "${STATE_VARS[@]}" > "$tmp" && mv "$tmp" "$RUN_DIR/state.sh" || { rm -f "$tmp"; return 1; }
}
_in_phase() { [ "$N" -gt 0 ] || _die "$1 before start_phase"; }

init() {             # a new run: check run.sh is whole, set earlier state aside, never delete it
  local old f pid v
  # shellcheck disable=SC2086
  for v in _die _has _need_worktree _save _lock $VERBS; do
    declare -F "$v" >/dev/null || _die "run.sh is incomplete: $v is not defined"
  done
  old="$RUN_DIR/stale-$(date +%Y%m%d-%H%M%S)-$$"   # unique, even for two inits in one second
  for f in "$RUN_DIR/state.sh" "$RUN_DIR/browser.launches" "$RUN_DIR"/*.pid "$RUN_DIR"/*.pid.reused; do
    [ -e "$f" ] || continue
    pid=$(cat "$f" 2>/dev/null)
    case "$f" in *.pid) kill -0 "$pid" 2>/dev/null && echo "still running: PID $pid from $f" >&2 ;; esac
    mkdir -p "$old" && mv "$f" "$old/" && echo "moved aside: $f -> $old/" >&2
  done
  return 0
}
resume() { _need_worktree; state; }
state()  { declare -p "${STATE_VARS[@]}"; }
start_phase() {      # start_phase <n> <gate spec files...>
  { [ $# -ge 1 ] && [ "$1" -gt 0 ]; } 2>/dev/null || _die "usage: start_phase <n> <gate spec files...>"
  N="$1"; ATTEMPT=1; shift; PHASE_SPEC_FILES=("$@"); PHASE_IMPACTED=()
}
set_impacted()   { _in_phase set_impacted; PHASE_IMPACTED=("$@"); }
spec_committed() {   # spec_committed <repo-relative path, as git prints it>
  _in_phase spec_committed; [ $# -eq 1 ] || _die "usage: spec_committed <path>"
  _has "$1" "${RUN_SPEC_FILES[@]}" || RUN_SPEC_FILES+=("$1")
}
next_attempt() {
  _in_phase next_attempt
  [ "$ATTEMPT" -lt 3 ] || _die "attempt 3 was the last: diagnose, mark phase $N red, move on"
  ATTEMPT=$((ATTEMPT + 1))
}
phase_done() {
  local f
  _in_phase phase_done
  for f in "${RUN_SPEC_FILES[@]}" "${PHASE_IMPACTED[@]}"; do
    _has "$f" "${WAVE_TESTS[@]}" || WAVE_TESTS+=("$f")
  done
}
new_wave() { WAVE_TESTS=(); }
```

`state.sh` is written by `declare -p` and read only by run.sh's own bash, never by the agent's shell. The lock is `flock` on `state.lock`, taken through perl's Fcntl because macOS ships no `flock` command: the kernel holds it on the writer's open descriptor and drops it when that process exits, killed or not, so there is no PID file, no age check and nothing to take over. A live holder makes the next writer wait up to `LOCK_WAIT` seconds, then it dies naming the lock. `ensure_dev_server` and `ensure_browser` run unlocked and take the lock only to merge their own variables into the state (section 15) and to bump the browser launch counter, so a browser launch never holds up another writer.

## 1. `with_timeout`

```bash
# run.sh: with_timeout
with_timeout() {     # with_timeout <seconds> <command...>
  if command -v timeout >/dev/null 2>&1; then timeout "$@"
  else perl -e 'alarm shift; exec @ARGV' "$@"; fi
}
_adapter() {         # _adapter <seconds> <command string> [args...]: in the worktree, args kept whole
  local secs="$1" cmd="$2"; shift 2
  _need_worktree
  ( cd "$WORKTREE" && with_timeout "$secs" bash -c "$cmd" _ "$@" )
}
```

macOS ships no `timeout`, and a brief that calls it dies on `command not found` in phase 1. Perl's pending `alarm` survives `exec`, so the command itself takes the signal. A timed-out command exits 124 (`timeout`) or 142 (perl); either is an infrastructure failure, never a red result. The signal reaches only the launched process, so run `heartbeat` after a timeout to catch orphaned children.

## 2. The dev server: reuse first, then start

One dev server for the whole run, started once, before phase 1; later calls find and reuse it.

```bash
# run.sh: processes and the dev server
_listener() { lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null | head -1; }    # PID listening on a port
_cwd_of()   { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; } # that process's cwd
# Linux without lsof: `ss -ltnp "sport = :<port>"` gives the PID, `readlink /proc/<pid>/cwd` the cwd.
_pids_with() {      # PIDs whose command line has $1 as a whole argument (fixed string)
  [ -n "$1" ] || _die "_pids_with: empty pattern"
  ps -Ao pid=,command= | PAT="$1" awk '{
    p = ENVIRON["PAT"]; at = 0          # at: where the unsearched rest of the line starts
    while ((i = index(substr($0, at + 1), p)) > 0) {
      i += at; c = substr($0, i + length(p), 1)   # a space before, a space or the end after:
      if (substr($0, i - 1, 1) == " " && (c == "" || c == " ")) { print $1; next }   # a whole argument
      at = i
    } }'
}
_is_ours() {        # does PID $1 still belong to this run? PIDs are reused after a process exits
  [ -n "$1" ] && kill -0 "$1" 2>/dev/null || return 1
  _pids_with "--user-data-dir=$PROFILE" | grep -qx -- "$1" && return 0
  _under_worktree "$(_cwd_of "$1")"
}
_kill_ours() { _is_ours "$1" && kill "$1" 2>/dev/null; }

ensure_dev_server() {   # ours on the saved port first, then the first free port
  local p holder pid
  local -a order=("$PORT")
  _need_worktree
  pid=$(cat "$RUN_DIR/dev.pid" 2>/dev/null)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then   # ours is alive: never start a second
    for _ in $(seq 60); do
      holder=$(_listener "$PORT")
      [ -n "$holder" ] && _under_worktree "$(_cwd_of "$holder")" && return 0
      sleep 0.5
    done
    _die "dev server $pid is alive but not serving this worktree on :$PORT (see dev.log)"
  fi
  for p in "${PORTS[@]}"; do _has "$p" "${order[@]}" || order+=("$p"); done
  for p in "${order[@]}"; do
    holder=$(_listener "$p")
    if [ -z "$holder" ]; then
      ( cd "$WORKTREE" && exec bash -c "$START" _ "$p" ) >>"$RUN_DIR/dev.log" 2>&1 9>&- &
      STARTED=$!; STARTED_FILE="$RUN_DIR/dev.pid"; echo "$STARTED" > "$STARTED_FILE"
    elif _under_worktree "$(_cwd_of "$holder")"; then
      [ -e "$RUN_DIR/dev.pid" ] || echo "$holder" > "$RUN_DIR/dev.pid.reused"
    else
      echo "port $p: foreign process $holder, skipped" >&2; continue   # never kill it
    fi
    PORT="$p"; APP_URL="http://127.0.0.1:$p$APP_PATH"; return 0
  done
  _die "every port in PORTS is held by a foreign process"
}
```

- `START` pins the port and fails when it is taken (`--strictPort` or the stack's equivalent). A server that silently moves to the next free port leaves the sweep verifying whatever was already on `$PORT`.
- The saved port is checked first, so a foreign holder that has since left an earlier port never causes a second server.
- `dev.pid` is torn down; `dev.pid.reused` never is. A server is "reused" only when this run did not start it, and killing one takes down whatever did.

## 3. The browser: reuse first, smoke-test, then trust it

Every sweep uses four browser verbs: navigate the run's one tab and wait for load (`b_nav <url>`, non-zero on failure), print an expression's value (`b_eval <js>`), write a non-empty screenshot (`b_shot <path>`), and write raw console and network output (`b_logs <path>`).

- **With a script harness** (Playwright, a CDP script), they are run.sh verbs built from `B_NAV`, `B_EVAL`, `B_SHOT` and `B_LOGS`, and any worker, a CLI one included, calls them as `bash "<evidence dir>/run.sh" b_nav <url>`.
- **With a browser MCP server**, they are its navigate, evaluate, screenshot and console tools, which exist only in the session that has the server. The sweep then runs in the run itself, or in a subagent that inherits its tools, never through a CLI worker (`codex exec`, `claude -p`). The identity gate's part (a) is still `identity_cwd`; part (b), the smoke test and the heartbeat's browser check are tool calls, each result asserted exactly as the verbs below assert it. A tool call that returns `false` is a failed gate, not a successful call.

The run owns its browser: a dedicated profile under `$RUN_DIR`, its own debugging port, headless unless the app renders differently headless.

```bash
# run.sh: the browser (script harness)
_b() {              # _b <command string> [args...]
  local cmd="$1"; shift
  [ -n "$cmd" ] || _die "no script harness: browser checks are the session's MCP tool calls"
  export CDP_PORT; with_timeout 120 bash -c "$cmd" _ "$@"
}
b_nav()  { _b "$B_NAV" "$@"; }
b_eval() { _b "$B_EVAL" "$@"; }
b_shot() { _b "$B_SHOT" "$@"; }
b_logs() { _b "$B_LOGS" "$@"; }

_browser_is_ours() {
  local holder; holder=$(_listener "$CDP_PORT"); [ -n "$holder" ] || return 1
  _pids_with "--user-data-dir=$PROFILE" | grep -qx "$holder"
}
browser_works() {   # functional, not merely listening
  curl -sf --max-time 5 -o /dev/null "http://127.0.0.1:$CDP_PORT/json/version" || return 1
  b_nav "about:blank" >/dev/null 2>&1 || return 1
  [ "$(b_eval '1+1' 2>/dev/null | tr -dc 0-9)" = "2" ] || return 1
  rm -f "$RUN_DIR/smoke.png"; b_shot "$RUN_DIR/smoke.png" >/dev/null 2>&1
  [ -s "$RUN_DIR/smoke.png" ]
}
_start_browser() {
  "$CHROME" --remote-debugging-port="$CDP_PORT" --user-data-dir="$PROFILE" \
    --headless=new --no-first-run --no-default-browser-check \
    --disable-extensions --disable-background-networking \
    about:blank >>"$RUN_DIR/browser.log" 2>&1 9>&- &
  STARTED=$!; STARTED_FILE="$RUN_DIR/browser.pid"; echo "$STARTED" > "$STARTED_FILE"
  for _ in $(seq 30); do
    curl -sf --max-time 5 -o /dev/null "http://127.0.0.1:$CDP_PORT/json/version" && return 0
    sleep 0.5
  done
  return 1
}
_take_launch() {    # bump the on-disk launch counter under the lock, held for the counter alone; false once spent
  local n
  _lock; n=$(cat "$RUN_DIR/browser.launches" 2>/dev/null || echo 0)
  [ "$n" -ge 2 ] || echo $((n + 1)) > "$RUN_DIR/browser.launches"
  _unlock; [ "$n" -lt 2 ]
}
_port_frees() {      # waits up to 10 s for nothing to listen on $CDP_PORT
  for _ in $(seq 20); do [ -z "$(_listener "$CDP_PORT")" ] && return 0; sleep 0.5; done
  return 1
}
ensure_browser() {  # at most TWO launches for the whole run, counted on disk
  local p pids
  _browser_is_ours && browser_works && return 0
  if [ -n "$(_listener "$CDP_PORT")" ] && ! _browser_is_ours; then
    CDP_PORT=$((CDP_PORT + 1))           # a foreign browser: step aside, never kill
  fi
  while _take_launch; do
    if _browser_is_ours && ! browser_works; then   # ours but failing the smoke test: kill it, wait for the port
      pids="$(cat "$RUN_DIR/browser.pid" 2>/dev/null) $(_listener "$CDP_PORT")"   # the listener too, when init set its pid file aside
      for p in $pids; do _kill_ours "$p"; done
      _port_frees || {                   # it ignored SIGTERM: force it, still only if it is ours
        for p in $pids $(_listener "$CDP_PORT"); do _is_ours "$p" && kill -9 "$p" 2>/dev/null; done
        _port_frees; }
    fi
    _browser_is_ours || _kill_ours "$(cat "$RUN_DIR/browser.pid" 2>/dev/null)"   # ours but not serving: reap it
    _browser_is_ours || _start_browser          # a parallel call's browser on the port is ours: keep it
    _browser_is_ours && browser_works && return 0  # never drive a foreign browser
  done
  echo "browser unhealthy after 2 launches: browser phases unverified, command gates only" >&2
  return 1
}
```

- **A debugging port answers even after the renderer has died.** The smoke test navigates, evaluates and writes a fresh screenshot, the three things every sweep depends on; passing it is what "the browser is up" means.
- **The run's own browser failing the smoke test is replaced, not kept.** `ensure_browser` kills it by its recorded PID and the port's listener, each only while it still belongs to the run, waits up to 10 s for the debugging port to free, sends `kill -9` to whichever of them still holds it, then launches a new one. A browser that isn't the run's is never killed.
- **The launch counter lives on disk**, so a restart or a pressure recycle cannot reset it. Only `init` moves it aside.
- **One tab, navigated.** A new tab per acceptance row leaves dozens of live renderers.
- **A harness that launches its own browser** (many MCP servers do) gets an isolated profile when it supports one, never the user's own. Find the browser's PID right after the first navigate and ledger it.

## 4. Build-identity gate — before every sweep

Both parts must pass or the sweep is void: rebuild, restart, re-gate. A failed gate is recorded as *not verified*, never *not landed*. Both parts **assert**: printing the serving cwd without comparing it passes on any cwd, and an evaluate call exits 0 while printing `false`.

```bash
# run.sh: the identity gate
identity_cwd() {    # part (a): the process serving $PORT is rooted in this worktree
  local pid cwd
  pid=$(_listener "$PORT")
  [ -n "$pid" ] || { echo "identity: nothing listening on $PORT" >&2; return 1; }
  cwd=$(_cwd_of "$pid")
  _under_worktree "$cwd" || { echo "identity: :$PORT served from '$cwd', not this worktree" >&2; return 1; }
}
identity_gate() {   # identity_gate <JS expression that is true only with this phase's sentinel>
  local found
  [ -n "$1" ] || _die "usage: identity_gate <sentinel expression>"
  identity_cwd || return 1
  b_nav "$APP_URL" >/dev/null || { echo "identity: navigate failed" >&2; return 1; }
  found=$(b_eval "$1")
  [ "$found" = "true" ] || { echo "identity: sentinel absent (got '$found')" >&2; return 1; }
}
```

The sentinel exists **only** after this phase's change: a new test id, route or label, named per phase while writing the brief, e.g. `identity_gate 'document.querySelector("[data-testid=\"last-login\"]") !== null'`. A command-gated phase replaces part (b) with a command whose output must contain its sentinel: a version string, a new flag in `--help`, a new route's response.

## 5. Agent calls — effort, style, and the reviewer ladder

### Effort

Every agent call sets its effort explicitly; a CLI's global default otherwise applies, including to a sweep whose whole job is to click four things.

```bash
# run.sh: agent calls
effort_for() {      # effort_for <role> [attempt]
  local role="$1" attempt="${2:-1}"
  case "$role:$attempt" in
    sweep:1)       echo low    ;;  # acceptance rows name a selector and expected text: a checklist
    sweep:2)       echo medium ;;  # something didn't land: look harder
    sweep:3)       echo high   ;;  # last look before the cap
    fix:1)         echo medium ;;  # named gap, file guess, stated verification command
    fix:2)         echo high   ;;
    fix:3)         echo "effort_for: attempt 3 is the diagnose agent, not a third fix" >&2
                   echo xhigh  ;;
    diagnose:*)    echo xhigh  ;;
    audit-spec:*)  echo medium ;;  # one spec, one question: does it assert what EXPECTED says?
    review:1)      echo medium ;;  # hunks against the GAPS lines and the scope fence
    review:*)      echo high   ;;  # a second review of one phase: the first fix missed
    audit-brief:*) echo high   ;;  # once per brief; the audit whose miss costs the night
    *)             echo medium ;;
  esac
}
_timeout_for() { case "$1" in fix|diagnose) echo 1800 ;; audit-spec) echo 600 ;; *) echo 900 ;; esac; }

codex_model() {     # for the log only; codex picks its model from its own config
  local m
  m=$(awk -F'"' '/^\[/{exit} /^model *=/{print $2; exit}' ~/.codex/config.toml 2>/dev/null)
  echo "${m:-codex default}"
}
claude_model() {    # for the log only; claude picks its model from its own settings
  local m
  m=$(sed -n 's/^ *"model": *"\([^"]*\)".*/\1/p' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json" 2>/dev/null | head -1)
  echo "${m:-claude default}"
}
codex_call() {      # codex_call <role> <sandbox> <prompt-file> <reply-file> [extra codex args...]
  local role="$1" sandbox="$2" prompt="$3" reply="$4"; shift 4
  local -a dirs=()
  _need_worktree
  [ "$role:$sandbox" != sweep:workspace-write ] || dirs=(--add-dir "$RUN_DIR")   # the sweep writes evidence; a fix worker never writes state.sh, run.sh or findings.md
  with_timeout "$(_timeout_for "$role")" codex exec -C "$WORKTREE" \
    -c model_reasoning_effort="$(effort_for "$role" "$ATTEMPT")" \
    --sandbox "$sandbox" "${dirs[@]}" "$@" --output-last-message "$reply" - < "$prompt"
}
claude_call() {     # claude_call <role> <prompt-file> <reply-file>: plan mode, cannot edit
  _need_worktree
  ( cd "$WORKTREE" && with_timeout "$(_timeout_for "$1")" \
      claude -p --permission-mode plan --effort "$(effort_for "$1" "$ATTEMPT")" \
      --add-dir "$RUN_DIR" ) < "$2" > "$3"
}
```

- **Behavioural acceptance rows start one rung higher.** "The panel reflows without clipping at 768px" is a judgement; "`[data-testid=save]` is enabled" is a lookup.
- **Fixes touching shared state, async ordering, or three or more files start at `high`,** and so does the review of such a diff.
- Each agent takes the level through its own option: codex `-c model_reasoning_effort=<level>`, `claude --effort <level>`, a subagent tool whatever model or effort option it has. Where an agent has none, log that its effort was its default.

### Style preamble

An agent started through a CLI can't load the session's compression skill, so every prompt to one opens with:

```
Style: terse. Drop articles, filler, hedging. Fragments fine. No preamble, no
narration, no restating the task, no summary paragraph. Reproduce EXACTLY, never
paraphrased or shortened: error strings, selectors, file paths, numbers, units,
code. Output the contract block and nothing else.
```

### Calls

Prompts are files in `$RUN_DIR` named `<role>-prompt-p<N>-a<ATTEMPT>.md`, and each reply lands in `<role>-p<N>-a<ATTEMPT>.md` whatever produced it (`bash run.sh state` prints N and ATTEMPT). The reviewer cannot know its own rung, so the run puts a `REVIEWER:` line at the top of every review reply (sections 12 to 14), naming the rung and model: `codex — <model>`, `claude — <model>`, `subagent, different model — <model>`, `fresh subagent, same model — weaker`, `self-review — weaker`.

**Rung 1 — the other agent's CLI.** From Claude Code, `codex_call`; neither call passes a model name.

| Role | Sandbox | Extra args |
|---|---|---|
| sweep | `workspace-write` | `-c sandbox_workspace_write.network_access=true` |
| fix | `workspace-write` | none |
| diagnose, audit-spec, review | `read-only` | none |

`codex_call` adds the evidence directory as a writable root for the sweep only, so it can write its screenshots and call run.sh's verbs; a fix worker writes the worktree alone and cannot touch `state.sh`, `run.sh` or `findings.md`. `workspace-write` blocks network by default, localhost included: without the override a sweep reports a connection error that reads like a broken app. From a Codex run, the reviewer is `claude_call`.

**Rungs 2 and 3 — subagents.** The same prompt file and contract, sent through the session's subagent tool: in Claude Code the Agent tool, with `model` set to a different model for rung 2; in Codex its native agent tools, when the session has them. Rung 3 is a fresh subagent that never saw the artifact being written. The run writes the subagent's reply to the reply file verbatim.

**Rung 4 — self-review.** A separate step after the artifact is written: re-read the prompt and the artifact from disk, fill the contract as if someone else wrote it, and write it to the reply file.

**Falling through.** A CLI that is missing, fails to authenticate, or times out sends that artifact to the next rung, logged. After two consecutive failures of one rung, the run uses the next rung for the rest of the run.

**Workers** (sweep, fix, diagnose) are the run itself or one agent at a time through the same calls; with a browser MCP server the sweep stays in the session (section 3). Workers never stage or commit.

## 6. Sweep

The sweep prompt carries the style preamble, the app URL, how to reach the browser (for a CLI worker, the run.sh path and its `b_nav`, `b_eval`, `b_shot`, `b_logs` verbs; with an MCP server the sweep runs in the session), the phase's acceptance rows verbatim, the sentinel, the scope fence, and this contract, which is the whole response:

```
PHASE: <n> attempt <a>
IDENTITY: pass | fail — <cwd observed> / <sentinel found?>
ACCEPTANCE:
  - <row>: landed | not-landed | unverified — <selector or text observed> — <screenshot path>
REGRESSIONS: <console errors, 4xx/5xx, broken route> | none
GAPS: <in-scope defect> — <file:line best guess> — <command reproducing that one case>
OUT-OF-SCOPE: <seen, left alone> | none
BLOCKED: <the single question that needs a human> | none
```

The prompt makes the sweep write its evidence, not describe it: a screenshot per row (`p<N>-a<ATTEMPT>-<row>.png` in `$RUN_DIR`) and the raw console and network capture (`p<N>-a<ATTEMPT>-console.log`), every sweep, pass or fail, never overwriting an earlier attempt's. A console error paraphrased into the verdict cannot be debugged three days later.

## 7. Findings log — append after every sweep

The per-sweep files answer "what happened in phase 3"; the findings log answers "what did the run find", which is the question asked the next morning.

```bash
# run.sh: the findings log
log_sweep() {       # log_sweep <phase name>: this attempt's sweep reply, into the log
  local sweep="$RUN_DIR/sweep-p$N-a$ATTEMPT.md"
  [ -s "$sweep" ] || _die "no sweep reply at $sweep"
  { echo "## P$N attempt $ATTEMPT — ${1:-phase $N}"
    echo "identity: $(sed -n 's/^IDENTITY: //p' "$sweep")"
    sed -n '/^ACCEPTANCE:/,$p' "$sweep"
    echo "evidence: $RUN_DIR/p$N-a$ATTEMPT-*"
    echo; } >> "$FINDINGS"
}
log_append() {      # log_append <file>: a receipt, verdict block or note, verbatim
  [ -s "$1" ] || _die "nothing to append: $1"
  { cat "$1"; echo; } >> "$FINDINGS"
}
```

Append passes and void sweeps too; a void entry reads `identity: fail` and says why nothing was verified. Red receipts, spec-audit and diff-review blocks (each with its `REVIEWER:` line), mechanical spec fixes and escalations go in through `log_append`. The `OUT-OF-SCOPE` lines exist nowhere else.

## 8. Fix and diagnosis

The fix prompt carries the sweep's `GAPS` lines verbatim, the scope fence, and the verification command. It names this phase's spec files and every earlier run spec as **read-only**, and says to answer "spec appears to misencode the requirement" rather than adjust an assertion. Without that sentence an agent told to make a test pass eventually edits the test.

Before any commit, check that no spec moved. The guard returns non-zero on a violation; one that prints a warning and exits 0 is not a guard.

```bash
# run.sh: the spec guard
assert_specs_untouched() {
  local -a changed=()
  local f c p
  _need_worktree
  while IFS= read -r -d '' f; do changed+=("$f"); done < <(
    { git -C "$WORKTREE" diff --no-renames --name-only -z          # a renamed spec lists both paths
      git -C "$WORKTREE" diff --cached --no-renames --name-only -z
      git -C "$WORKTREE" ls-files -z --others --exclude-standard; } )  # untracked count too
  for c in "${changed[@]}"; do
    for p in "${RUN_SPEC_FILES[@]}"; do
      [ "$c" = "$p" ] && { echo "STOP: fix modified spec $c" >&2; return 1; }
    done
  done
  return 0
}
```

Exact comparison, not `grep`: a substring match lets `a.spec.ts` match `not-a.spec.ts.bak`. `RUN_SPEC_FILES` holds repo-relative paths, as git prints them, recorded by `spec_committed`.

When attempt 3 fails, a diagnosis replaces the third fix: the same inputs plus every earlier sweep and fix reply, `read-only`, at `effort_for diagnose`. It returns a root cause with evidence, whether the plan's premise still holds, and what stays red. It writes no code; the phase stops red with that entry in the findings log.

## 9. Gate tiers

```
spec written → spec audit (section 12) → spec commit, spec_committed (red, receipt logged)
   ↓
build → identity gate → specs + sweep → green, rows landed, no in-scope regressions?
                              │         → diff review (section 13) → commit, phase_done
                              ↓ no
                           fix (implementation only) → next_attempt → back to build
```

**Cap: three attempts per phase.** An attempt is one build, identity gate and sweep. Attempts 1 and 2 end, on a failed sweep or a diff review's `fix`, in a fix and `next_attempt`; attempt 3 ends, on failure, in the diagnosis (section 8) and the phase stops red. That is three sweeps and at most two fixes. One agent at a time, never two phases in parallel.

**`PHASE_IMPACTED` is resolved during the spec session, not at run time**, with the repo's own dependency or test-selection tooling (`vitest related`, `jest --findRelatedTests`, a build-graph query), written into the brief as paths for `set_impacted`. Where no such tooling exists, a grep for importers is the last resort: it misses aliases, re-exports and dynamic imports, so the brief says it fell back and widens the phase tier.

```bash
# run.sh: gates
# BEFORE implementing, behavior-red specs only. A non-zero exit is NOT proof of red:
# a missing runner, syntax error, timeout, crash or zero tests executed all exit non-zero.
gate_spec_red() {   # gate_spec_red <spec file> <test name as the runner prints it> <expected signature>
  local spec="$1" name="$2" want="$3" rc out
  out="$RUN_DIR/spec-red-p$N-$(basename "$spec").txt"
  _adapter 600 "$TEST_ONE" "$spec" "$name" >"$out" 2>&1; rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "PRE-IMPLEMENTATION PASS: classify (already met, wrong assertion, never ran). See $out" >&2
    return 2
  fi
  grep -qE -- "$FAIL_PATTERN" "$out" || {
    echo "INFRASTRUCTURE FAILURE, not red: no test failure reported. See $out" >&2; return 3; }
  grep -qF -- "$name" "$out" || {
    echo "INFRASTRUCTURE FAILURE: named test '$name' never ran. See $out" >&2; return 3; }
  grep -qF -- "$want" "$out" || {
    echo "RED FOR THE WRONG REASON: '$want' absent. See $out" >&2; return 4; }
  echo "red as predicted; receipt: $(git -C "$WORKTREE" rev-parse HEAD) / $out"
}
test_one() { _adapter 600 "$TEST_ONE" "$@"; }   # test_one <spec> <test name>: one failing case

# Never call the runner with an empty list: most runners then run the WHOLE suite.
run_tests() {
  [ "$#" -gt 0 ] || { echo "GATE ERROR: empty test list, refusing to run" >&2; return 1; }
  _adapter 900 "$TEST_FILES" "$@"
}
_typecheck() { [ -z "$TYPECHECK" ] || _adapter 600 "$TYPECHECK"; }
gate_attempt() {    # every build inside the fix loop
  run_tests "${PHASE_SPEC_FILES[@]}" && _typecheck
}
gate_phase() {      # once, when gate_attempt goes green: every run spec so far, plus impacted
  local -a uniq=(); local f
  for f in "${RUN_SPEC_FILES[@]}" "${PHASE_IMPACTED[@]}"; do
    _has "$f" "${uniq[@]}" || uniq+=("$f")
  done
  run_tests "${uniq[@]}" && _typecheck
}
gate_wave() {       # the union of this wave's phase tiers, built by phase_done
  local a
  run_tests "${WAVE_TESTS[@]}" || return 1
  for a in "$TYPECHECK" "$LINT" "$BUILD" "$DIST_CHECK"; do
    [ -z "$a" ] || _adapter 900 "$a" || return 1
  done
}
gate_full() {       # gate_full <why>: minutes, so the reason is logged first
  [ -n "$1" ] || _die "usage: gate_full <why>"
  echo "## ESCALATION P$N attempt $ATTEMPT — $1" >> "$FINDINGS"
  _adapter 1800 "$FULL_SUITE"
}
```

A sweep's `GAPS` line carries the failing case's own command. Re-run **that** (`test_one <spec> <test name>`), never the suite containing it.

The full suite runs in exactly two situations, each logged by `gate_full` and named in the report:

1. **Phase 0**, once, to capture the baseline. Without it no later number is interpretable.
2. **When a failure will not localize**: the phase tier is green while the sweep still reports a regression, or the fix loop cannot find where a failure starts.

| Tier | Green means |
|---|---|
| spec-red | each of the phase's specs fails for the reason its requirement predicts, recorded before any implementation |
| attempt | the phase's spec files pass, typecheck clean |
| phase | those specs, every earlier run spec and every importer's suite pass, typecheck clean |
| wave | the wave's union passes, plus lint, typecheck, build, dist check |
| escalation | the phase-0 baseline, with zero new failures and no new failing suite names |

A targeted run is never compared with a full-suite count: "215 pass, 0 fail" is not "7084 pass, 59 fail".

## 10. Heartbeat — between every phase

```bash
# run.sh: heartbeat
heartbeat() {
  local pids
  curl -sf --max-time 10 -o /dev/null "$APP_URL" || echo "STUCK: dev server down at $APP_URL"
  [ -z "$B_NAV" ] || { _browser_is_ours && browser_works; } || echo "STUCK: browser unhealthy"   # never drives a foreign browser
  echo "codex exec processes: $(pgrep -f '[c]odex exec' | wc -l | tr -d ' ') (0 between phases; a Codex run counts itself)"
  pids=$(_pids_with "--user-data-dir=$PROFILE" | tr '\n' ','); pids="${pids%,}"
  echo "browser processes: $(echo "$pids" | tr ',' '\n' | grep -c .) (a jump between phases means leaking tabs)"
  echo "browser tree: $([ -z "$pids" ] && echo 0 || ps -o rss= -p "$pids" | awk '{s+=$1} END {printf "%d", s/1024}') MB"
  if command -v memory_pressure >/dev/null 2>&1; then memory_pressure | grep -i 'free percentage'
  else free -m 2>/dev/null; fi
}
```

- **Unhealthy browser:** `ensure_browser` kills the run's own browser, waits for its port to free, and relaunches within its two-launch budget; it never stacks a second instance beside the first.
- **Browser tree over ~1.5 GB, or system free memory under 15%:** recycle between phases (`teardown`, then `ensure_dev_server` and `ensure_browser`). The identity gate re-runs anyway.
- Anything stuck is killed by its ledger PID and restarted, not waited on.

## 11. Teardown — on success, failure and abort

```bash
# run.sh: teardown
teardown() {        # kills what this run started; deletes nothing
  local f pid
  for f in "$RUN_DIR"/*.pid; do    # never *.pid.reused
    [ -e "$f" ] || continue
    _kill_ours "$(cat "$f")" || echo "skipped $f: PID $(cat "$f") is gone or no longer the run's" >&2
    rm -f "$f"
  done
  pid=$(_listener "$PORT")   # a dev server's real process is often a child of dev.pid
  if [ -n "$pid" ] && [ ! -e "$RUN_DIR/dev.pid.reused" ] && _under_worktree "$(_cwd_of "$pid")"; then
    kill "$pid" 2>/dev/null
  fi
  for pid in $(_pids_with "--user-data-dir=$PROFILE"); do kill "$pid" 2>/dev/null; done
  sleep 1
  echo "left: $(_pids_with "--user-data-dir=$PROFILE" | wc -l | tr -d ' ') browser," \
       "$(pgrep -f '[c]odex exec' | wc -l | tr -d ' ') codex exec (a Codex run counts itself)"
}
```

Kill each recorded PID that still belongs to the run (its command line carries the run's profile, or its cwd is in the worktree), so a PID the system has since reused is never killed, and remove the pid files. Then the listener on the run's port when it serves this worktree and was not reused, then whatever still carries this run's profile path as a whole argument, matched as a fixed string with a space before it and a space or the line end after, so neither `<profile>-old` nor `--flag=--user-data-dir=<profile>` is this run's. Anything reused is left alone: it belonged to something else before the run began. **Never a bare `pkill -f chrome` or `pkill -f node`**: that kills the user's own browser and unrelated work.

## 12. Spec audit — between "spec written" and "spec committed red"

The run wrote the spec, so the run doesn't say it encodes the requirement. The reviewer (section 5, role `audit-spec`, read-only) gets the style preamble, the requirement row verbatim (`CURRENT`, `EXPECTED`, authority, gate mode), the spec file path, and this contract:

```
SPEC: <path>
SUBJECT: matches | drifts — <what the assertion actually tests>
VALUE: from-EXPECTED | from-implementation | tautology — <the literal it checks>
MODE: <gate mode> validatable | not — <why>
MECHANICS: ok | <missing import, bad selector, racy wait, misused harness API>
VERDICT: commit | fix-mechanics | stop-semantic
```

`commit` → commit the spec, `spec_committed`, and `gate_spec_red`. `fix-mechanics` → correct the named mechanics only, log it, audit once more. `stop-semantic` → the spec asserts something the user did not say: a runtime stop, never a rewrite. The block goes into the findings log whichever way it lands.

## 13. Diff review — before every commit

Every commit on the run's branch is preceded by a written verdict on its diff from a reviewer that did not write it:

| Diff written by | Reviewed by |
|---|---|
| the run (a phase change, a spec, a mechanical spec fix) | the resolved reviewer, role `review`, read-only |
| a worker on the reviewer's side (a codex fix agent, say) | the run itself, against the same contract |

```bash
# run.sh: the review diff
review_diff() {     # the whole change against HEAD, new files included; prints its path
  local -a new=(); local f out="$RUN_DIR/review-p$N-a$ATTEMPT.diff"
  _need_worktree
  while IFS= read -r -d '' f; do new+=("$f"); done < <(
    git -C "$WORKTREE" ls-files -z --others --exclude-standard)
  # intent-to-add on untracked files only: they show in the diff, nothing is staged
  [ ${#new[@]} -eq 0 ] || git -C "$WORKTREE" add -N -- "${new[@]}"
  git -C "$WORKTREE" diff HEAD > "$out" && echo "$out"
}
```

The prompt carries the style preamble, the diff path, what the diff is meant to do (the sweep's `GAPS` lines, or the phase's stated change for a first implementation), the scope fence, the protected spec list, and this contract:

```
HUNKS: <n> — each: <file:lines> → <the GAP line or phase change it serves> | unexplained
SCOPE: inside | <file outside the fence>
SPECS: untouched | <spec file modified>
DEFECTS: <file:line — what breaks, and the command that shows it> | none
VERDICT: commit | fix — <the one thing to change>
```

`commit` → `assert_specs_untouched`, stage, commit through the commit skill, `phase_done` after the implementation commit. `fix` → the `DEFECTS` lines go to the fix worker as its `GAPS`, `next_attempt`, back to build. An `unexplained` hunk is a `fix`: a change nobody asked for goes back, not in. A review that produced no block did not happen.

## 14. Brief audit — at brief-writing time, before the paste line

Not part of run.sh or the brief. The session writing the brief runs it, through the first rung it has (section 5), because the author of the brief is not the one that clears it. The auditor is told to find the reason the run will fail or build the wrong thing, not to confirm the brief. With codex, every path written out:

```sh
mkdir -p "<evidence dir>"
codex exec -C "<source repo>" --add-dir "<brief's folder>" --add-dir "<source plan's folder>" \
  -c model_reasoning_effort=high --sandbox read-only \
  --output-last-message "<evidence dir>/audit-brief.md" - < "<evidence dir>/audit-brief-prompt.md"
```

From Codex, `claude -p --permission-mode plan --effort high` with `--add-dir` for each of those folders, run from the source repo, the prompt on stdin and the reply redirected to `audit-brief.md`. The prompt carries the style preamble, the brief and source plan paths, the instruction to argue against the brief, and this contract:

```
REQUIREMENTS: <n> rows — each: EXPECTED verbatim | paraphrased | inferred; authority named | missing
MODES: every gate mode validatable | <row> not — <why>
GROUND TRUTH: paths, branch, base, install, runner all exist | <what does not>
PASTE LINE: standalone | <placeholder, ~ path, unresolved symlink, missing worktree clause>
TRIGGERS: every trigger, skill and tool named is present | <what is missing>
PREMISE: the plan addresses the report | <the gap between the fix and the complaint>
UNKNOWNS: all carried | <one the plan flagged that the brief dropped>
RUN.SH: bash -n clean, placeholders resolved, init and a verb tried | <what failed>
BLOCKERS: <what must change before this ships> | none
VERDICT: ship | revise
```

`ship` → print the paste line. `revise` → fix the named blockers and audit once more. A second `revise` goes back to the user as questions, not into a third draft.

## 15. Dispatch — the last block of run.sh

```bash
# run.sh: dispatch. Keep this block last.
declare -F _die >/dev/null || { echo "run.sh is incomplete: the guards block is missing" >&2; exit 2; }
VERBS=" init resume state start_phase set_impacted spec_committed next_attempt phase_done new_wave
  with_timeout ensure_dev_server ensure_browser browser_works b_nav b_eval b_shot b_logs
  identity_cwd identity_gate effort_for codex_model claude_model codex_call claude_call
  log_sweep log_append assert_specs_untouched gate_spec_red test_one run_tests gate_attempt
  gate_phase gate_wave gate_full heartbeat teardown review_diff "
WRITERS=" init start_phase set_impacted spec_committed next_attempt phase_done new_wave "  # locked throughout
case "${1:-}" in   # slow verbs run unlocked, then merge only their own variables under the lock
  ensure_dev_server) own="PORT APP_URL" ;;
  ensure_browser)    own="CDP_PORT" ;;
  *)                 own= ;;
esac
verb="${1:-}"; [ $# -eq 0 ] || shift
# shellcheck disable=SC2086  # VERBS, WRITERS and own are word lists, split on purpose
_has "$verb" $VERBS || _die "unknown verb '$verb'. Verbs: $(echo $VERBS)"
declare -F "$verb" >/dev/null || _die "verb $verb is listed but not defined: a run.sh block is missing"
writer=
# shellcheck disable=SC2086
if _has "$verb" $WRITERS; then writer=1; mkdir -p "$RUN_DIR"; _lock; fi
_defaults
if [ "$verb" != init ]; then
  [ -f "$RUN_DIR/state.sh" ] || _die "no state in $RUN_DIR: run init first"
  # shellcheck source=/dev/null
  source "$RUN_DIR/state.sh"
fi
"$verb" "$@"; rc=$?
# shellcheck disable=SC2086
if [ -n "$own" ]; then   # reload what every other call saved meanwhile, then set this verb's own variables
  writer=1; kept=$(declare -p $own)
  # shellcheck source=/dev/null
  _lock; source "$RUN_DIR/state.sh"; eval "$kept"
fi
[ -z "$writer" ] || _save || _die "could not save state to $RUN_DIR/state.sh: $verb's change did not persist"
exit "$rc"
```

A writer verb holds the lock from load to save, so parallel calls queue rather than lose updates, and the kernel drops the lock when the call exits, however it exits. `ensure_dev_server` and `ensure_browser` wait on servers and browsers for minutes, so they run unlocked, then take the lock, reload what every other call saved meanwhile, each other's included, and set only their own variables (`PORT` and `APP_URL`; `CDP_PORT`) before saving. A slow verb whose lock wait times out after it started a server or browser kills that process, says so, and dies, so nothing runs unrecorded. Every other verb reads `state.sh` without the lock: `_save` replaces it by an atomic rename, so a reader sees the old file or the new one, and a reader in a sandbox that can't write the evidence directory still works. A writer that cannot open the lock dies at once with the real error. A verb that fails through `_die` exits before `_save`, so a refused change never lands half-made, and a save that fails fails the verb.
