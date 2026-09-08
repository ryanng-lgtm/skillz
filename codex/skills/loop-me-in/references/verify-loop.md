# Codex verification loop

Read when resolving a runnable brief. Generate and validate concrete commands for the
target stack, then embed them in the brief. This reference is independent of Claude's
verification recipes; do not import its launch commands or package-manager defaults.

## Harness and identity

| Target | Resolve during preparation |
| --- | --- |
| Web UI | Available chrome-devtools skill/tool, exact executable and supported CLI, app URL and isolated browser profile |
| OM Chat web GUI | Available testing-harness skill and its implemented modes; verify build provenance before sweeping |
| Native app | Native automation/build identity and required device access; a web export is not native verification |
| Backend, CLI, library | Exact command, expected value and executable/package provenance |

Read the selected harness's instructions and help before generating commands. Name a
sentinel per phase, such as a test ID, route, label, version or artifact hash. A web
identity check must assert both that the serving process's cwd is the worktree or a
descendant and that the sentinel is present in the served output. Assert the returned
value: a browser evaluation that prints `false` may still exit zero.

If a phase has no browser-observable change, use an appropriate command identity gate.
If browser evidence is required but its sentinel or process check fails, that attempt
is unverified. Rebuild and re-gate within the phase cap; do not label a stale build
“not landed” or record its passing tests as evidence for this worktree.

## Commands, time limits and gate selection

Use the repo's actual install and script commands. Each adapter must name its working
directory, argument handling, expected success result, output path and timeout. Missing
optional adapters are explicitly omitted. Preserve mandatory repository gates at the
boundary where the repository requires them, including full-suite completion checks.

Use Bash explicitly for generated helpers that rely on Bash arrays. Keep file lists as
arrays expanded with `"${files[@]}"`; never pass a space-joined list. Reject empty test
selections and zero-tests-executed results. Resolve impacted tests with the repository's
dependency tools; record a wider gate when the affected set cannot be bounded reliably.

Resolve an available timeout facility instead of assuming GNU `timeout` on macOS.
Every browser command, build, install, test and external agent call has a time limit.
If a helper is necessary, include its complete definition and validate both success
and timeout behavior before handing it off. Record the timeout exit classification;
it is infrastructure failure, never a predicted assertion failure. Timeouts must also
trigger cleanup of the run's owned child processes; terminating only a parent is not
enough. Do not hide failures with `|| true` in acceptance gates.

Persist the phase, attempt, spec receipt and worktree/base identity before long steps.
After interruption, inspect the checkpoint, Git state and process identities before
continuing. A restart does not reset phase attempts or the browser launch counter.

## Process ownership and recovery

Resolve an ordered, finite set of permissible app and CDP ports before execution.
When a foreign process holds a port, leave it running and choose the next permitted
port. Update the start command, app URL, CDP endpoint and identity gate consistently.
If callbacks or configuration require a fixed occupied port and no safe alternative
exists, record an environment blocker for the affected phase.

At spawn, record PID, start time, command identity, claimed port, profile/worktree and
ownership in the process ledger. Reuse only a server whose cwd is within this worktree
or a browser whose profile exactly matches this run. Mark reused processes separately;
they are excluded from teardown and destructive recovery.

One dev server and one browser are reused across phases. Browser state and profile live
under the run's evidence directory. Use one tab. Before the first sweep and between
phases, prove browser health by navigating, evaluating a known result, and writing a
new nonempty screenshot. An old screenshot or an answering debugging port is insufficient.

Persist a browser launch counter. Two launches total, including pressure-related
restarts, are allowed for the whole run. After exhaustion, stop browser attempts and
mark browser-dependent phases unverified; independent command phases can continue.
Never replace required UI evidence with command-only success.

Between phases check the app, browser smoke test, owned outstanding workers/stopped
jobs, browser-tree RSS and system free memory. At roughly 1.5 GB browser RSS or under
15% system free memory, recover only owned processes and only within the launch budget.
An unhealthy reused process is a blocker or requires an isolated replacement; permission
to reuse does not grant permission to kill it.

Teardown runs on success, failure and abort. Revalidate each owned PID's start time and
command identity before killing it, to avoid PID reuse. Reap its verified descendants;
any additional matching must be restricted to this run's exact owned profile and must
not affect reused processes. Confirm no owned processes survived. Never delete evidence.

## Sweep, correction and diagnosis

The orchestrator can run each role inline or use available native agent tools. Reuse
the same worker for later tasks. Count all agents over the whole task, respect the
environment's lower cap, and run only one sweep/fix worker at once. Do not turn every
phase or retry into a new `codex exec` process. If external CLI execution is needed,
check its installed help, model/effort support, sandbox and evidence-write access before
embedding exact commands; do not assume a model, network policy or writable vault.

Choose effort for the role: mechanical observation can begin low, behavioral checks
medium, and shared state or async fixes high when supported. Increase effort after
failure; diagnosis uses the strongest appropriate supported effort. Internal prompts
may be compressed, but persisted findings and evidence verdicts use normal prose.

A sweep receives the acceptance rows verbatim, build sentinel, surface/command,
scope fence, evidence paths and exact reproduction command. It returns:

```text
PHASE: <phase and attempt>
IDENTITY: pass | fail — observed process/artifact and sentinel
ACCEPTANCE: one verdict per row: landed | not-landed | unverified, with evidence
REGRESSIONS: observed in-scope regressions, or none
GAPS: defect, likely file/line, exact command for reproducing that case
OUT-OF-SCOPE: findings left untouched, or none
BLOCKED: unresolved decision or unavailable prerequisite, or none
```

Save screenshots and raw console/network or command output per phase **and attempt**,
without overwriting previous evidence. Append findings after every attempt, including
passes and failed identity checks. Record receipts, baseline comparisons, actual
commands, acceptance verdicts, regressions, scope gaps, blockers and artifact paths.

Fix work is limited to implementation files; protect current and earlier acceptance
specs and inspect staged, unstaged and untracked changes before committing. A suspected
spec defect returns to the orchestrator for mechanical-versus-semantic classification.
Mechanical corrections get a separate logged test-only change and mode revalidation;
semantic changes require Ryan. Workers never stage or commit.

After attempt 1 fails, correct and recheck once. Attempt 3 after a second failure is
read-only diagnosis: root cause, supporting evidence, whether the plan's premise holds,
and what remains red/unverified. Two bugs of the same class trigger diagnosis immediately.
Then skip dependent phases and continue independent ones. Preserve counters across
recovery and resume. Finish only after all required gates pass; otherwise report the
unfinished work honestly and handle goal status using the target runtime's rules.
