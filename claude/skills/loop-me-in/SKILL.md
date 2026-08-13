---
name: loop-me-in
description: Use when a fix plan, spec, or design doc needs to become a file that a fresh session can execute unattended and prove its own changes landed — "make this runnable", "turn this plan into a loop", "so I can paste it and let it rip". Trigger: /loop-me-in [path].
---

# loop-me-in — a plan in, a self-driving brief out

## Overview

A plan is written for a reader who already has the context. A runnable brief is written for a session that has none: fresh window, no transcript, no memory of which worktree, which trap, which decision was already settled.

**Core principle: the output must survive being pasted into an empty session.** Anything the plan leaves implicit — the repo, the branch, the environment trap that eats an hour — has to be on the page, or the run rediscovers it the expensive way.

**Second principle: the brief closes its own loop.** It builds, drives the real product, decides for itself whether the change landed, fixes what it finds, and re-checks — until green or until it hits a stated cap. Ryan is not the verification step.

**A finished brief has exactly two human touchpoints:**

1. A **blocking decision** the plan did not settle — a product call, an ambiguity, a question the run cannot answer from the page.
2. **Deployment** — the cherry-pick, push, merge, or release into main.

Everything between those is the run's job, commits on its own branch included. A brief that ends with "confirm it looks right" has not been converted; it has been reformatted.

## When to use

- A `/ivtg` fix plan, a `superpowers:writing-plans` plan, or any dated plan in the vault is approved and ready to execute.
- You want to hand execution to a session you won't babysit.
- Symptoms: the plan says "then fix it" without naming the branch; it assumes a tool that 404s; it was written before three decisions that have since been made; the last run kept pulling you back in to confirm whether a change had actually landed.

**Don't use for:** a plan still under discussion (run `/demuddy` first), or a one-line change you'd just do.

## Procedure

1. **Read the whole plan** — including the sections that aren't instructions. Also read anything it cites as spec-of-record. The brief must stand alone, so facts have to be copied in, not linked.

   **Mine the "Risks & unknowns" / "Open questions" section hardest.** It is the one a brief reliably drops, because it contains no steps to transcribe — and it is where "does this fix even address the report?" lives. A `/demuddy` pass concentrates exactly these into one clean section, which makes them easier to skip and more expensive to skip.

   **If the plan exists in more than one copy, diff them before building.** A duplicate vault, an older draft, a pre-review version: they can differ by hundreds of lines and by which fix is correct. Build from the copy the user names, and say in the brief how to recognise a stale one.
2. **Resolve the environment, don't assume it.** For every repo the plan touches, establish and write down: exact worktree path, branch name and base, whether the tree is clean, how deps are installed, and the verification command. Check these — a stale path is the single most common way these runs die.
3. **Harvest the traps.** Every "don't do X, it breaks Y" you know: package managers that 404, files that must be regenerated rather than hand-merged, test harnesses with sharp edges, suites that OOM. A trap costs one line here and an hour there.
4. **Design the verify loop.** Pick the harness, resolve the surface (command, port, URL), and give every phase acceptance rows and a sentinel. Do this while you still have the plan open — retrofitting acceptance rows onto a written brief is how they end up as "check the page renders".
5. **Ask where it reports.** Do not infer the channel or topic from the plan's subject. Ask the user to paste the destination — channel, and topic if the work belongs to one — once per area if the plan splits across several. Resolve what they paste to a canonical resource string and write that into the brief.
6. **Pick the trigger** (table below).
7. **Write the brief to `~/.claude/plans/YYYY-MM-DD/<source-name>-run.md`** — resolve that symlink and say the real path in your report, so a wrong target is caught immediately. Never into a repo; plan files are not committed.

   **Vault trap:** an iCloud-nested duplicate of the plans vault can exist (`…/Obsidian/Obsidian/Claude Plans` beside the real `…/Obsidian/Claude Plans`), and the source plan may be handed to you as a path inside the *duplicate*. Do not infer the destination from where the source file sits, and do not infer it from the symlink alone. If both directories exist, name both and ask which is live before writing.
8. **Report the path and the paste line.** That's the deliverable.

## The verify loop

The brief verifies itself. Manual confirmation is not a phase, not a gate, and not a completion criterion.

Commands, prompts, the sweep output contract, and the exact codex invocations live in `references/verify-loop.md`. **Copy the resolved commands into the brief** — a fresh session will not read that file.

### Pick the harness

| Target | Harness | Why |
|---|---|---|
| Any web UI served from the worktree | A codex agent driving the `chrome-devtools` CDP script | Headless-capable, scriptable, no interactive consent, works against any localhost surface |
| The OM Chat GUI | `/om-chat-web` | Already carries `doctor` (is the daemon actually serving the working tree?), saved logins, and a cloud-vs-local pixel-diff report |
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
build → identity gate → sweep → all acceptance rows landed, no in-scope regressions?
                                  ├─ yes → review diff, commit, next phase
                                  └─ no  → fix agent → attempt += 1 → back to build
```

The sweep returns a fixed shape — verdict per acceptance row with the evidence, regressions seen en route, in-scope gaps with a file guess, out-of-scope findings left alone, and the single question that would need a human. The out-of-scope slot is what keeps an unattended run from wandering: those findings get recorded and reported, not fixed.

**Every sweep appends to a findings log, and the evidence outlives the run.** Screenshots, raw console and network captures, per-sweep verdicts, and the appended log all live in one directory beside the brief in the plans vault — never in `/tmp`, which a reboot clears. Teardown kills processes; it never deletes that directory. Passing sweeps get an entry too: a log that records only failures can't show that phase 2 was green before phase 5 broke it. The out-of-scope findings are the reason the file exists — a post capped at 40–100 words will not carry them, and they are exactly what a browser sweep is uniquely good at noticing.

**Cap at 3 sweeps per phase.** On the third failure the phase stops, stays red in the report, and the run moves to the next phase that does not depend on it. Two failures of the same class mean the model of the problem is wrong; a fourth patch makes it worse.

**Every codex run and every browser command is time-boxed.** A hung agent costs the whole night. macOS has no `timeout` binary — the brief defines a `with_timeout` helper instead (`references/verify-loop.md`, section 0), or the first phase dies on `command not found`.

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

Every brief reports to OM Chat over the `openmarket-chat` MCP tools, unless the work is unshippable or the user says not to. An unattended run is otherwise silent, and silence reads as progress.

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
- **The destination comes from the user, the resource string comes from the server.** They paste the channel and topic (procedure step 5); `session_grants` (read-only, no consent side effects) confirms it and yields the canonical resource string that goes in the brief — `room_post` wants that, not a display title. `82eae63a1bd3` (`#chat`, space `openmarket`) is the default when they don't name one. Verify the `post` capability while writing: a missing grant means the run stalls at 3am waiting for consent.
- **Route to the right topic.** Where the work belongs to a topic, list them with `room_topic_list` and confirm the posting tool's schema advertises the topic field before assuming it takes one. Creating a topic needs `contribute` on the room — knock for it while writing the brief. If more than one channel is in scope, the brief names each destination against the phases it covers.
- **`room_post` posts as the bot. `om room say` posts as Ryan.** Say which.
- **It may only claim what was verified.** Backend work a browser cannot show, and any fix whose link to the original report is still an open question, must be worded honestly or left out.
- **It names the findings log path.** The word ceiling is what keeps the post readable; the path is what keeps the detail reachable. One line, and everything the sweeps saw is a click away.
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

**`/loop` runs on this machine.** Sleep, shutdown, or a closed lid stops it mid-phase, which for an overnight run means waking up to a half-applied plan and a leaked browser. Say so in the brief when the run is expected to go long: either the machine stays awake, or the work belongs in `/schedule`.

**Always give the brief a turn cap or phase count.** An unbounded loop burns tokens on work nobody is reading. State the ceiling and what to do on hitting it: report, don't continue.

## The brief's required shape

Write these sections, in this order. Each is a slot to fill, not a suggestion.

```markdown
# <Name> — runnable brief
Paste line: /loop <one sentence naming the work>
(no interval — self-paced. Runs locally: keep the machine awake.)

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
port, URL), how the browser starts and how it is reused, the smoke test, the
two-part identity gate, the sweep and fix agent invocations, and the sweep
output contract. Attempt cap: 3 sweeps per phase. The `with_timeout` helper,
defined here and used on every long-running command.

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

## Stop conditions
The situations where the run must stop and report instead of deciding:
ambiguity the plan didn't settle, a product decision, a second failure of
the same kind, a third failed sweep on one phase, a browser that will not come
up healthy, work that would widen scope.
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
- **One worktree per repo, one branch, for the whole run.** Say it explicitly and forbid `git worktree add` and per-phase checkouts. Phases stack as commits on one branch. A fresh session will otherwise isolate a phase and build against a tree missing the earlier phases' changes — which fails quietly, not loudly. Name the phase pairs that touch the same file, so the ordering constraint is visible.
- **Pilot before the long run.** Tell the brief to execute phase 1 and report before continuing, when the plan is large or the repo is unfamiliar.
- **Feed lessons back.** If the run discovers a trap, it belongs in the plan's Environment traps for next time — fixing the instance without recording it means the next run pays again.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Linking the spec instead of copying its constraints | Fresh session can't see it; invents its own interpretation |
| Omitting the worktree path | Run edits the checkout another session is using |
| Not forbidding per-phase worktrees | A later phase builds against a tree missing the earlier ones; fails quietly |
| Building from a stale copy of the plan | Implements a superseded fix; the cite that was corrected is the one it follows |
| Dropping the plan's unknowns | Run "fixes" a bug the report was never about, and closes it |
| "Run the tests" with no command or baseline | Any red result reads as catastrophe or gets ignored |
| No stop conditions | Run guesses on the one question that needed a human |
| Leaving publish/push/merge unqualified | An unattended run does something outward-facing |
| Writing the brief into the repo | Plan docs get committed, against house rules |
| Sweeping without the build-identity gate | "Verified" against a stale bundle or a second server on the same port |
| No attempt cap on the fix/re-sweep cycle | Patches forever against a wrong model of the bug |
| Fixing out-of-scope bugs the sweep surfaced | Unattended scope creep, in a diff nobody watched grow |
| No time box on codex or browser commands | One hang costs the entire unattended window |
| Writing `timeout 900 …` in the brief | No such binary on macOS; every phase dies on `command not found` |
| Treating "the CDP port answers" as a working browser | Sweeps run against a dead renderer and report false negatives all night |
| Relaunching the browser until it works | Forty headless Chromes by morning, nothing verified |
| Killing or tearing down a process the run didn't start | Takes down Ryan's browser, or another session's dev server |
| No teardown, or `pkill -f chrome` as the teardown | Either leaks until the machine chokes, or kills everything he had open |
| Writing the post from memory instead of `/mr-markdown` | Claims drift from the diff that actually landed |
| Posting mid-plan on a bundled `ivtg-*` fix set | Partial claims about fixes whose siblings are still red |
| A per-wave post on a wave with nothing substantial | Noise, and the next real report gets skimmed |
| A post over its ceiling — 100 words bundled, 40 per wave | The loop's only output goes unread |
| A paste line naming a trigger this session doesn't have | The brief is dead on arrival; nothing runs at all |
| An overnight `/loop` with no note that it dies with the machine | Half-applied plan and a leaked browser by morning |
| Evidence written to `/tmp`, or a teardown that deletes it | The night's only proof is gone before it's read |
| Out-of-scope findings that live only in the post | The word cap eats them; the bugs the sweep found are lost |
| A findings log that records only failed sweeps | No way to tell which phase broke something that used to pass |

## Red flags

- You're about to write "as discussed" or "as above" — the fresh session has neither.
- You can't name the branch. Stop and resolve it; don't write "the feature branch".
- The brief has no stop conditions. Every unattended run needs an exit that isn't "finish anyway".
- You're about to write "verify visually" or "check with Ryan that it renders" — name the sentinel, the selector, and the expected text instead.
- You can't say which string proves a phase landed. That phase has no verification yet, whatever the brief claims.
- A process gets started in the brief and never appears again. Ledger it, or it survives the run.
- A phase step reads "start the browser". It starts once, before phase 1, and every later phase reuses it.
