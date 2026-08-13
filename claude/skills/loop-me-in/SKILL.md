---
name: loop-me-in
description: Use when a fix plan, spec, or design doc needs to become a file that a fresh session can execute unattended and prove its own changes landed — "make this runnable", "turn this plan into a loop", "so I can paste it and let it rip". Trigger: /loop-me-in [path].
---

# loop-me-in — a plan in, a self-driving brief out

## Overview

A plan is written for a reader who already has the context. A runnable brief is written for a session that has none: fresh window, no transcript, no memory of which worktree, which trap, which decision was already settled.

**Core principle: the output must survive being pasted into an empty session.** Anything the plan leaves implicit — the repo, the branch, the environment trap that eats an hour — has to be on the page, or the run rediscovers it the expensive way.

**Second principle: the brief closes its own loop.** It builds, drives the real product, decides for itself whether the change landed, fixes what it finds, and re-checks — until green or until it hits a stated cap. Ryan is not the verification step.

**There are exactly two human touchpoints in a finished brief:**

1. A **blocking decision** the plan did not settle — a product call, an ambiguity, a question the run cannot answer from the page.
2. **Deployment** — the cherry-pick, push, merge, or release into main.

Everything between those is the run's job, commits on its own branch included. A brief that ends with "confirm it looks right" has not been converted; it has been reformatted.

## When to use

- A `/ivtg` fix plan, a `superpowers:writing-plans` plan, or any dated plan in the vault is approved and ready to execute.
- You want to hand execution to a session you won't babysit.
- Symptoms that you need this: the plan says "then fix it" without naming the branch; it assumes a tool that 404s; it was written before three decisions that have since been made.

**Don't use for:** a plan still under discussion (run `/demuddy` first), or a one-line change you'd just do.

## Procedure

1. **Read the whole plan** — including the sections that aren't instructions. Also read anything it cites as spec-of-record. The brief must stand alone, so facts have to be copied in, not linked.

   **Mine the "Risks & unknowns" / "Open questions" section hardest.** It is the one a brief reliably drops, because it contains no steps to transcribe — and it is where "does this fix even address the report?" lives. A `/demuddy` pass tends to concentrate exactly these into one clean section, which makes them easier to skip and more expensive to skip.

   **If the plan exists in more than one copy, diff them before building.** A duplicate vault, an older draft, a pre-review version: they can differ by hundreds of lines and by which fix is correct. Build from the copy the user names, and say in the brief how to recognise a stale one.
2. **Resolve the environment, don't assume it.** For every repo the plan touches, establish and write down: exact worktree path, branch name and base, whether the tree is clean, how deps are installed, and the verification command. Check these — a stale path is the single most common way these runs die.
3. **Harvest the traps.** Every "don't do X, it breaks Y" you know: package managers that 404, files that must be regenerated rather than hand-merged, test harnesses with sharp edges, suites that OOM. A trap costs one line here and an hour there.
4. **Design the verify loop.** Pick the harness, resolve the surface (command, port, URL), and give every phase acceptance rows and a sentinel. See "The verify loop" below. Do this while you still have the plan open — retrofitting acceptance rows onto a written brief is how they end up as "check the page renders".
5. **Pick the trigger** (see table below).
6. **Write the brief to `~/.claude/plans/YYYY-MM-DD/<source-name>-run.md`** — resolve that symlink and say the real path in your report, so a wrong target is caught immediately. Never into a repo; plan files are not committed.

   **Vault trap:** an iCloud-nested duplicate of the plans vault can exist (`…/Obsidian/Obsidian/Claude Plans` beside the real `…/Obsidian/Claude Plans`), and the source plan may be handed to you as a path inside the *duplicate*. Do not infer the destination from where the source file sits, and do not infer it from the symlink alone. If both directories exist, name both and ask which is live before writing.
7. **Report the path and the paste line.** That's the deliverable.

## The verify loop

The brief verifies itself. Manual confirmation is not a phase, not a gate, and not a completion criterion.

### Pick the harness

| Target | Harness | Why |
|---|---|---|
| Any web UI served from the worktree | A codex agent driving the `chrome-devtools` CDP script | Headless-capable, scriptable, no interactive consent, works against any localhost surface |
| The OM Chat GUI | `/om-chat-web` | Already carries `doctor` (is the daemon actually serving the working tree?), saved logins, and a cloud-vs-local pixel-diff report |
| Backend, CLI, library | A command with an expected value | A browser check that proves nothing is worse than admitting the check is a command |

`claude-in-chrome` is the wrong tool here: per-site permission grants and Ryan's real profile mean the run stalls at 3am waiting for consent.

### The gate that makes it definitive

Every sweep opens with a **build-identity gate**, in two parts:

- the process listening on the app's port has its `cwd` inside this worktree, and
- a **sentinel** — a string that exists only after this phase's change — reaches the served output.

Both pass or the sweep is void. A void sweep is recorded as *not verified* and the run rebuilds and re-gates; it is never recorded as *not landed*. Without this, a stale bundle or a second dev server on the same port turns "verified" into "clicked around something".

Name a sentinel per phase while writing the brief: a new `data-testid`, a new route, a new label. A phase with no observable sentinel gets a command gate instead, and the brief says so.

### The loop

```
build → identity gate → sweep → all acceptance rows landed, no in-scope regressions?
                                  ├─ yes → review diff, commit, next phase
                                  └─ no  → fix agent → attempt += 1 → back to build
```

The sweep returns a fixed shape — verdict per acceptance row with the evidence, regressions seen en route, in-scope gaps with a file guess, out-of-scope findings left alone, and the single question that would need a human. The out-of-scope slot is what keeps an unattended run from wandering: findings get recorded and reported, not fixed.

**Cap at 3 sweeps per phase.** On the third failure the phase stops, stays red in the report, and the run moves to the next phase that does not depend on it. Two failures of the same class mean the model of the problem is wrong; a fourth patch makes it worse.

**Every codex run and every browser command is wrapped in `timeout`.** A hung agent costs the whole night.

Commands, prompts, the output contract, and the exact codex invocations: `references/verify-loop.md`. **Copy the resolved commands into the brief** — a fresh session will not read that file.

### Process ledger and teardown

Anything the run starts that outlives one command — dev server, Chrome, background codex — is recorded at spawn with its claimed port and PID, in a `## Process ledger` section the run appends to.

- **Between phases, a heartbeat:** app URL answers, CDP endpoint answers, no `codex exec` still running, no stopped background jobs. Anything stuck is killed and restarted, not waited on.
- **Teardown runs on success, failure, and abort.** Kill by ledger PID; `pgrep` only to confirm nothing survived.
- Chrome gets a dedicated `--user-data-dir` and a claimed debugging port so teardown can be precise. A bare `pkill -f chrome` would take Ryan's own browser with it — the brief must never contain one.

## Choosing the trigger

| Plan shape | Trigger | Why |
|---|---|---|
| Multiple phases/tasks, each with its own verification | `/loop` with no interval | Self-paces, which is what a build → sweep → fix cycle needs; survives a phase failing without losing the rest |
| One fix with a single verifiable done-condition | `/goal <condition>` | Runs until the goal is met or the turn cap is hit |
| Recurring work, or work that must outlive the session | `/schedule` | Runs in the cloud rather than this terminal |
| Small enough to just do | None — say so | Not everything needs a loop; the simplest thing that works wins |
| Phases that each need a human decision | None — say so | A loop that stops every phase to ask is worse than a checklist |

**Always give the brief a turn cap or phase count.** An unbounded loop burns tokens on work nobody is reading. State the ceiling and what to do on hitting it (report, don't continue).

## The brief's required shape

Write these sections, in this order. Each is a slot to fill, not a suggestion.

```markdown
# <Name> — runnable brief
Paste line: /loop <one sentence naming the work>

## Ground truth
Repos and worktrees (path, branch, base, clean?), the spec-of-record path,
what already landed (commit shas), what is deliberately NOT in scope.
One branch per repo, one worktree for the whole run.

## Environment traps
One line each. Install commands that break things. Files that must be
regenerated rather than edited. Test-harness sharp edges. Known flakes and
their names, so a red suite isn't misread as a regression.

## Verification loop
The harness and its exact commands: how the surface starts (command, claimed
port, URL), how Chrome starts (dedicated profile dir, debugging port), the
two-part identity gate, the sweep agent invocation, the fix agent invocation,
and the sweep output contract. Attempt cap: 3 sweeps per phase.
Every long-running command wrapped in `timeout`.

## Process ledger
Empty table the run fills in as it spawns things: what, port, PID, started.
Plus the heartbeat check to run between phases, and the teardown block that
runs on success, failure, and abort alike.

## Phases
Numbered. Each carries: the change, the files, the sentinel that proves it
reached the served output, the acceptance rows the sweep must return a verdict
on, the command gate, and what "done" looks like.
One phase = one commit = one reviewable unit.

## Gates
The exact command line per repo. The known-good baseline (test count, lint
warning count) so drift is visible. The browser gate is the sweep, and it is
green only when every acceptance row reads landed with evidence attached.

## Open questions — resolve or report
Every unknown the plan flags, carried over verbatim in substance. Mark which
must be answered BEFORE a phase runs, and which just ride into the final
report. Never let one be silently assumed away.

## Completion post
Destination, when it fires, the word cap, and what it may not claim.

## Commit and safety rules
Authorised without asking: commits on the run's own branch, the verify sweeps,
the completion post. Needs explicit human OK: push, merge, cherry-pick into
main, publish, release, migrations against real data, anything else
outward-facing. Codex agents never commit — the run reviews the diff, stages,
and commits via the `/commit` skill.

## Stop conditions
The situations where the run must stop and report instead of deciding:
ambiguity the plan didn't settle, a product decision, a second failure of
the same kind, a third failed sweep on one phase, work that would widen scope.
Everything else: keep going. Do not stop to ask whether it looks right.
```

## Rules for the brief you write

- **Copy facts, don't cite them.** "See the handoff" fails in a fresh session. Paste the constraint.
- **Every phase ends in a verification command**, not "check it works".
- **State the baseline numbers.** "5,781 tests, 0 fail; lint 42 warnings, 0 errors" turns an ambiguous red run into an obvious regression.
- **Name the known flakes.** Otherwise the run treats one as a real failure and starts patching.
- **Decisions already made go in as decisions**, not options. A brief that reopens a settled question wastes the run.
- **Scope fences are explicit.** Say what must NOT be touched; that is where autonomous runs do their damage.
- **Verification is quantitative.** A command plus an expected number, not "looks right". A check the run genuinely cannot perform — hardware, a third-party account, a human judgement call — is a stop condition, not a phase. "Ryan will look at it" is not one of those.
- **Every phase names its sentinel.** Without a string that only exists after the change, the sweep cannot tell a landed change from a cached bundle.
- **The sweep reports gaps, the run fixes them, the sweep runs again.** Bugs found during a sweep are the loop's input, not a footnote in the final report — with the scope fence deciding which get fixed now and which get recorded.
- **Every spawned process is in the ledger, and teardown is unconditional.** Chrome and dev servers leak silently: nothing fails, they just sit there eating memory until the machine is unusable.
- **Heartbeat between phases.** A dead dev server, a detached CDP endpoint, or a codex run past its timeout turns the rest of the night into no-ops that look like progress.
- **One worktree per repo, one branch, for the whole run.** Say it explicitly and forbid `git worktree add` and per-phase checkouts. Phases stack as commits on one branch. A fresh session will otherwise isolate a phase and build against a tree missing the earlier phases' changes — which fails quietly, not loudly. Name the phase pairs that touch the same file, so the ordering constraint is visible.
- **Pilot before the long run.** Tell the brief to execute phase 1 and report before continuing, when the plan is large or the repo is unfamiliar.
- **Feed lessons back.** If the run discovers a trap, it belongs in the plan's Environment traps for next time — fixing the instance without recording it means the next run pays again.

### The completion post — include by default

Every brief ends with one post to OM Chat, unless the work is unshippable or the user says not to. An unattended run is otherwise silent, and silence reads as progress.

- **Fires once, after the verify loop is green** — not after the last commit. Green means every acceptance row came back landed with evidence, on a sweep whose identity gate passed. A phase that hit the attempt cap is reported as red, not omitted.
- **The post is what replaces Ryan watching.** It carries the verdict per phase, what is still red, and the gaps recorded but deliberately not fixed. A post that only says "done" makes the whole loop unfalsifiable.
- **Resolve the destination, don't transcribe it.** Call `session_grants` (read-only, no consent side effects) and use the resource string it reports; `room_post` wants that canonical name, not a display title. Currently that is `82eae63a1bd3` (`#chat`, space `openmarket`) with `read` + `post`. Confirm rather than assume — a missing `post` grant means the run stalls at 3am waiting for consent.
- **`room_post` posts as the bot. `om room say` posts as Ryan.** Say which.
- **Shape: a simplified `/mr-markdown` summary — one title line, at most 4 bullets, 100 words total. Tell the brief to count them**; a cap stated without counting produces a message well under it.
- **It may only claim what was verified.** Backend work a browser cannot show, and any fix whose link to the original report is still an open question, must be worded honestly or left out.
- **A blocked run still posts** — what landed, what failed, that the rest is halted.
- **Authorise exactly this one outward-facing action** in the safety rules, so "post" does not read as permission to push or publish.

Per-wave progress reports are a variant: only when asked, and "wave complete" must mean committed *and* green.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Linking the spec instead of copying its constraints | Fresh session can't see it; invents its own interpretation |
| Omitting the worktree path | Run edits the checkout another session is using |
| Not forbidding per-phase worktrees | A later phase builds against a tree missing the earlier ones; fails quietly |
| A post that claims more than the run verified | A green-looking message for work nobody confirmed |
| "Run the tests" with no command or baseline | Any red result reads as catastrophe or gets ignored |
| Leaving publish/push/merge unqualified | An unattended run does something outward-facing |
| No stop conditions | Run guesses on the one question that needed a human |
| Dropping the plan's unknowns | Run "fixes" a bug the report was never about, and closes it |
| Building from a stale copy of the plan | Implements a superseded fix; the cite that was corrected is the one it follows |
| Writing the brief into the repo | Plan docs get committed, against house rules |

## Red flags

- You're about to write "as discussed" or "as above" — the fresh session has neither.
- You can't name the branch. Stop and resolve it; don't write "the feature branch".
- The brief has no stop conditions. Every unattended run needs an exit that isn't "finish anyway".
