---
name: loop-me-in
description: Use when a fix plan, spec, or design doc needs to become a file that a fresh session can execute unattended and prove its own changes landed — "make this runnable", "turn this plan into a loop", "so I can paste it and let it rip". Elicits the expected result of every change from the user first (never assumed), turns each into a committed spec written before the code, and gates the run on those specs. Trigger: /loop-me-in [path].
---

# loop-me-in — a plan in, a self-driving brief out

## Overview

A plan is written for a reader who already has the context. A runnable brief is written for a session that has none: fresh window, no transcript, no memory of which worktree, which trap, which decision was already settled.

**Core principle: the output must survive being pasted into an empty session.** Anything the plan leaves implicit — the repo, the branch, the environment trap that eats an hour — has to be on the page, or the run rediscovers it the expensive way.

**Second principle: the brief closes its own loop.** It builds, drives the real product, decides for itself whether the change landed, fixes what it finds, and re-checks — until green or until it hits a stated cap. Ryan is not the verification step.

**Third principle: requirements are elicited, never inferred.** The run does not decide what "fixed" means. A plan describes a change; only Ryan can say what the change is *for*. Guessing here is the failure that all the machinery downstream cannot detect: a run can be green on every gate and have built the wrong thing.

**Current behaviour and expected behaviour are two different fields, and only one of them can be measured.** A probe shows how the system behaves *today*. A live capture shows Ryan *reproducing the defect*. Both are evidence of the present, and neither is an oracle — treat either as the expected result and you encode the bug as the specification. Every requirement therefore carries both, separately:

| Field | Source | Answers |
|---|---|---|
| `CURRENT` | probe output, live capture, reproduction steps | what it does now |
| `EXPECTED` | Ryan's decision, an approved product requirement, an API contract, a compatibility invariant | what it must do instead |

`EXPECTED` must name its authority. "Because the probe showed X" is not an authority; it is the thing being changed.

**Fourth principle: the acceptance criteria are executable, and their meaning is locked before the code is read.** Requirements become spec files — committed, runnable, and derived from `EXPECTED` rather than from the implementation that will satisfy it. Implementation is then judged against them: a failing spec is a bad implementation. See the **Spec-first** section below.

**A finished brief has exactly three human touchpoints, and the first is the largest:**

1. **Specification** — up front, before anything runs: the requirements, the expected result of each, and a live capture where words were not enough.
2. A **blocking decision** the spec session did not settle — a product call, an ambiguity, a question the run cannot answer from the page.
3. **Deployment** — the cherry-pick, push, merge, or release into main.

Everything between those is the run's job, commits on its own branch included. A brief that ends with "confirm it looks right" has not been converted; it has been reformatted.

**The point of touchpoint 1 is to buy out touchpoints later.** Time spent pinning down expected results is not overhead added to the run — it is the per-phase "does this look right?" interruptions, paid once, in daylight, before the machine is committed to anything.

## When to use

- A `/ivtg` fix plan, a `superpowers:writing-plans` plan, or any dated plan in the vault is approved and ready to execute.
- You want to hand execution to a session you won't babysit.
- Symptoms: the plan says "then fix it" without naming the branch; it assumes a tool that 404s; it was written before three decisions that have since been made; the last run kept pulling you back in to confirm whether a change had actually landed; the last run finished green and had fixed something adjacent to the actual complaint.

**Budget for the specification session.** This skill front-loads a conversation: every requirement's expected result, probed and where necessary captured live. That is the work, not a preamble to it — a plan handed over without it produces a brief that cannot tell right from wrong.

**Don't use for:** a plan still under discussion (run `/demuddy` first), or a one-line change you'd just do.

## Procedure

1. **Read the whole plan** — including the sections that aren't instructions. Also read anything it cites as spec-of-record. The brief must stand alone, so facts have to be copied in, not linked.

   **Mine the "Risks & unknowns" / "Open questions" section hardest.** It is the one a brief reliably drops, because it contains no steps to transcribe — and it is where "does this fix even address the report?" lives. A `/demuddy` pass concentrates exactly these into one clean section, which makes them easier to skip and more expensive to skip.

   **If the plan exists in more than one copy, diff them before building.** A duplicate vault, an older draft, a pre-review version: they can differ by hundreds of lines and by which fix is correct. Build from the copy the user names, and say in the brief how to recognise a stale one.
2. **Resolve the environment, don't assume it.** This comes before any spec work, because a spec cannot be written, run, or committed without knowing the worktree, the branch, the test runner and the install command. For every repo the plan touches, establish and write down: the source repo path, the worktree path the run will create and the feature branch it will cut there, the base branch read from `origin/HEAD` rather than assumed to be `main`, how deps are installed, the test runner and how it names spec files, and the verification command. Check these — a stale path is the single most common way these runs die.

   **Specify the worktree; never create it.** This skill writes briefs and runs no `git worktree` command of its own. Name the exact path the run will create, so every gate, evidence path and command in the brief is absolute and correct before that worktree exists.

   **An install is not a safe no-op.** Where a repo depends on a private registry, a bare `install` can re-resolve a package, fail to fetch it, and leave the tree worse than it found it. Name the install command that is known to work, and make a failed install a stop condition rather than something the run works around.

   **A new worktree starts empty of everything git does not track.** Dependencies, build caches, `.env` and other ignored files, and any uncommitted work sitting in Ryan's own checkout do not travel to it. Name what must be installed or copied across before the first gate; a plan that depends on uncommitted local work is a brief-generation blocker, not something the run discovers at 3am.
3. **Lock the acceptance oracle for every requirement. Ask; never assume.** A conversation with Ryan, before phases exist. Work the ladder in **Establishing expected results** below until each requirement has a `CURRENT` and an `EXPECTED` with a named authority, specific enough to encode as an assertion. Assign each one a **gate mode** (table in **Spec-first**). **A requirement whose `EXPECTED` you inferred is a brief-generation blocker: the brief does not ship until Ryan settles it.**
4. **Plan the specs; the run writes them.** In the brief, map requirements to spec files and phases — many-to-many is fine and often correct. For each, record the gate mode and the *expected* failure signature. The run writes, validates and commits each spec at the start of its own phase; the brief carries the plan and the expected signature, not the spec's text or its recorded output. See **Spec-first**.
5. **Harvest the traps.** Every "don't do X, it breaks Y" you know: package managers that 404, files that must be regenerated rather than hand-merged, test harnesses with sharp edges, suites that OOM. A trap costs one line here and an hour there.
6. **Design the verify loop around the specs.** Pick the harness, resolve the surface (command, port, URL), and for each phase name its spec files plus the sentinel proving the build under test is this one. Do this while you still have the plan open. Where a requirement cannot be a unit spec — a visual, a layout, a live surface — its spec is a *scripted* assertion (a committed CDP script, or a command with an expected value), never sweep prose.

   **Resolve the stack's adapters here, by name**, so the brief is not silently hard-coded to one ecosystem: `START`, `TEST_ONE`, `TEST_IMPACTED`, `TYPECHECK`, `BUILD`, `DIST_CHECK`. A repo without one of these omits that gate explicitly rather than inheriting a command from another project.
7. **Ask where it reports.** Do not infer the channel or topic from the plan's subject. Ask the user to paste the destination — channel, and topic if the work belongs to one — once per area if the plan splits across several. Resolve what they paste to a canonical resource string and write that into the brief.
8. **Pick the trigger** (table below).
9. **Write the brief to `~/.claude/plans/YYYY-MM-DD/<source-name>-run.md`** — resolve that symlink and say the real path in your report, so a wrong target is caught immediately. Never into a repo; plan files are not committed.

   **Vault trap:** an iCloud-nested duplicate of the plans vault can exist (`…/Obsidian/Obsidian/Claude Plans` beside the real `…/Obsidian/Claude Plans`), and the source plan may be handed to you as a path inside the *duplicate*. Do not infer the destination from where the source file sits, and do not infer it from the symlink alone. If both directories exist, name both and ask which is live before writing.

   **Quote every path.** The vault's real path contains spaces (`Mobile Documents`, `Claude Plans`), and so do some source directories. An unquoted path, or a `for f in $(cat list)`, silently shatters into fragments and the run reads past it. Quote in every command the brief contains, and never word-split a file list.
10. **Report the path and the paste line.** That's the deliverable. Print the paste line in full, with every path already resolved and quoted — it has to work pasted into a fresh session by itself, so a placeholder left in it is a broken deliverable, not a detail.

## Establishing expected results

**Do not assume anything.** Not from the plan's title, not from the code, not from what would be reasonable. A plan says what someone intends to change; it very often does not say what the result should look like, and it is written by someone who already knew.

Two instruments establish `CURRENT`; only Ryan establishes `EXPECTED`. Run them in this order — measure first, then ask, because confirming a finding is fast and specifying from nothing is slow.

| Step | Instrument | Establishes | Produces |
|---|---|---|---|
| 1 | **Probe** — cheapest first | `CURRENT` | A recorded observation: command plus output, request plus response, a screenshot of how it behaves *today* |
| 2 | **Live capture**, when the probe can't settle it | `CURRENT` | A screen recording, CDP trace, console and network capture of Ryan reproducing it, saved in the evidence directory |
| 3 | **Ask Ryan for the desired delta** | `EXPECTED` | The result in his words — exact text, number, state; what should happen and what should *stop* happening — plus the authority it rests on |

**Steps 1–2 can never produce step 3.** They tell you what is; the change is defined by what ought to be. A probe that shows a badge reading `0` does not tell you whether `0` or no badge at all is correct. That is the question for Ryan, and it is the whole point of the session.

**Escalate to live capture rather than negotiating in prose.** Three rounds of "do you mean X or Y?" costs more than one recording, and a recording carries what nobody thinks to mention — the timing, the intermediate state, the second thing that flickers. Escalate whenever the issue is intermittent, visual, or Ryan can't put it in words; also whenever his description of current behaviour and the probe disagree, since one of them is wrong and the spec must not be written until you know which.

**The live capture is an artifact, not a conversation.** It lands in the evidence directory beside the brief, it is named in the requirement it supports, and the spec cites it. A capture described in chat and never saved is gone by the time the run needs it.

**What "specific enough" means.** Encodable as an assertion, without a judgement call at run time. "The counter should be right" is not. "After deleting the last unread DM, the sidebar badge shows no number at all, not 0" is.

**Every requirement carries its expected result into the brief verbatim.** Ryan's words, not a paraphrase — a paraphrase is where an assumption re-enters after you were careful enough to avoid one.

### The blocker that outranks the others

A requirement whose `EXPECTED` is unconfirmed is a **brief-generation blocker**, and it is settled in daylight: the brief does not ship until Ryan states it. This is deliberately *not* a runtime stop condition — an unattended run must never be the thing that discovers a requirement was never specified. Every gate downstream can pass on a wrong target, so this is the one failure the machinery cannot catch. A brief built on an assumed expectation is worse than no brief: it produces confident, tested, committed, wrong work.

## Spec-first — the requirement is the test

Acceptance criteria are **files in the repo**, whose meaning is fixed from `EXPECTED` before the implementation is read.

### The rules

1. **Lock the meaning before reading the implementation; encode it afterwards.** What is frozen is the *acceptance semantics* — the assertion's subject and its expected value, taken from `EXPECTED` and the capture. The *mechanics* are not frozen: read the test harness, fixtures, helpers, public interfaces and the runner's conventions freely, because a spec written blind to them produces exactly the missing-import and bad-selector failures that rule 2 rejects. What you must never do is derive an expected value from the implementation, or write an assertion that restates what the code does. Review each spec for tautologies before committing it.
2. **Validate the spec against its gate mode before implementing.** Not every requirement can or should fail red:

   | Mode | Pre-implementation validation | Use for |
   |---|---|---|
   | `behavior-red` | The named test runs and fails **at the expected assertion**, with the recorded signature | New behaviour, bug fixes with an observable wrong result |
   | `green-characterization` | The tests pass **before and after** — they pin behaviour that must not change | Refactors, moves, extractions |
   | `compile-red` | Fails to build because the named symbol/route/export does not exist yet | New API surface |
   | `benchmark-delta` | A recorded baseline, a stated tolerance, and a repeat count that survives noise | Performance work |
   | `structural-invariant` | The invariant holds now and must keep holding (lint rule, dist check, import fence) | Boundary and packaging rules |
   | `discovery` | No gate is possible yet — the phase's output *is* the information needed to specify | Spikes; ends in a report, never a claim of done |

   Only `behavior-red` requires an assertion failure. Each requirement's mode is chosen during the spec session and written into the brief; a mode that cannot be validated is a brief-generation blocker, not a phase.
3. **A pre-implementation pass under `behavior-red` is a finding, not a green light.** It means one of: the requirement is already satisfied (report it, drop the phase), the spec asserts the wrong thing, or the spec never ran. Classify which, and say so. It is never banked as progress.
4. **Infrastructure failure is not red.** A missing runner, dependency error, syntax error, timeout, crash, or zero-tests-executed is an infrastructure failure and is fixed, not recorded as evidence. Red means *this named test executed and failed at the assertion you predicted*.
5. **The red receipt is the proof, not the commit order.** Commit ordering only proves that test text preceded implementation text. Record a receipt per spec — base SHA, spec SHA, exact command, exit classification, the named test, and the expected-vs-actual failure signature — in the findings log. Separate spec and implementation commits are the default because they are reviewable, but **check first whether the repo tolerates an intentionally-red commit**: CI on every push, pre-commit gates, and `git bisect` all suffer from one. Where it does not, land the pair as one commit and let the receipt carry the red evidence.
6. **A failing spec is a bad implementation.** The fix loop changes the implementation.
7. **Freeze the meaning, not the file.** A spec can be wrong in two very different ways:
   - **Mechanically** — bad selector, malformed fixture, wrong mock, racy wait, misused harness API. The requirement is intact. The run may land a **test-only corrective commit**, logged in the findings log with what was wrong, and must re-validate the gate mode afterwards. This is not an escape hatch: it may not change the assertion's subject or expected value.
   - **Semantically** — the assertion encodes something Ryan did not ask for, or satisfying it would require weakening what he did ask for. **Stop.** Only Ryan can re-state a requirement.

   Weakening, skipping, deleting or loosening an assertion to make an implementation pass is never a mechanical fix, whatever it looks like at attempt 3.
8. **Requirements, specs and phases are many-to-many.** One requirement may need several focused spec files and shared fixtures; several coupled requirements may need one atomic implementation. The brief carries a **traceability matrix** — requirement ↔ spec files ↔ phase — so coverage is checkable without forcing a 1:1:1 that produces giant spec files, duplicated fixtures and phases that cannot independently go green. What each phase must state is which spec files are its gate.

### What this actually buys — stated honestly

**Spec-first does not reveal blast radius.** Writing the test before the code tells you nothing about which other modules the change can break. Focused-test *selection* is what saves time, and it is a separate mechanism that spec-first makes easier rather than causes.

The real saving is narrow and worth having: **inside the fix loop**, the question is "do this phase's spec files pass?" — seconds, no guessing which suite covers the change. That is where the attempts pile up, so that is where the hours were going.

What has *not* gone away: an impacted-test set still runs at the phase boundary, and a wider gate at the wave boundary. A green spec proves the requirement is met; it does not prove nothing else broke. Anyone who reads this scheme as "no more suite runs" will ship a regression.

The specs accumulate. By the last phase, the run's own spec files are a fast, targeted regression suite for exactly the behaviour this plan cared about — and they stay in the repo afterwards, which is the durable half of the work.

## The verify loop

The brief verifies itself. Manual confirmation is not a phase, not a gate, and not a completion criterion.

Commands, prompts, the sweep output contract, and the exact codex invocations live in `references/verify-loop.md`. **Copy the resolved commands into the brief** — a fresh session will not read that file.

### Pick the harness

| Target | Harness | Why |
|---|---|---|
| Any web UI served from the worktree | A codex agent driving the `chrome-devtools` CDP script | Headless-capable, scriptable, no interactive consent, works against any localhost surface |
| The OM Chat GUI | `/testing-harness` | Already carries `doctor` (is the daemon actually serving the working tree?), saved logins, and a cloud-vs-local pixel-diff report. Confirm it is in this session's skill list before naming it — it was renamed from `/om-chat-web`, and a brief that names a trigger the run doesn't have has no harness at all |
| Backend, CLI, library | A command with an expected value | A browser check that proves nothing is worse than admitting the check is a command |

`claude-in-chrome` is the wrong tool here: per-site permission grants and Ryan's real profile mean the run stalls at 3am waiting for consent.

### The build-identity gate

Every sweep opens with a gate in two parts:

- the process listening on the app's port has its `cwd` inside this worktree, and
- a **sentinel** — a string that exists only after this phase's change — reaches the served output.

Both pass or the sweep is void. A void sweep is recorded as *not verified*, and the run rebuilds and re-gates; it is never recorded as *not landed*. Without this, a stale bundle or a second dev server on the same port turns "verified" into "clicked around something".

Name a sentinel per phase while writing the brief: a new `data-testid`, a new route, a new label. A phase with no observable sentinel gets a command gate instead, and the brief says so.

### The loop

```
spec commit (red, for the stated reason)
   │
   ▼
build → identity gate → run this phase's spec + sweep → spec green, acceptance rows
                                  │                     landed, no in-scope regressions?
                                  ├─ yes → review diff, commit, next phase
                                  └─ no  → fix agent (implementation only, never the
                                           spec) → attempt += 1 → back to build
```

The sweep returns a fixed shape — verdict per acceptance row with the evidence, regressions seen en route, in-scope gaps with a file guess, out-of-scope findings left alone, and the single question that would need a human. The out-of-scope slot is what keeps an unattended run from wandering: those findings get recorded and reported, not fixed.

**Cap at 3 sweeps per phase, and the third attempt changes job.** Two failures of the same class mean the model of the problem is wrong, so attempt 3 is not a third patch: it is a read-only diagnosis agent that returns a root cause and a verdict on whether the plan's premise still holds. The phase then stops red with that explanation in the findings log, and the run moves to the next phase that does not depend on it. An explanation is worth more than a fourth patch.

**Every codex run and every browser command is time-boxed.** A hung agent costs the whole night. macOS has no `timeout` binary — the brief defines a `with_timeout` helper instead (`references/verify-loop.md`, section 0), or the first phase dies on `command not found`.

### Targeted gates. The full suite is a last resort, not a tier.

A suite that takes 224 seconds is not a gate — at fourteen phases and three attempts it is two and a half hours of re-proving code the phases never touched. It stays out of the loop entirely, and out of the wave boundary too. Every scheduled gate is scoped to what the change can reach:

| Tier | Scope | When |
|---|---|---|
| **Attempt** | **This phase's spec file**, plus `typecheck` | Every build inside the fix loop |
| **Phase** | That spec, plus every spec written earlier in this run, plus the suites of modules importing the changed file | Once, when the attempt gate goes green |
| **Wave** | The union of that wave's phase tiers, plus lint, typecheck, build, dist check | Once per wave |

The attempt tier is a single spec file because spec-first made it one: the phase exists to satisfy one requirement, so the inner loop asks one question. That is the whole saving.

The phase tier is what makes the omission safe, and it has two parts for two different reasons. **Re-running every earlier spec** catches the phase that satisfies its own requirement by breaking a previous one — cheap, because these are targeted files the run wrote itself. **The importers' suites** catch what the change broke in consumers the specs never mention. Lint, typecheck and build stay at the wave boundary because they are fast; it is the test runner that is expensive.

**The full suite runs in exactly two situations:**

1. **Once at phase 0**, to capture the baseline. Without it no later number is interpretable, and one run is the price of reading every other run correctly.
2. **As an escalation, when a failure will not localize** — a phase tier that comes back green while the sweep still reports a regression, or a failure whose origin the fix loop cannot find. Then it is a deliberate act: budgeted with `with_timeout`, logged in the findings log as an escalation with what prompted it, and named in the report. Never a reflex, never "to be safe".

**Error scans are targeted too.** When a sweep returns a gap, re-run that one case — not the suite containing it. The failing case's own command goes in the sweep's output, so the fix loop never has to guess and never has to widen.

**Never check a targeted run against the full-suite baseline.** "215 pass, 0 fail" is not "7084 pass, 59 fail". The brief states which number each tier is checked against, or a green subset gets read as a green repo.

### The findings log

**Every sweep appends to it, and the evidence outlives the run.** Screenshots, raw console and network captures, per-sweep verdicts, and the appended log all live in one directory beside the brief in the plans vault — never in `/tmp`, which a reboot clears. Teardown kills processes; it never deletes that directory.

Passing sweeps get an entry too: a log that records only failures can't show that phase 2 was green before phase 5 broke it. Void sweeps get one reading `identity: fail`, so "nothing was verified" stays distinguishable from "nothing landed".

**Out-of-scope findings are the reason the file exists.** They are the bugs the run found and was told not to fix, they are what a browser sweep is uniquely good at noticing, and a post capped at 40–100 words will not carry them.

### One browser, proven healthy, reused

The most expensive failure mode here is a run that spends the night launching browsers instead of verifying with one.

- **Reuse before starting.** A dev server already on the port whose `cwd` is the worktree gets reused; a Chrome already on the debugging port whose `--user-data-dir` is this run's profile gets reused. Neither is relaunched. A *foreign* process on either port is never killed — the dev server case stops the run, the Chrome case steps to the next port via `CHROME_DEVTOOLS_URL`.
- **A port that answers is not a working browser.** Before the first sweep and at every heartbeat, the browser must pass a functional smoke test: navigate, evaluate, and write a real screenshot file. Those are the three things every sweep depends on, and `/json/version` still answers from a Chrome whose renderer has died.
- **Two launch attempts for the whole run, then stop.** A relaunch loop ends the night with forty headless Chromes and zero verification. The third failure is a stop condition, not a retry.
- **One tab, not one per check.** `--new-tab` once at the start, then navigate that same tab. Each extra tab is another renderer process.
- **One codex agent at a time** — sweep or fix, never both, never two phases in parallel.

### Process ledger, memory, teardown

Anything the run starts that outlives one command — dev server, Chrome, background codex — is recorded at spawn with its claimed port and PID, in a `## Process ledger` section the run appends to. Reused processes are recorded separately, because they must not be torn down.

- **Between phases, a heartbeat:** app URL answers, browser passes the smoke test, no `codex exec` still running, no stopped background jobs, and two numbers — the RSS of this run's browser tree and the machine's free memory (`memory_pressure`). Anything stuck is killed and restarted, not waited on.
- **Recycle on pressure, don't wait for the crash.** Browser tree over ~1.5 GB or system free under 15%: kill it by ledger PID and bring one back. A headless Chrome twenty sweeps deep is not the process it was at phase 1.
- **Teardown runs on success, failure, and abort.** Kill by ledger PID, then one pattern kill scoped to this run's profile path to reap the renderer children; `pgrep` only to confirm nothing survived. A bare `pkill -f chrome` would take Ryan's own browser with it, and the brief must never contain one.

## The completion post

Every brief reports to OM Chat over the OpenMarket MCP server's rooms tools (`room_*`, `doc_*`), unless the work is unshippable or the user says not to. An unattended run is otherwise silent, and silence reads as progress.

**How the run builds it** — three steps, in this order:

1. Run `/mr-markdown` over the changes made this session — the run's own commits on its branch, not the whole diff against main.
2. Compress that output to a **bolded one-line title in the form `<thing that changed> now <what it does>`**, followed by at most 4 bullets. Spend the bullets on what a reader has to act on first — anything still red, gaps recorded but deliberately not fixed, anything waiting on a decision — then on change detail.
3. Count the words against the budget before posting. A cap stated without counting produces a message well over it.

**When it posts, and the budget:**

| Plan shape | Posts | Budget |
|---|---|---|
| Several unrelated fixes bundled in one plan (`ivtg-*`) | once, after every fix has landed and its sweep is green | 100 words, hard ceiling |
| One large standalone feature | per wave or phase, as each goes green | 40 words, hard ceiling |
| A wave too small to say anything substantial | not at all — folds into the next wave's report | — |

Below 40 words there was nothing worth interrupting for; over 100 nobody reads it.

- **A post never precedes its sweep.** Green means every acceptance row came back landed with evidence, on a sweep whose identity gate passed. A phase that hit the attempt cap is named as still red, not omitted.
- **The destination comes from the user, the resource string comes from the server.** They paste the channel and topic (procedure step 7); `session_grants` (read-only, no consent side effects) confirms it and yields the canonical resource string that goes in the brief — `room_post` wants that, not a display title. `82eae63a1bd3` (`#chat`, space `openmarket`) is the default when they don't name one. Verify the `post` capability while writing: a missing grant means the run stalls at 3am waiting for consent.
- **Route to the right topic.** Where the work belongs to a topic, list them with `room_topic_list` and confirm the posting tool's schema advertises the topic field before assuming it takes one. Creating a topic needs `contribute` on the room — knock for it while writing the brief. If more than one channel is in scope, the brief names each destination against the phases it covers.
- **`room_post` posts as the bot. `om room say` posts as Ryan.** Say which.
- **It may only claim what was verified.** Backend work a browser cannot show, and any fix whose link to the original report is still an open question, must be worded honestly or left out.
- **It names the findings log path.** The word ceiling keeps the post readable; the path keeps the detail reachable.
- **A blocked run still posts** — what landed, what failed, that the rest is halted. Same budget.
- **Authorise exactly these posts** in the safety rules, so "post" does not read as permission to push or publish.

## Choosing the trigger

| Plan shape | Trigger | Why |
|---|---|---|
| Multiple phases/tasks, each with its own verification | `/loop <one sentence naming the work>` — no interval | Omitting the interval puts `/loop` in self-paced mode, which is what a build → sweep → fix cycle needs. An interval (`/loop 5m …`) re-fires the same prompt on a timer instead, which is wrong for phased work. |
| One fix with a single verifiable done-condition | `/goal <condition>, stop after <n> tries` | An evaluator model checks the criteria each turn, and the cap is part of the command. **Confirm `/goal` is in this session's skill list before writing it into a paste line** — it isn't installed everywhere. Where it's absent, use the `/loop` form with the success condition and try cap stated in the brief instead. |
| Recurring work, or work that must outlive this machine | `/schedule` | Runs as a cloud routine on a cron schedule (research preview), so a closed laptop doesn't end it |
| Small enough to just do | None — say so | Not everything needs a loop; the simplest thing that works wins |
| Phases that each need a human decision | None — say so | A loop that stops every phase to ask is worse than a checklist |

**The trigger is the first word of the paste line, not the whole of it.** Whichever one you pick, the resolved brief, plan and evidence paths and the worktree clause still follow it — a `/goal` or `/schedule` paste line lands in the same contextless session a `/loop` one does.

**`/loop` runs on this machine.** Sleep, shutdown, or a closed lid stops it mid-phase, which for an overnight run means waking up to a half-applied plan and a leaked browser. Say so in the brief when the run is expected to go long: either the machine stays awake, or the work belongs in `/schedule`.

**Always give the brief a turn cap or phase count.** An unbounded loop burns tokens on work nobody is reading. State the ceiling and what to do on hitting it: report, don't continue.

## Token discipline

An unattended run pays for every word it generates, and most of them are scaffolding nobody reads. The brief turns compression on with `/caveman:caveman full` as soon as the worktree is cut, which compresses the run's own reasoning and internal writing for the rest of the session.

| Compressed | Left as normal prose |
|---|---|
| The run's reasoning, phase notes, todos, tool-call descriptions | The completion post — Ryan reads it |
| Sweep and fix prompts sent to codex | The findings log — Ryan reads it the next morning |
| Messages between the run and its agents | Commit messages, MR descriptions, code, comments |
| Verdict prose in the sweep output contract | Security warnings, and any irreversible-action confirmation |

The plugin's own boundary rule already exempts everything persisted outside chat, so turning it on does not corrupt the post or the log. Say which side of the line each artifact is on anyway; a run that compresses the one message Ryan reads has saved tokens by making the output useless.

**Codex cannot invoke Claude Code skills**, so its prompts carry the compression rules inline instead. Exact strings survive compression: error text, selectors, file paths, numbers, units, and code are reproduced verbatim, never paraphrased shorter.

**Reasoning effort is set per call, never inherited.** `~/.codex/config.toml` sets `model_reasoning_effort = "xhigh"` globally, so an agent without an explicit override runs at xhigh — including a sweep whose entire job is to click four things and report what it saw. The brief carries an `effort_for` helper keyed on role and attempt: mechanical work opens low, each failed attempt moves one rung up, and behavioural acceptance rows or wide-blast-radius fixes start one rung higher. Values and the helper itself: `references/verify-loop.md`, section 4.

The rest of the spend is structural, not stylistic: quote the constraint in the prompt instead of telling the agent to go read it, and reference the console-log path rather than pasting the log.

## The brief's required shape

Write these sections, in this order. Each is a slot to fill, not a suggestion.

```markdown
# <Name> — runnable brief
Paste line: /loop <one sentence naming the work>. Read this brief first and
follow it: "<resolved absolute path to this file>". Source plan:
"<resolved absolute path>". Evidence dir: "<resolved absolute path>".
Land every change in a new git worktree on a new feature branch cut from a
freshly-pulled default branch; never commit to the default branch, and never
work in Ryan's own checkout.
(no interval — self-paced. Runs locally: keep the machine awake.)
First action: cut that worktree — Ground truth names the path, the branch and
the base. Then /caveman:caveman full — internal work only. The completion post,
the findings log, and commit messages stay normal prose.

## Requirements — CURRENT, EXPECTED, and the oracle
One row per requirement, none of it paraphrased: `CURRENT` (probe command and
its recorded output, or the live-capture path in the evidence directory);
`EXPECTED` in Ryan's words verbatim; the **authority** EXPECTED rests on
(his decision, a product requirement, an API contract, a compatibility
invariant); and the gate mode. No row may be UNSPECIFIED — that is resolved
before this brief ships, not at 3am.

## Traceability matrix
Requirement ↔ spec files ↔ phase, many-to-many. Per spec: its gate mode and
the *expected* failure signature the run must match before implementing.
The run records the actual signature as a red receipt in the findings log.
State that acceptance semantics are frozen while test mechanics are not; that
a mechanical test defect may be corrected in a logged test-only commit that
re-validates the gate mode; and that a semantic spec error stops the run.

## Ground truth
Per repo: the source repo path, the worktree path the run creates, the feature
branch it cuts there, and the base branch read from `origin/HEAD` — fetched and
fast-forwarded before the cut, with the base SHA recorded so the run's diff
stays interpretable. Then the spec-of-record path, what already landed (commit
shas), and what is deliberately NOT in scope.
One branch per repo, one worktree for the whole run, cut before phase 1.
The install command known to work, run in the new worktree before the first
gate, and that a failed install stops the run.

## Environment traps
One line each. Install commands that break things. Files that must be
regenerated rather than edited. Test-harness sharp edges. Known flakes and
their names, so a red suite isn't misread as a regression.

## Verification loop
The harness and its exact commands: how the surface starts (command, claimed
port, URL), how the browser starts and how it is reused, the smoke test, the
two-part identity gate, the sweep and fix agent invocations, the `effort_for`
helper, and the sweep output contract. Attempt cap: 3 sweeps per phase, the
third being diagnosis rather than a fix. The `with_timeout` helper, defined
here and used on every long-running command.

## Process ledger
Empty table the run fills in as it spawns things: what, port, PID, started,
started-or-reused. Plus the heartbeat to run between phases, and the teardown
block that runs on success, failure, and abort alike — which kills processes
and deletes nothing.

## Findings log
The evidence directory's absolute path, beside this brief in the plans vault.
The append block the run runs after every sweep, pass or fail. What each entry
carries: phase and attempt, identity verdict, acceptance rows, regressions,
in-scope gaps, out-of-scope findings, and the screenshot and console-log paths.

## Phases
Numbered, one requirement each. Every phase carries: the requirement it
satisfies, its spec file and that spec's recorded red failure, the change, the
files, the sentinel that proves the build under test is this one, the
acceptance rows the sweep must return a verdict on, the command gate, and what
"done" looks like — which is always "this spec is green".
One requirement = one spec = one phase = one commit pair (spec red, then
implementation green).

## Gates
Three scoped commands per repo — attempt tier (this phase's spec file plus
typecheck), phase tier (that spec plus every earlier spec in the run plus the
importers' suites), wave tier (the union of the wave's phase tiers plus lint,
typecheck, build, dist check). The full suite is
not a tier: it runs once at phase 0 for the baseline, and thereafter only as a
logged escalation when a failure will not localize. State which number each
tier is checked against, and how long the full suite takes so it is never
mistaken for a hang. The browser gate is the sweep, and it is green only when
every acceptance row reads landed with evidence attached.

## Open questions — resolve or report
Every unknown the plan flags, carried over verbatim in substance. Mark which
must be answered BEFORE a phase runs, and which just ride into the final
report. Never let one be silently assumed away.

## Completion post
Destination — channel and topic, by canonical resource string, per phase if
more than one. Cadence: once at the end (bundled fixes) or per wave (large
feature). The recipe: `/mr-markdown` over this session's commits, compressed
to a bolded `<thing> now <what>` title plus at most 4 bullets, counted against
the ceiling — 100 words consolidated, 40 per wave. What it may not claim.

## Commit and safety rules
Authorised without asking: commits on the run's own branch, the verify sweeps,
the completion post. Needs explicit human OK: push, merge, cherry-pick into
main, publish, release, migrations against real data, anything else
outward-facing. Codex agents never commit — the run reviews the diff, stages,
and commits via the `/commit` skill.
**Never authorised, at any attempt, for any reason: changing what a spec
asserts, or its expected value, to make an implementation pass.** Weakening,
skipping, loosening or deleting an assertion is the same move under another
name. A mechanical test defect — selector, fixture, mock, racy wait — may be
corrected in a test-only commit that leaves the assertion's subject and
expected value untouched, is logged in the findings log, and re-validates the
gate mode. Anything beyond that is a semantic change to the requirement, and
only Ryan can make one.

## Stop conditions
Two lists, and the difference matters more than either.

CLEARED IN DAYLIGHT — brief-generation blockers. The brief does not ship
until every one is resolved, so the run never meets them: unconfirmed
EXPECTED, a gate mode that cannot be validated, an undecided worktree path,
feature branch or base branch, a failing install, a plan that depends on
uncommitted work in Ryan's checkout, a duplicate-vault ambiguity, a missing
posting grant, a verification that only a human can perform.

RUNTIME — the run halts and reports only for: a semantic spec error, a
product decision the spec session did not settle, a third failed sweep on one
phase, or work that would widen scope.

RUNTIME RECOVERY, not a stop — the run handles these itself and logs them:
a foreign process on a port (step to the next port), a browser that will not
come up healthy after two attempts (record the phase as unverified and
continue with command gates), an unreachable posting destination (write the
report to the findings log instead), a phase blocked by an earlier red phase
(skip it and take the next independent one).
Everything else: keep going. Do not stop to ask whether it looks right.
```

## Rules for the brief you write

- **Copy facts, don't cite them.** "See the handoff" fails in a fresh session. Paste the constraint.
- **The paste line is the whole handover, and it assumes a session that knows nothing.** It is the one part guaranteed to arrive, so two things are always in it and neither is paraphrased, shortened, or left to the brief body:
  - **The file paths, resolved and quoted.** This brief, the source plan, and the evidence directory, each as a real absolute path — `~/.claude/plans` is a symlink, so resolve it, and quote every one because the vault's path contains spaces. A fresh session cannot find a file it was not handed.
  - **The worktree clause.** Changes land in a new git worktree on a new feature branch cut from a freshly-pulled default branch; the default branch and Ryan's own checkout are off limits.
- **Every requirement arrives with Ryan's expected result attached**, verbatim, plus how it was established. No expected result, no phase.
- **Every phase's done-condition is its spec going green**, and that spec was red first for a recorded reason.
- **Every phase ends in a verification command**, not "check it works".
- **State the baseline numbers.** "5,781 tests, 0 fail; lint 42 warnings, 0 errors" turns an ambiguous red run into an obvious regression.
- **Name the known flakes.** Otherwise the run treats one as a real failure and starts patching.
- **Decisions already made go in as decisions**, not options. A brief that reopens a settled question wastes the run.
- **Scope fences are explicit.** Say what must NOT be touched; that is where autonomous runs do their damage.
- **Verification is quantitative.** A command plus an expected number, not "looks right". A check the run genuinely cannot perform — hardware, a third-party account, a human judgement call — is a stop condition, not a phase. "Ryan will look at it" is not one of those.
- **One worktree per repo, one branch, for the whole run — cut once, as the run's first action.** The run creates it from the path, branch and base the brief names; every later `git worktree add` and per-phase checkout is forbidden. Phases stack as commits on that one branch. A fresh session will otherwise isolate a phase and build against a tree missing the earlier phases' changes — which fails quietly, not loudly. Name the phase pairs that touch the same file, so the ordering constraint is visible.
- **Pilot without blocking.** "Execute phase 1 and report before continuing" is a contradiction in an unattended run: if it waits for review the night ends after one phase, and if it doesn't it was never a pilot. Instead, when the plan is large or the repo is unfamiliar, make phase 1 a **self-judged canary** — it posts its result immediately and continues, and it *stops the run* only on a stated tripwire (its gate mode could not be validated, or the environment turned out different from the brief). Ryan wakes to either a finished run or a run that stopped at phase 1 with a reason.
- **Feed lessons back.** If the run discovers a trap, it belongs in the plan's Environment traps for next time — fixing the instance without recording it means the next run pays again.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Assuming the expected result instead of asking | Every gate passes; the run built the wrong thing, tested and committed |
| Treating a probe or a live capture as the expected result | Both measure CURRENT. You have just specified the bug as the requirement |
| An EXPECTED with no named authority | Nobody can tell later whether it was a decision or a guess |
| Paraphrasing Ryan's expected result into the brief | The assumption you avoided re-enters as your wording |
| Negotiating an ambiguous issue in prose instead of asking for a live capture | Rounds of clarification, and a spec written on the wrong reading anyway |
| A live capture described in chat but never saved to the evidence dir | The one piece of ground truth is gone when the run needs it |
| Deriving an expected value from the implementation | The spec asserts what the code does, so it passes whether the code is right or not |
| Writing a spec blind to the harness, fixtures and interfaces | Guaranteed missing-import and bad-selector failures — the exact ones that don't count as red |
| Demanding `behavior-red` of a refactor or a perf change | Unsatisfiable gate; the phase cannot start, or a fake failure gets manufactured to satisfy it |
| Accepting any non-zero exit as red | A missing runner, syntax error or zero tests executed all look like proof; none is |
| Relying on commit order as the red evidence | Proves text order only. Without a receipt, nothing shows the spec ever ran or why it failed |
| An intentionally-red commit in a repo with CI on every push or bisect in use | You have knowingly broken CI, cherry-picks and `git bisect` for a record a receipt could have carried |
| Loosening an assertion and calling it a mechanical fix | The one move that voids the scheme, wearing the costume of the one that's allowed |
| Treating a spec that passes pre-implementation as a green phase | Either the requirement was already met, the spec is wrong, or it isn't running — and the run can't tell which |
| Linking the spec instead of copying its constraints | Fresh session can't see it; invents its own interpretation |
| Omitting the worktree path, or not forbidding per-phase worktrees | A later phase builds against a tree missing the earlier ones; fails quietly |
| A paste line with no worktree clause | The run commits straight onto the default branch, inside Ryan's own checkout, overnight |
| A paste line carrying `~` paths, an unresolved symlink, or a leftover placeholder | The fresh session cannot find the brief it was told to follow, and improvises from the sentence alone |
| Assuming the default branch is `main`, or cutting from a stale local copy of it | Breaks outright on a `master`/`develop` repo, or lands the whole run on a base weeks behind origin |
| A new worktree used before its install | The first gate fails on missing dependencies and reads as a code failure |
| Building from a stale copy of the plan | Implements a superseded fix; the cite that was corrected is the one it follows |
| Dropping the plan's unknowns | Run "fixes" a bug the report was never about, and closes it |
| "Run the tests" with no command or baseline | Any red result reads as catastrophe or gets ignored |
| No stop conditions | Run guesses on the one question that needed a human |
| Leaving publish/push/merge unqualified | An unattended run does something outward-facing |
| Writing the brief into the repo | Plan docs get committed, against house rules |
| A paste line naming a trigger this session doesn't have | The brief is dead on arrival; nothing runs at all |
| Sweeping without the build-identity gate | "Verified" against a stale bundle or a second server on the same port |
| No attempt cap, or a third attempt that patches instead of diagnosing | Patches forever against a wrong model of the bug |
| Fixing out-of-scope bugs the sweep surfaced | Unattended scope creep, in a diff nobody watched grow |
| Writing `timeout 900 …`, or no time box at all | No such binary on macOS; and one hang costs the whole window |
| Gate helpers left to run under zsh | zsh doesn't word-split, so a multi-file gate collapses to one bogus path and reports "no tests found" — which reads as green |
| An unquoted `$RUN_DIR` | The plans vault path contains spaces; the evidence write lands somewhere else or fails silently |
| Treating "the CDP port answers" as a working browser | Sweeps run against a dead renderer and report false negatives all night |
| Relaunching the browser until it works | Forty headless Chromes by morning, nothing verified |
| Killing or tearing down a process the run didn't start | Takes down Ryan's browser, or another session's dev server |
| No teardown, or `pkill -f chrome` as the teardown | Either leaks until the machine chokes, or kills everything he had open |
| Evidence written to `/tmp`, or a teardown that deletes it | The night's only proof is gone before it's read |
| A findings log that skips passing sweeps, or omits out-of-scope finds | No way to tell which phase broke what; the bugs the sweep found are lost |
| Writing the post from memory instead of `/mr-markdown` | Claims drift from the diff that actually landed |
| Posting mid-plan on a bundled `ivtg-*` fix set | Partial claims about fixes whose siblings are still red |
| A post over its ceiling, or a per-wave post with nothing substantial | The loop's only output goes unread, or the next real one gets skimmed |
| Compressing the post or the findings log | Tokens saved by making the only output Ryan reads useless |
| A prompt that lets an agent narrate, or points at a file instead of quoting it | Pays for preamble and re-reads on every phase, every attempt |
| The full suite as a scheduled gate, per attempt, phase, or wave | Hours of re-proving untouched code; the loop spends the night in the test runner |
| A single test file as the only gate | Misses what the change broke in the modules that import it |
| Re-running a suite to reproduce one failing case | Minutes per attempt to learn what the sweep already reported |
| Comparing a targeted run against a full-suite baseline | A green subset reads as a green repo |
| An escalation full-suite run with no log entry saying why | The one expensive run nobody can account for afterwards |

## Red flags

- **You're about to write an expected result Ryan never said.** If you cannot quote him or name the contract it comes from, you are guessing. Stop and ask.
- **You caught yourself thinking "obviously it should…".** That is the assumption. Ask anyway; the obvious ones are cheap to confirm and are exactly where the wrong build comes from.
- **You're about to write `EXPECTED` by describing what the probe showed.** That is `CURRENT`. You have not specified anything yet.
- **You took an expected *value* from the implementation** — a constant, a shape, an existing string. The spec is now a tautology whatever order it was written in.
- **Every requirement in the brief came out as `behavior-red`.** Real plans contain refactors and invariants. A uniform mode usually means the modes were not considered.
- **A spec passed on the first run, before any implementation.** Do not bank it. Name which of the three reasons applies.
- **The fix loop is on attempt 2 and the spec is starting to look wrong to you.** Decide honestly which kind of wrong: mechanical (fix it, log it, re-validate) or semantic (stop). "It's basically mechanical" at attempt 3 is how the scheme dies.
- **A requirement has no row in the traceability matrix.** It has no gate, whatever the acceptance rows claim.
- You're about to write "as discussed" or "as above" — the fresh session has neither.
- You can't name the branch. Stop and resolve it; don't write "the feature branch".
- The brief has no stop conditions. Every unattended run needs an exit that isn't "finish anyway".
- You're about to write "verify visually" or "check with Ryan that it renders" — name the sentinel, the selector, and the expected text instead.
- You can't say which string proves a phase landed. That phase has no verification yet, whatever the brief claims.
- A process gets started in the brief and never appears again. Ledger it, or it survives the run.
- A phase step reads "start the browser". It starts once, before phase 1, and every later phase reuses it.
- An overnight run with no note about the machine staying awake. `/loop` dies with the lid.
