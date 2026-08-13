---
name: loop-me-in
description: Use when a fix plan, spec, or design doc needs to become a file that a fresh session can execute unattended — "make this runnable", "turn this plan into a loop", "so I can paste it and let it rip". Trigger: /loop-me-in [path].
---

# loop-me-in — a plan in, a self-driving brief out

## Overview

A plan is written for a reader who already has the context. A runnable brief is written for a session that has none: fresh window, no transcript, no memory of which worktree, which trap, which decision was already settled.

**Core principle: the output must survive being pasted into an empty session.** Anything the plan leaves implicit — the repo, the branch, the environment trap that eats an hour — has to be on the page, or the run rediscovers it the expensive way.

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
4. **Pick the trigger** (see table below).
5. **Write the brief to `~/.claude/plans/YYYY-MM-DD/<source-name>-run.md`** — resolve that symlink and say the real path in your report, so a wrong target is caught immediately. Never into a repo; plan files are not committed.

   **Vault trap:** an iCloud-nested duplicate of the plans vault can exist (`…/Obsidian/Obsidian/Claude Plans` beside the real `…/Obsidian/Claude Plans`), and the source plan may be handed to you as a path inside the *duplicate*. Do not infer the destination from where the source file sits, and do not infer it from the symlink alone. If both directories exist, name both and ask which is live before writing.
6. **Report the path and the paste line.** That's the deliverable.

## Choosing the trigger

| Plan shape | Trigger | Why |
|---|---|---|
| Multiple phases/tasks, each with its own verification | `/loop` | Self-paces on device; survives a phase failing without losing the rest |
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

## Phases
Numbered. Each carries: the change, the files, the verification command,
and what "done" looks like. One phase = one commit = one reviewable unit.

## Gates
The exact command line per repo. The known-good baseline (test count, lint
warning count) so drift is visible.

## Open questions — resolve or report
Every unknown the plan flags, carried over verbatim in substance. Mark which
must be answered BEFORE a phase runs, and which just ride into the final
report. Never let one be silently assumed away.

## Wave reporting (only if the user asked for it)
Where to post, what counts as a wave, the word cap, and the rule that a
blocked wave still reports.

## Commit and safety rules
What may be committed, by whom. What needs explicit human OK: pushes,
publishes, releases, merges, migrations against real data, anything
outward-facing.

## Stop conditions
The situations where the run must stop and report instead of deciding:
ambiguity the plan didn't settle, a product decision, a second failure of
the same kind, work that would widen scope.
```

## Rules for the brief you write

- **Copy facts, don't cite them.** "See the handoff" fails in a fresh session. Paste the constraint.
- **Every phase ends in a verification command**, not "check it works".
- **State the baseline numbers.** "5,781 tests, 0 fail; lint 42 warnings, 0 errors" turns an ambiguous red run into an obvious regression.
- **Name the known flakes.** Otherwise the run treats one as a real failure and starts patching.
- **Decisions already made go in as decisions**, not options. A brief that reopens a settled question wastes the run.
- **Scope fences are explicit.** Say what must NOT be touched; that is where autonomous runs do their damage.
- **Verification is quantitative.** A command plus an expected number, not "looks right". If a check is manual today, say so — a check the run can't perform is a stop condition, not a phase.
- **Pilot before the long run.** Tell the brief to execute phase 1 and report before continuing, when the plan is large or the repo is unfamiliar.
- **Feed lessons back.** If the run discovers a trap, it belongs in the plan's Environment traps for next time — fixing the instance without recording it means the next run pays again.

### If the user wants wave reports

Unattended runs are silent by default, so a progress channel is often worth it. When asked for one:

- **Verify the destination before writing the brief**, don't transcribe what the user said. Chat IDs are not always room names — `room_post` wants a canonical room name, and an ID may be a grant resource or a topic. Call `session_grants` (read-only, no consent side effects) and use the resource string it reports.
- **Confirm the capability exists.** No `post` grant means the run will stall mid-wave asking for consent; say so now rather than letting it discover that at 3am.
- **Define what a wave IS** in commits and gates — "wave complete" must mean *committed and green*, or the run reports work that doesn't hold up.
- **Cap the length and say to count.** A word limit stated without "count them" produces 60-word messages.
- **A blocked wave still posts.** Silence reads as progress; that is the failure mode worth designing out.
- **Never let a post claim what the run cannot verify.** If a check is manual, the message says so explicitly.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Linking the spec instead of copying its constraints | Fresh session can't see it; invents its own interpretation |
| Omitting the worktree path | Run edits the checkout another session is using |
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
