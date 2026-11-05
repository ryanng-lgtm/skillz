---
name: dev-loop
description: >-
  Use when an approved fix plan, spec or design doc has to become a brief a
  fresh session can run unattended and prove its own changes landed, or when
  the last unattended run kept pulling the user back in or went green having
  fixed something next to the actual complaint. Not for a plan still under
  discussion (clean it up first, e.g. with the demuddy skill) or a one-line
  change. Trigger: /dev-loop [path], $dev-loop [path], "make this runnable",
  "turn this plan into a loop", "so I can paste it and let it rip".
---

# dev-loop — a plan in, a self-driving brief out

## Overview

A plan is written for a reader who already has the context. A runnable brief is written for a session that has none: fresh window, no transcript, no memory of which worktree, which trap, which decision was already settled. This skill writes that brief; it does not run it.

**Core principle: the brief must survive being pasted into an empty session, and close its own loop there.** Everything the plan leaves implicit (the repo, the branch, the environment trap that eats an hour) goes on the page. The run builds, drives the real product, decides for itself whether each change landed, fixes what it finds and re-checks, until green or a stated cap. The user is not the verification step.

**Requirements are elicited, never inferred.** A plan describes a change; only the user can say what the change is *for*. A run can be green on every gate and have built the wrong thing, and nothing downstream detects that. So every requirement carries two separate fields:

| Field | Source | Answers |
|---|---|---|
| `CURRENT` | probe output, live capture, reproduction steps | what it does now |
| `EXPECTED` | the user's decision, an approved product requirement, an API contract, a compatibility invariant | what it must do instead |

A probe or a capture is evidence of the present, never an oracle: treat it as the expected result and the bug becomes the specification. `EXPECTED` names its authority, and "the probe showed X" is not one.

**Acceptance criteria are executable, and their meaning is locked before the code is read.** Requirements become committed spec files derived from `EXPECTED`, not from the implementation that will satisfy them. A failing spec is a bad implementation.

**A finished brief has exactly three human touchpoints:**

1. **Specification**, before anything runs: the requirements, the expected result of each, a live capture where words were not enough. Every question this skill asks belongs here, a second brief-audit `revise` included. It is the largest touchpoint, and it buys out every later "does this look right?".
2. **A blocking decision** the spec session did not settle.
3. **Deployment**: the push, merge, cherry-pick or release.

Everything between is the run's job, commits on its own branch included. A brief that ends with "confirm it looks right" has been reformatted, not converted.

## Settings

Two lines under `## Skill settings` in the user's global instructions (`~/.claude/CLAUDE.md` in Claude Code, `~/.codex/AGENTS.md` in Codex):

- `- Plans folder: <path>`: where briefs and their evidence go.
- `- Dev-loop reports: <destination>`: where the run posts its completion report. Any channel the session can post to: a chat channel through an MCP server, an issue or MR thread, a file.

Read both at the start of step 1, and ask then for any that is missing, offering to add the line: probes and captures write to the evidence directory from step 2 on. With no `Dev-loop reports` answer, the findings log is the report. Never fall back to a built-in folder or channel. Expand a leading `~` to `$HOME`, resolve symlinks, and quote every path in commands, since these folders may contain spaces.

## Procedure

1. **Read the settings, then the whole plan**, including the sections that aren't instructions, and anything it cites as spec-of-record. Mine the risks, unknowns and open questions hardest: they hold no steps to transcribe, so briefs drop them, and they are where "does this fix even address the report?" lives. If the plan exists in more than one copy (an older draft, a pre-review version), diff them, build from the one the user names, and say in the brief how to recognise a stale one.

2. **Resolve the environment; don't assume it.** Before any spec work, establish and check for every repo the plan touches: the source repo path; the worktree path the run will create and the feature branch it will cut there; the base branch, read from `origin/HEAD`; the install command known to work; the test runner and how it names spec files; and the stack's adapters by name (`START`, `TEST_FILES`, `TEST_ONE`, `FULL_SUITE`, `TYPECHECK`, `LINT`, `BUILD`, `DIST_CHECK`). A repo without one omits that gate explicitly rather than inheriting another project's command. A stale path is the most common way these runs die.
   - **Specify the worktree; never create it.** This skill runs no `git worktree` command. Name the exact path, so every command and evidence path in the brief is absolute before the worktree exists, and confirm path and branch in the step 3 batch with the proposed value as the recommended option.
   - **An install is not a safe no-op.** Against a private registry a bare install can re-resolve a package and break the tree. Name the command known to work; a failed install stops the run.
   - **A new worktree has nothing git doesn't track**: dependencies, build caches, `.env` and other ignored files. Name what must be installed or copied before the first gate. A plan that depends on uncommitted work in the user's checkout is a blocker now, not a discovery at 3am.

3. **Lock the acceptance oracle for every requirement. Ask; never assume.** As soon as the environment is resolved and the probes have run, work the ladder in **Establishing expected results** until each requirement has a `CURRENT`, an `EXPECTED` with a named authority, and a gate mode (**Spec-first**). Ask through the agent's interactive question tool (`AskUserQuestion` in Claude Code): up to four questions per call, one decision per question, the recommended answer first and marked `(Recommended)`, each option's consequence in its description. Without such a tool, ask one decision per message, recommended answer first. Never ask as a numbered list in prose: it makes the user do the bookkeeping, and an unanswered item silently becomes an assumption. The same batches carry the worktree path and branch.

4. **Plan the phases and specs; the run writes the specs.** Order phases by dependency: a phase comes after every phase whose output it uses (the API field before the column that displays it), and the brief marks which phases are independent, since those are what the run moves on to when one goes red. Group them into waves, the plan's milestones (a small plan is one wave). Map requirements to spec files and phases, many-to-many. Per spec, record its gate mode and *expected* failure signature. The run writes, validates and commits each spec at the start of its phase; the brief carries the plan, never spec text or invented output.

5. **Harvest the traps.** Every "don't do X, it breaks Y" you know: package managers that 404, files to regenerate rather than hand-merge, harnesses with sharp edges, suites that run out of memory, known flakes by name. A trap costs a line here and an hour there.

6. **Design the verify loop around the specs.** Read `references/verify-loop.md` and copy its `run.sh` into the brief, resolved: the run never reads this skill, and runs every helper as `bash "<evidence dir>/run.sh" <verb>`. Pick the harness, resolve the surface (start command, port, URL), and per phase name its spec files and the sentinel proving the build under test is this one. A requirement that can't be a unit spec (a visual, a layout, a live surface) gets a *scripted* assertion, a committed browser script or a command with an expected value, never sweep prose. Resolve which reviewer the run will have (**Reviewers**), and confirm every tool, skill and trigger the brief names is present in this session.

7. **Resolve where it reports**: the `Dev-loop reports` setting, else the user's step 1 answer; never infer a channel from the plan's subject. Confirm now that the session can post there (tool present, permission granted, thread or topic exists). A missing grant stalls the run at 3am waiting for consent.

8. **Pick the trigger** (**Choosing the trigger**).

9. **Write the brief** to `<Plans folder>/YYYY-MM-DD/<source-name>-run.md`, with its evidence directory `<source-name>-run-evidence/` beside it, creating the dated folder first. Never into a repo, and never inferred from where the source plan sits. Report the resolved real path, so a wrong target is caught at once.

10. **Have the reviewer audit the brief** (`references/verify-loop.md`, section 14), writing `audit-brief.md` into the evidence directory. `revise` means fix the named blockers and audit once more; a second `revise` goes back to the user as questions through the interactive question tool, not into a third draft.

11. **Report the brief's path, the reviewer that cleared it, and the paste line** in full, every path resolved and quoted. A placeholder left in the paste line is a broken deliverable.

## Establishing expected results

Assume nothing: not from the plan's title, the code, or what would be reasonable. Measure first, then ask, because confirming a finding is fast and specifying from nothing is slow.

| Step | Instrument | Establishes | Produces |
|---|---|---|---|
| 1 | **Probe**, cheapest first | `CURRENT` | A recorded observation: command and output, request and response, a screenshot of today's behaviour |
| 2 | **Live capture**, when the probe can't settle it | `CURRENT` | The user reproducing it, captured however this session can (browser trace, console and network log, screenshots), or a screen recording the user makes and hands over; saved in the evidence directory |
| 3 | **Ask the user for the desired delta** | `EXPECTED` | The result in their words (exact text, number, state; what should happen and what should *stop* happening) plus its authority |

Steps 1–2 never produce step 3. A probe showing a badge reading `0` does not say whether `0` or no badge at all is correct; that is the question for the user.

- **Escalate to a live capture rather than negotiating in prose** whenever the issue is intermittent, visual, hard to put in words, or the user's description and the probe disagree (one of them is wrong, and no spec is written until you know which). A capture is an artifact: saved in the evidence directory, named in the requirement it supports, cited by the spec.
- **"Specific enough" means encodable as an assertion with no judgement call at run time.** "The counter should be right" is not. "After deleting the last unread message, the sidebar badge shows no number at all, not 0" is.
- **`EXPECTED` goes into the brief verbatim**, in the user's words. A paraphrase is where an assumption re-enters.

**An unconfirmed `EXPECTED` is a brief-generation blocker, settled in daylight.** The brief does not ship until the user states it. It is deliberately not a runtime stop: an unattended run must never be what discovers a requirement was never specified, and a brief built on an assumed expectation produces confident, tested, committed, wrong work.

## Spec-first — the requirement is the test

1. **Lock the meaning before reading the implementation; encode it afterwards.** Frozen: the assertion's subject and expected value, taken from `EXPECTED` and the capture. Not frozen: the mechanics. Read the harness, fixtures, helpers, public interfaces and runner conventions freely, or the spec fails on a missing import. Never derive an expected value from the implementation or write an assertion that restates what the code does. The reviewer audits each spec before it is committed.
2. **Validate each spec against its gate mode before implementing.**

   | Mode | Pre-implementation validation | Use for |
   |---|---|---|
   | `behavior-red` | The named test runs and fails **at the expected assertion**, with the recorded signature | New behaviour; bug fixes with an observable wrong result |
   | `green-characterization` | The tests pass **before and after**: they pin behaviour that must not change | Refactors, moves, extractions |
   | `compile-red` | Fails to build because the named symbol, route or export does not exist yet | New API surface |
   | `benchmark-delta` | A recorded baseline, a stated tolerance, and a repeat count that survives noise | Performance work |
   | `structural-invariant` | The invariant holds now and must keep holding (lint rule, dist check, import fence) | Boundary and packaging rules |
   | `discovery` | No gate is possible yet: the phase's output *is* the information needed to specify | Spikes; ends in a report, never a claim of done |

   Only `behavior-red` requires an assertion failure. A mode that cannot be validated is a brief-generation blocker.
3. **A pre-implementation pass under `behavior-red` is a finding, not a green light**: the requirement is already met (report it, drop the phase), the spec asserts the wrong thing, or it never ran. Say which; never bank it as progress.
4. **Infrastructure failure is not red.** A missing runner, dependency or syntax error, timeout, crash, or zero tests executed gets fixed, not recorded. Red means *this named test executed and failed at the predicted assertion*.
5. **The red receipt is the proof, not the commit order.** Per spec, log the base SHA, spec SHA, exact command, exit classification, named test, and expected-vs-actual failure signature. Separate spec and implementation commits are the default; where the repo can't tolerate an intentionally red commit (CI on every push, pre-commit gates, bisect), land the pair as one commit and let the receipt carry the red evidence.
6. **A failing spec is a bad implementation.** The fix loop changes the implementation.
7. **Freeze the meaning, not the file.** A *mechanical* defect (bad selector, malformed fixture, wrong mock, racy wait) gets a logged test-only corrective commit that leaves the assertion's subject and expected value untouched, and the gate mode is re-validated. A *semantic* defect (the assertion encodes something the user didn't ask for, or satisfying it would weaken what they did) stops the run: only the user restates a requirement. Weakening, skipping, deleting or loosening an assertion is never mechanical, whatever it looks like at attempt 3.
8. **Requirements, specs and phases are many-to-many.** The brief carries a traceability matrix (requirement ↔ spec files ↔ phase), so coverage is checkable without forcing giant one-per-requirement spec files. Each phase states which spec files are its gate.

## The verify loop

Manual confirmation is not a phase, a gate, or a completion criterion. `references/verify-loop.md` holds the commands, prompts and output contracts behind each rule below.

### Reviewers — no artifact is cleared by its author

The brief, each spec and each diff get a written verdict block from a reviewer other than their author before they ship, are committed, or land. The reviewer is the first of these the session has, resolved while writing the brief and walked down at run time when one fails:

1. **The other agent's CLI**: `codex` with its configured model when the run is Claude Code, `claude` when the run is Codex. Pass no model name; codex runs its configured default, and the log records which model that was.
2. **A subagent on a different model.**
3. **A subagent on the same model with a fresh context** that never saw the artifact being written.
4. **A separate self-review pass**, when the agent can't start subagents: re-read the artifact cold from disk and fill the contract as if someone else wrote it.

All four run inside the loop; the run never stops or hands off for review. Every verdict block names its reviewer, and the findings log and completion report say which reviewer cleared each artifact, flagging rungs 3 and 4 as weaker. A diff written by a worker on the reviewer's side (a codex fix agent, say) is reviewed by the run itself against the same contract. A verdict that exists only as "looked fine" did not happen.

### Pick the harness

| Target | Harness |
|---|---|
| A web UI served from the worktree | The browser automation this session has (a browser MCP server such as Chrome DevTools MCP, Playwright, a CDP script), on a dedicated headless profile the run owns |
| Backend, CLI, library | A command with an expected value |
| A web UI, with no browser automation available | Offer to install one (Playwright, or a browser MCP server) before the brief ships. Otherwise command gates (HTTP responses, served HTML, build output) and DOM or component tests where they prove the row. A row nothing can verify is a brief-generation blocker |

An MCP server's tools exist only in the session that has the server, so with one the sweep runs in the run itself or in a subagent that inherits its tools, never through a CLI worker (`codex exec`, `claude -p`). Never drive the user's own browser or profile: consent prompts stall an unattended run, and its teardown could take their session with it.

### The loop

```
spec written → spec audit (reviewer) → spec commit (red, for the stated reason)
   │
   ▼
build → identity gate → this phase's specs + sweep → specs green, rows landed,
                                 │                   no in-scope regressions?
                                 ├─ yes → diff review (reviewer), commit, next phase
                                 └─ no  → fix (implementation only, never the
                                          spec) → attempt += 1 → back to build
```

- **Every sweep opens with a two-part build-identity gate**: the process serving the app's port has its `cwd` inside this worktree, and a **sentinel**, a string that exists only after this phase's change (a new test id, route or label), reaches the served output. Both pass or the sweep is void: recorded as *not verified*, rebuilt and re-gated, never recorded as *not landed*. The sentinel is part of the requirement, so the brief names it without reading the implementation, and the implementation adds it. A phase with no observable sentinel gets a command gate, and the brief says so.
- **The sweep returns a fixed shape**: a verdict per acceptance row with evidence, regressions, in-scope gaps with a file guess, out-of-scope findings left alone, and the one question that needs a human. The out-of-scope slot keeps an unattended run from wandering: those findings are recorded and reported, not fixed.
- **Three attempts per phase, and the third changes job.** An attempt is one build, gate and sweep; attempts 1 and 2 end, on failure, in a fix. Two failed fixes mean the model of the problem is wrong, so a failed attempt 3 gets a read-only diagnosis instead of a third patch: a root cause and whether the plan's premise still holds. The phase stops red with that in the findings log, and the run moves to the next phase that doesn't depend on it.
- **One worker at a time** (sweep, fix, diagnosis or review), never two phases in parallel.
- **Every agent call and long-running command is time-boxed** through run.sh's `with_timeout`, and every run.sh call gets a shell-tool timeout above its own bound. Every `codex_call` and `claude_call`, every `gate_*`, `run_tests` and `test_one`, and every `ensure_*` runs in the background, and the run waits for it (`references/verify-loop.md`, section 0).

### Targeted gates; the full suite is not a tier

A wave is a group of phases that land together (step 4).

| Tier | Scope | When |
|---|---|---|
| **Attempt** | This phase's spec files, plus typecheck | Every build inside the fix loop |
| **Phase** | Those specs, every spec written earlier in this run, and the suites of modules importing the changed files | Once, when the attempt tier goes green |
| **Wave** | The union of the wave's phase tiers, plus lint, typecheck, build, dist check | Once per wave |

Re-running every earlier spec catches a phase that satisfies its own requirement by breaking a previous one; the importers' suites catch what it broke in consumers no spec mentions. The full suite runs in exactly two situations: once at phase 0 for the baseline, and as a logged escalation when a failure will not localize. When a sweep returns a gap, re-run that one case, not its suite. Never check a targeted run against the full-suite baseline: the brief states which number each tier is checked against.

### The findings log

Screenshots, raw console and network captures, per-sweep verdicts and the appended log live in the evidence directory beside the brief, never in `/tmp`. Teardown never deletes it. Every sweep appends an entry, passes included, so the log can show phase 2 was green before phase 5 broke it; a void sweep's entry reads `identity: fail`. Out-of-scope findings are the reason the file exists: the bugs the run found and was told not to fix, which no short report will carry.

### Browser and processes

- **Reuse before starting.** A dev server or browser already on the port whose `cwd` or profile is this run's is reused. A foreign process on either port is never killed; the run steps to the next port.
- **A port that answers is not a working browser.** Smoke-test it (navigate, evaluate, write a real screenshot file) before the first sweep and at every heartbeat.
- **A browser of the run's own that fails the smoke test is killed and relaunched**, once its port frees. **Two browser launches for the whole run, then stop trying**: the browser phases are recorded unverified and the run continues on command gates. One tab, navigated, not one per check.
- **Ledger everything the run starts** that outlives one command, with port and PID, in a `## Process ledger` section. Reused processes are recorded separately, because they are never torn down.
- **Heartbeat between phases, and recycle on pressure** (browser tree over ~1.5 GB, or system free memory under 15%) rather than waiting for the crash.
- **Teardown runs on success, failure and abort.** It kills each ledger PID that still belongs to the run (a PID can be reused once its process exits), then the listener on the run's port when it serves this worktree and was not reused, then whatever still carries this run's own browser-profile path as a whole argument. Never a broad pattern kill such as `pkill -f chrome`: it takes the user's own browser with it.

## The completion report

Every run reports unless the work is unshippable or the user says not to; an unattended run is otherwise silent, and silence reads as progress. The report goes to the `Dev-loop reports` destination; without one, the findings log is the report.

The run builds it in three steps:

1. Run the mr-markdown skill over the run's own commits on its branch, not the whole diff against the default branch. Without that skill, write the same thing from `git log` and the diff of those commits: what changed and why, for a reviewer.
2. Compress it to a bolded one-line title, `<thing that changed> now <what it does>`, and at most 4 bullets. Spend the bullets first on what the reader must act on (anything still red, gaps recorded but deliberately not fixed, decisions waiting), then on change detail.
3. Count the words against the budget before posting. A cap stated without counting produces a message well over it.

| Plan shape | Posts | Budget |
|---|---|---|
| Several unrelated fixes bundled in one plan | once, after every fix has landed and its sweep is green | 100 words, hard ceiling |
| One feature, one wave | once, at the end | 40 words, hard ceiling |
| One feature, several waves | per wave, as each goes green | 40 words each, hard ceiling |

A wave too small to say anything substantial folds into the next wave's report. The last wave always reports, so every run posts at least once.

- **A post never precedes its sweep.** Green means every acceptance row came back landed with evidence, on a sweep whose identity gate passed. A phase that hit the attempt cap is named as still red, not omitted.
- **It claims only what was verified.** Work the harness can't show, and any fix whose link to the original report is still an open question, is worded honestly or left out.
- **It says who reviewed** in a phrase ("reviewed by codex", "self-reviewed, weaker") and names the findings log path, which carries the detail the word ceiling can't.
- **A blocked run still reports**: what landed, what failed, that the rest is halted. Same budget.
- **The run ends with the summary skill.** After its last report, posted or left in the findings log, whether the run finished, stopped or halted, it runs the summary skill, and that output is the session's final reply: the repos touched, the merge order, and what is left for the user. The post is for the destination; the summary is for the user when they come back to the session. Without that skill, the final reply covers the same three things, read from git and the forge.
- **Say which identity it posts as** where the destination tells the user apart from a bot, and authorise exactly these posts in the safety rules, so "post" does not read as permission to push or publish.

## Choosing the trigger

| Plan shape | Trigger |
|---|---|
| Multiple phases, each with its own verification | Claude Code: `/loop <one sentence naming the work>`, with no interval. No interval means self-paced, which a build → sweep → fix cycle needs; an interval re-fires the same prompt on a timer. |
| One fix with a single verifiable done-condition | `/goal <condition>, stop after <n> tries` when this session has `/goal`; otherwise the `/loop` form with the condition and try cap stated in the brief |
| Recurring, or must outlive this machine | Not this brief. A cloud routine (`/schedule` in Claude Code) can't reach the local paths, worktree, browser or credentials the brief and its paste line depend on. Recurring work runs locally, one run per occurrence; say so rather than hand over a paste line that can't work. |
| A Codex run | `codex exec`, below |
| Small enough to just do | None; say so |
| Phases that each need a human decision | None; say so. A loop that stops every phase to ask is worse than a checklist. |

Under Codex the brief itself is the prompt:

```bash
codex exec -C "<source repo>" -s workspace-write \
  -c sandbox_workspace_write.network_access=true \
  --add-dir "<source repo>/.git" --add-dir "<worktree's parent folder>" \
  --add-dir "<evidence directory>" - < "<brief path>"
```

`-C` is the source repo. `workspace-write` keeps `.git` read-only even inside a writable folder, and `codex exec` never asks for approval, so without the `.git` entry the worktree cut fails with `Operation not permitted`; with it, the cut and commits work and everything else stays sandboxed. The other `--add-dir` entries are the folders outside the repo the run writes, and network access is for installs and the local browser.

- **The trigger is the first word of the paste line, not the whole of it.** The resolved paths and the worktree clause follow it whichever trigger you pick.
- **`/loop` and `codex exec` run on this machine.** Sleep, shutdown or a closed lid stops them mid-phase. Say so in a brief expected to run long.
- **Always give the brief a phase count or turn cap**, and what to do on hitting it: report, don't continue.

## Token discipline

An unattended run pays for every word it generates. When this session has a compression skill (such as `/caveman`), the brief turns it on right after the worktree is cut; otherwise the brief states the style rule inline. Either way it covers internal work only: the run's reasoning, notes, todos and tool-call descriptions, prompts and messages to its agents, and verdict prose inside the contracts. The completion report and findings log (the user reads them), commit messages, MR descriptions, code, comments, security warnings and irreversible-action confirmations stay normal prose.

- An agent started through a CLI can't load this session's skills, so its prompt carries the style rules inline. Exact strings survive compression: error text, selectors, paths, numbers, units and code are reproduced verbatim.
- **Set reasoning effort per call; never inherit it.** A CLI's global default applies to every call that doesn't override it, including a sweep whose job is to click four things. The brief carries an `effort_for` helper keyed on role and attempt (`references/verify-loop.md`, section 5).
- Quote the constraint in a prompt instead of telling the agent to go read it, and pass a log's path instead of pasting the log.

## The brief's required shape

Write these sections, in this order. Each is a slot to fill, not a suggestion.

```markdown
# <Name> — runnable brief
Paste line: /loop <one sentence naming the work>. Read this brief first and
follow it: "<resolved absolute path to this file>". Source plan:
"<resolved absolute path>". Evidence dir: "<resolved absolute path>".
Land every change in a new git worktree on a new feature branch cut from a
freshly-pulled default branch; never commit to the default branch, and never
work in the user's own checkout.
(Self-paced. Runs locally: keep the machine awake. A Codex run uses the
`codex exec` command in place of this line.)
First action: cut that worktree (Ground truth names the path, branch and
base), write run.sh (Verification loop) to "<evidence dir>/run.sh", and run
`bash "<evidence dir>/run.sh" init` (`resume` instead when continuing a
stopped run). Then <the compression command, when this session has one>,
for internal work only.

## Requirements — CURRENT, EXPECTED, and the oracle
One row each, nothing paraphrased: CURRENT (probe and recorded output, or
capture path), EXPECTED in the user's words, its authority, the gate mode.
No row UNSPECIFIED.

## Traceability matrix
Requirement ↔ spec files ↔ phase; per spec, its gate mode and expected
failure signature. Spec-first rules 3 to 7, copied in.

## Ground truth
Per repo: source path; the worktree path and feature branch the run creates,
once, before phase 1; the base from origin/HEAD, fetched and fast-forwarded,
its SHA recorded. Spec-of-record path, what already landed, what is NOT in
scope. The install command known to work (a failure stops the run), and
what git doesn't track that must be copied in.

## Environment traps
One line each: installs that break things, files to regenerate rather than
edit, harness sharp edges, known flakes by name.

## Verification loop
run.sh as one bash block (the reference's `# run.sh:` blocks joined in
order, resolved), and the rule that every helper runs as
`bash "<evidence dir>/run.sh" <verb>`, is never sourced, and gets a
shell-tool timeout above its own bound; the agent calls, gates, `run_tests`,
`test_one` and `ensure_*` run in the background. The resolved
reviewer and its fallbacks with each call, and the sweep, fix, diagnose,
spec-audit and diff-review prompts and contracts. No artifact is cleared by
its author. Three attempts per phase; a failed third gets a diagnosis.

## Process ledger
Empty table: what, port, PID, started, started-or-reused. The heartbeat
between phases. Teardown for success, failure and abort: ledger PIDs, the
worktree's own listener, this run's browser profile; it deletes nothing.

## Findings log
The evidence directory's path and the append block, run after every sweep,
pass or fail: phase and attempt, identity verdict, acceptance rows,
regressions, gaps, out-of-scope findings, red receipts, verdict blocks with
their reviewer, evidence paths.

## Phases
Numbered, in dependency order, grouped into waves, independent ones marked.
Each: its requirements, gate spec files and expected red signatures, the
change, the files, the sentinel, the acceptance rows, the command gate, and
"done" (gate specs green, diff review said commit). Each is a commit pair,
or one commit carrying the red receipt where the repo can't take a red
commit. Name phase pairs that touch the same file. The state verbs, at
their steps: new_wave as each later wave begins; start_phase, then
set_impacted, as a phase begins; spec_committed after each spec commit;
next_attempt after each fix; phase_done after the implementation commit.

## Gates
The attempt, phase and wave tier commands per repo, and the baseline each is
checked against. The full suite: phase-0 baseline (its numbers and running
time) and logged escalation only. A sweep is green only when every
acceptance row reads landed with evidence attached.

## Open questions — resolve or report
Every unknown the plan flags, marked: answer before a phase runs, or carry
into the final report.

## Completion report
Destination, or "findings log only". Cadence and budget, the recipe, and
what it may not claim. It stays normal prose, like the findings log and
commit messages. Last action, on success, stop or halt: run the summary
skill; its output is the session's final reply.

## Commit and safety rules
Authorised without asking: commits on the run's own branch, the sweeps, the
completion report. Needs explicit human OK: push, merge, cherry-pick,
publish, release, migrations against real data, anything outward-facing.
Only the run stages and commits, through the commit skill (without it, `git
commit` of the staged changes in the repo's message style), after a
diff-review verdict from a reviewer that did not write the diff.
Never authorised, at any attempt: changing what a spec asserts, or its
expected value, to make an implementation pass. Weakening, skipping,
loosening or deleting an assertion is the same move; only the user changes
a requirement.

## Stop conditions
CLEARED BEFORE THE BRIEF SHIPPED: unconfirmed EXPECTED, an unvalidatable gate
mode, an undecided worktree path, branch or base, a failing install,
dependence on uncommitted work, an unnamed source among plan copies, a
missing posting permission, a check only a human can perform.
RUNTIME, halt and report: a semantic spec error, a product decision the spec
session did not settle, work that would widen scope.
RUNTIME RECOVERY, logged: a failed third attempt (diagnose, mark the phase
red, go on to independent phases), a foreign process on a port (next port),
a browser unhealthy after two launches (phase unverified, command gates), a
failing reviewer (next rung), an unreachable report destination (findings
log instead).
Everything else: keep going. Do not stop to ask whether it looks right.
```

## Rules

### The brief you write

- **Copy facts, don't cite them.** "See the handoff" fails in a fresh session. Paste the constraint.
- **The paste line is the whole handover**, and the one part guaranteed to arrive. It always carries, unparaphrased, the resolved and quoted absolute paths of the brief, the source plan and the evidence directory, and the worktree clause.
- **Every phase ends in a verification command**, and verification is quantitative: a command and an expected number, not "looks right". A check only a human can perform (hardware, a third-party account, a judgement call) is a stop condition, not a phase.
- **State the baseline numbers and name the known flakes.** "5,781 tests, 0 fail; lint 42 warnings, 0 errors" turns an ambiguous red run into an obvious regression, and an unnamed flake gets patched as a real failure.
- **Decisions already made go in as decisions**, not options.
- **Scope fences are explicit.** Say what must NOT be touched; that is where autonomous runs do their damage.
- **One worktree and one branch per repo, cut once, as the run's first action.** Phases stack as commits on that branch; a later `git worktree add` or per-phase checkout is forbidden, because a phase built in isolation misses the earlier phases' changes and fails quietly.
- **Pilot without blocking.** "Run phase 1 and report before continuing" is a contradiction in an unattended run. When the plan is large or the repo unfamiliar, make phase 1 a self-judged canary: it reports its result and continues, and stops the run only on a stated tripwire (its gate mode could not be validated, or the environment differs from the brief).
- **Feed lessons back.** A trap the run discovers goes into the findings log and the brief's Environment traps, so the next run doesn't pay for it again.

### Stop signs

- You caught yourself thinking "obviously it should…". That is the assumption. Ask anyway.
- Every requirement came out `behavior-red`. Real plans contain refactors and invariants; a uniform mode means the modes were not considered.
- The fix loop is on attempt 2 and the spec starts to look wrong. Decide honestly: mechanical (fix, log, re-validate) or semantic (stop). "It's basically mechanical" at attempt 3 is how the scheme dies.
- A requirement has no row in the traceability matrix. It has no gate, whatever the acceptance rows claim.
- You're about to print the paste line and no `audit-brief.md` exists in the evidence directory.
- You're about to commit, and the only review is your own glance at a diff you wrote. A self-review pass is a separate step that fills the contract; a glance is not a review.
- You wrote "as discussed", "as above", "the feature branch", or "verify visually". The fresh session has no discussion; name the branch, the sentinel, the selector and the expected text.
- You can't say which string proves a phase landed. That phase has no verification yet.
- A process is started in the brief and never appears again. Ledger it, or it survives the run.
- A phase step reads "start the browser". It starts once, before phase 1, and every later phase reuses it.
- The brief has no stop conditions. Every unattended run needs an exit that isn't "finish anyway".

## Common mistakes

- **Helpers sourced or pasted into the agent's shell.** That shell may be zsh and starts fresh on every call: arrays and saved state don't carry over, a multi-file gate collapses into one bogus path that reads as green, and a pasted block runs with empty variables, so `git -C ""` acts on whatever repo the shell is in. Every helper runs as `bash "<evidence dir>/run.sh" <verb>`, which guards its paths and keeps state under a lock (`references/verify-loop.md`, section 0).
- **A paste line naming a trigger, skill or tool this session doesn't have.** The brief is dead on arrival. Check `/goal`, `/loop`, the compression skill, the commit, mr-markdown and summary skills, the browser automation and the reviewer CLI against this session first, and write the fallback for any that is missing.
- **Writing a codex model name into an invocation.** The pin outlives the config, and the brief silently runs last quarter's model. Pass none; codex uses its configured default.
