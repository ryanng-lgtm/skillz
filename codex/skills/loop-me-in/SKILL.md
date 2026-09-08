---
name: loop-me-in
description: >-
  Turn an approved plan into a self-contained brief that a fresh Codex session can
  execute and verify unattended. Resolve missing expected results, execution paths,
  acceptance gates, retry caps, and reporting before handing it off.
  Trigger: $loop-me-in [path].
---

# loop-me-in — a plan in, a runnable Codex brief out

The brief must survive an empty session: copy the requirements and constraints,
resolve the environment, and define observable completion. The execution loop
implements and verifies against that contract without asking Ryan to judge each phase.

This is the independent Codex version. Do not edit the Claude skill or import its
launch commands. Generating a brief does not start a goal, create a worktree, install
dependencies, implement changes, commit, or post messages.

## Prepare the handoff

1. Read the complete source plan and its specification authorities, including risks
   and unknowns. If multiple copies exist, diff them and use the copy Ryan named.
   Carry settled decisions forward; ask only for missing or conflicting requirements.
   Clean up an unsettled plan before converting it; a small direct edit needs no loop.
2. Resolve each source repo, applicable instructions, default branch from
   `origin/HEAD`, future worktree path, feature branch, install command, runner, and
   gates. Check the paths and commands using read-only inspection. Record the branch
   freshness check the execution session must perform and its base-SHA receipt.
   Name ignored configuration and dependencies the new worktree must acquire.
   Dependence on uncommitted source-checkout work blocks the brief until resolved.
   Do not run an install as a probe; if its viability remains unknown, settle the
   prerequisite now. An actual install failure during execution stops that repo.
3. Record every requirement as `CURRENT`, `EXPECTED`, authority, and gate mode.
   Probe current behavior cheaply; save a live capture when timing, visuals, or a
   disagreement with the report makes the probe insufficient. Probes and captures
   establish only `CURRENT`, never the desired result.
4. Copy Ryan's stated `EXPECTED` verbatim, or copy the approved product requirement,
   API contract, or compatibility invariant and name its authority. An expectation
   already settled in this session needs no reconfirmation. Ask for any remaining
   desired delta before shipping the brief; never derive it from the implementation.
5. Map requirements to spec files and phases, many-to-many. Freeze each assertion's
   subject and expected value. Resolve harness mechanics from fixtures, helpers and
   public interfaces. The execution session writes and validates the specs at the
   start of each phase; the brief carries expected signatures, not invented receipts.
6. Read [references/verify-loop.md](references/verify-loop.md). Resolve the appropriate
   harness, build identity, commands, evidence, and recovery paths. Copy the resolved
   operational instructions into the brief; a reference link alone is insufficient.
7. Resolve reporting from Ryan's existing instructions. If no destination or posting
   authorization exists, ask once for the destination and whether the run should post.
   Do not infer a room from the subject or treat a server grant as user authorization.
   Check available tools and grants read-only; record a canonical room/topic resource.
   A local report is sufficient when posting is declined or explicitly optional.
8. Select the execution trigger below. Write the brief and return its real path plus
   the complete paste line, with no unresolved placeholders.

## Files and placement

Resolve `~/.codex/plans` and use today's `YYYY-MM-DD` directory beneath it. Write
`<source-name>-run.md` and a sibling `<source-name>-run-evidence/` directory there.
Trust this symlink: Ryan has already identified the live Obsidian vault. The nested
`Obsidian/Obsidian/` copy is not a destination, even if the source plan came from it.
Ask only if the configured symlink is missing or broken and the destination cannot
be established from the session. Do not reopen the settled duplicate-vault question.

Resolve and quote all paths in the paste line and generated commands; the vault path
contains spaces. Briefs, design documents, captures, and findings stay in the vault
and are never committed. Executable acceptance tests and their fixtures belong in
the implementation repo and may be committed. Do not overwrite an existing brief or
evidence directory belonging to another run; choose a distinct name.

## Acceptance gates

Choose the mode during preparation. Each phase may have several specs and modes.

| Mode | Before implementation | Completion evidence |
| --- | --- | --- |
| `behavior-red` | Named test executes and fails at the predicted assertion | That assertion passes |
| `green-characterization` | Tests pass on the original behavior | They still pass after the refactor |
| `compile-red` | Build fails because the named API surface is absent | That API compiles and its behavior checks pass |
| `benchmark-delta` | Baseline, repetitions, tolerance and noise handling recorded | Measured change meets the agreed target |
| `structural-invariant` | Boundary or packaging invariant holds | It still holds after the change |
| `discovery` | A bounded question and required evidence are defined | Report answers the question; no implementation-complete claim |

Only `behavior-red` requires an assertion failure. Missing dependencies, syntax
errors, crashes, timeouts, or zero tests executed are infrastructure failures.
A pre-implementation pass under `behavior-red` must be classified: already satisfied,
wrong assertion, or test never ran. Report and omit already-satisfied work.

Record a validation receipt per spec: base SHA, spec SHA (or content hash until its
commit), exact command, named test, exit classification, expected and observed result,
and raw output path. Validate before implementation. Separate spec and implementation
commits are the default when the repo permits intentionally failing commits; otherwise
commit the pair together and retain the pre-implementation receipt as proof.

The fix loop changes implementation. A mechanical spec defect (selector, fixture,
mock, or wait) may receive a logged test-only correction that preserves the assertion's
subject and expected value, followed by mode revalidation. A semantic error requires
Ryan's decision. Never weaken, skip, delete, or loosen assertions to obtain a pass.

## Execution trigger

Use Codex's native goal mechanism for a bounded implementation objective with several
checkpoints or retries. Confirm the target supports `/goal` or exposes native goal
tools; a built-in command need not appear in the skill list. Current documentation:
[Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals).

The generated paste line begins `/goal` when that command is supported. If only native
goal tools are available, begin with “Set a goal to…” and the same complete contract.
Do not assume Claude's `/loop` or `/schedule` exists in Codex. If goals are unavailable,
identify that before promising unattended continuation; ordinary execution is suitable
only when it can finish within a normal task. Do not silently change feature settings.

Name one bounded objective, completion gates, phase count and retry cap. Bundled fixes
must form an explicitly bounded deliverable with independent/dependent phases listed.
Set a token budget only when Ryan requests one. Reaching a cap leaves unfinished work
unfinished; it is not a reason to mark the goal complete. Follow the runtime's native
goal status and pause rules, and preserve enough checkpoint state to resume safely.

For work that must outlive this machine, first resolve an available remote execution
or scheduling mechanism and its access to repos, credentials, and evidence. A cloud
run cannot assume access to this Mac's vault, browser, Keychain, or devices. Local
overnight work requires the machine and execution environment to remain available.

The paste line must contain, in full:

- Objective, success condition, phase/retry ceiling, and instruction to read the brief.
- Resolved, quoted absolute paths for the brief, source plan, and evidence directory.
- “Land every change in a new git worktree on a new feature branch cut from a freshly
  fetched default branch; never commit to the default branch, and never implement in
  Ryan's own checkout. Use the exact paths and branch names in the brief.”

The execution session creates one worktree and branch per repo, once, before phase 1.
Fetch the named default branch, record the base SHA, and cut from that remote-tracking
ref without changing Ryan's checkout. On resume, validate and reuse the recorded
worktree and branch. Never create a worktree per phase.

## Verification and retry policy

Resolve `START`, `TEST_ONE`, `TEST_IMPACTED`, `TYPECHECK`, `LINT`, `BUILD`,
`DIST_CHECK`, and `FULL_TEST` per repo. Explicitly omit nonexistent adapters and state
why; do not inherit another project's package manager or test commands.

| Boundary | Gates |
| --- | --- |
| Phase 0 | Full-suite baseline, known flakes, tool/environment checks |
| Attempt | This phase's spec files and typecheck |
| Phase | Current and all earlier run specs, plus affected consumers' tests |
| Wave | Union of the wave's phase gates, lint, typecheck, build, applicable dist check |
| Completion | Every acceptance gate plus all mandatory repository completion checks |

Use the repo's dependency/test-selection tooling for affected consumers, including
transitive reach where applicable. Record limitations; uncertain impact can justify
a wider gate. Compare each targeted set with its own baseline, never the full-suite
test count. An empty selection or zero executed tests cannot pass a test gate.

Full suites run for the baseline, a logged escalation when a failure cannot localize,
and whenever repository instructions require them. In OpenFloor, completion requires
`pnpm run lint`, `pnpm run typecheck`, `pnpm test`, and `pnpm run export:smoke`.
Native lifecycle, push, deep links, secure storage and background behavior additionally
need real iOS and Android device evidence before a beta gate closes. Browser or
simulator evidence cannot replace that. Resolve device access before promising that
gate; an explicitly narrower implementation milestone must retain it as outstanding.

Each phase gets at most three verification attempts. After a first failed attempt,
make one scoped correction and recheck. After a second failure, attempt 3 is read-only
root-cause diagnosis, not another patch; leave that phase red/unverified. Two bugs of
the same class trigger diagnosis immediately. Continue only independent phases;
skip dependent ones with the reason recorded. No fourth patch and no widened scope.

Infrastructure recovery has its own bounds and must not silently reset counters.
Use a recorded list of alternate ports instead of killing a foreign listener; update
the URL and identity checks together. Allow two browser launches total for the whole
run, including restarts. If neither produces a healthy browser, mark browser-dependent
phases unverified and continue only gates/phases that can stand independently. Passing
command tests does not substitute for required browser evidence.

## Agents, reporting and authority

Prefer native Codex agent tools when available; otherwise perform sweep, fix and
diagnosis roles sequentially in the main session. Reuse agents rather than spawning
one per phase or retry. At most five agents including the orchestrator across the
whole task, or the environment's lower cap; one sweep/fix worker active at a time.
Workers do not stage or commit. The orchestrator reviews the diff, stages its scoped
changes, and follows `$commit`. Select available models and supported effort levels
for the role; never assume a global model/config value or require a hard-coded model.

Compress internal reasoning and agent prompts only. Findings, persisted evidence
verdicts, user updates, completion posts, code, comments and commits stay normal prose.
Preserve exact errors, selectors, paths, numbers and units.

Carry existing authorization into the brief. Do not ask again for an approved action.
The skill itself grants no permission to post, push, merge, publish or deploy. Record
which actions Ryan authorized and where the run must stop for new authority. Own-branch
implementation commits are part of an authorized implementation run; every commit
uses `$commit`. Never treat preparation alone as execution authorization.

When OM Chat reporting is authorized, use available `room_*`/`doc_*` tools as the bot,
with the confirmed canonical room/topic and posting capability. Do not substitute a
CLI command that posts as Ryan. Missing required reporting access is settled before
handoff; a runtime posting failure writes the report locally and is recorded.

Build the completion post from `$mr-markdown` over this run's commits, not the entire
branch history. Use a bold `<thing> now <behavior>` title for verified work, with at
most four bullets, prioritizing unresolved failures, gaps and decisions. A blocked run
uses an honest blocked title and still reports when authorized. Bundled fixes get one
final post (100 words maximum); a large feature gets meaningful completed-wave posts
(40 words maximum). Count before posting; do not pad to a minimum. Include the findings
path and only claims supported by completed gates. A canary can report and continue
without waiting for human review; stop only on its stated tripwire.

## Required brief sections

Write these in order, copying concrete facts and commands rather than linking context:

1. **Title and paste line** — complete launch instruction and first worktree action.
2. **Requirements** — CURRENT evidence, verbatim EXPECTED, authority and gate mode.
3. **Traceability matrix** — requirements ↔ spec files ↔ phases, expected validation
   signatures, frozen semantics and mechanical-correction rules.
4. **Ground truth** — source/worktree paths, branches, default-branch refresh, base SHA
   receipt, existing commits, install/config preparation, explicit scope exclusions.
5. **Environment traps** — known flakes, registry constraints, generated files,
   overlapping phase files and ordering, required versioned docs and device access.
6. **Verification loop** — resolved adapters, harness, identity gates, time boxes,
   agent/inline roles, attempt limits and recovery policy from the local reference.
7. **Process ledger** — process, port, PID, start time, identity, owned/reused, plus
   heartbeat and teardown instructions for success, failure and abort.
8. **Findings log** — absolute evidence path and append procedure after every attempt,
   including passes, invalid identity checks, receipts and out-of-scope findings.
9. **Phases** — dependency order, requirement/spec sets, implementation scope, files,
   build sentinel, acceptance rows, commands and mode-appropriate done condition.
10. **Gates** — exact tier commands, baseline counts/timings, mandatory completion and
    any explicitly deferred gates; missing evidence never counts as green.
11. **Open questions** — every remaining unknown, classified as prerequisite or report.
12. **Completion report** — local findings path, authorized destinations/cadence and caps.
13. **Commit and authority rules** — carried-forward permissions and scoped `$commit`.
14. **Stop and recovery conditions** — preparation blockers, runtime phase failures,
    dependent-phase skips, whole-run blockers, cleanup and goal/checkpoint handling.

Before returning the brief, walk each requirement through its mode, phase, command and
evidence. Check for unspecified expectations, unsupported commands, missing authority,
unresolved placeholders, contradictory recovery rules and unbounded retries. Preparation
blockers prevent a runnable handoff; runtime findings must state what remains unfinished.
New environment traps discovered during execution are appended to the findings and
brief so a resumed run does not rediscover them.
