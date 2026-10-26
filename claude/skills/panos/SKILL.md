---
name: panos
description: Use when MRs Ryan opened or pushed have landed on GitLab and need the review Panos (pan26, the usual blocking backend reviewer) would give, before Panos sees them — "review this like Panos", "assume you are Panos", "now that the work has landed, review and fix it". Trigger: /panos [MR ...] [--model MODEL].
---

# panos — review landed MRs as Panos, fix what is real

## Overview

Panos (`pan26`) is the usual blocking reviewer of the go-backend repos. This
skill gives each MR that review first: codex reviews it under the Panos brief,
you verify every finding against the code, fix the real ones on the MR's
branch, push, and report. Nothing is ever posted on the MR.

The reviewer is codex `gpt-6.1-sol` at `xhigh` unless `--model` names another
codex model.

## Hard rules

- Invoking `/panos` authorizes pushes to each selected MR's source branch, and
  nothing else. Never push to a target or default branch. Every force push is
  `--force-with-lease=<source>:<head recorded in Phase 0>`.
- Never write to the MR: no notes, replies, approvals, thread resolution,
  labels, reviewers or merge. Two exceptions: when a fix makes a sentence of
  the MR description false, correct that sentence; and Phase 5 may start a
  missing pipeline.
- Never touch production: no database, cluster or broker connections, no
  `connections.env`. A claim that needs prod numbers becomes a question for
  Ryan, with the measurement that would settle it.
- A reviewer finding is a hypothesis. Never fix one Phase 3 has not
  reproduced.
- Design changes go to Ryan, not into the branch: splitting an MR, moving a
  component to its own deployment, changing rollout or merge order, changing a
  public contract.
- If codex is missing, exits non-zero, times out (exit 124) or writes an empty
  review, show the log's tail and ask. Never retry on a different model.

## Phase 0 — pick the MRs

1. Arguments name MRs (`tsdb-gateway!2402`, a full path, or a URL): use
   exactly those.
2. Otherwise, the MRs this session opened or pushed to.
3. Otherwise, list Ryan's open MRs and ask with one `AskUserQuestion`
   (multiSelect).

```bash
bash ~/.claude/skills/panos/scripts/mrs.sh 'tsdb-gateway!2402' ...
```

Quote each ref (`!` expands in zsh) and pass only refs. The columns are in the
script header. An MR the script reports as not one of Ryan's open MRs: stop
and ask. Per MR:

- `path` is `-`: `git -C <clone> worktree add
  ~/Documents/GitLab/worktrees/<source with / as ->/<repo> <source>`, and say
  so.
- `local` must be `same`, with `fetch` = `ok`. `behind N`: `git merge
  --ff-only`. `ahead N`: the work has not landed, so ask whether to push first
  or review the local tip. `diverged`, `unknown`, `+dirty` or a failed fetch:
  stop for that MR and ask. Never stash, reset or discard.
- `behind` > 0: the MR is behind its target, so the review would run on a
  stale base and merge-time hazards stay hidden. Ask: `/syncup` first
  (recommend it when the diff touches migrations, generated files, `go.mod` or
  chart values), or review as is.
- Record `head`: it is the lease and the undo handle.

## Phase 1 — prepare each review

**Run dir:** if the work has a plan, its evidence dir is the one under
`~/.claude/plans` whose files mention the source branch (`grep -rl
'<source>' ~/.claude/plans`); use `<evidence dir>/panos/<YYYY-MM-DD-HHMM>/`.
Otherwise `<scratchpad>/panos/<YYYY-MM-DD-HHMM>/`.

**Siblings:** Ryan's open MRs with the same source branch, the MR this one is
stacked on, and the MRs whose branches this one pins in `go.mod`.

Per MR, with `<name>` = `<repo>-<iid>`:

```bash
glab api "projects/<pid>/merge_requests/<iid>" > <name>.json             # title, description, last pipeline
glab api "projects/<pid>/merge_requests/<iid>/versions" > <name>-versions.json  # [1].head_commit_sha = previous push
git -C <path> diff origin/<target>...HEAD > <name>.diff
python3 -I ~/.claude/skills/panos/scripts/threads.py <name>-threads.md --mr <pid> <iid>
```

The prompt is three parts, concatenated in this order:
`references/panos.md`, the block below, `references/contract.md`.

```
## This MR

<ref> — <title> (<source> → <target>), head <sha>
Worktree: <path>
Diff: <run dir>/<name>.diff
Threads: <run dir>/<name>-threads.md
Previous push: <sha> | none
Behind <target> by: <N>
Last pipeline: <status> at <sha> | none
Other MRs in this set: <ref → worktree, and how they depend on each other: pins, proto fields, stacking, merge order> | none
Infra and bare-metal config: ~/Documents/GitLab/infrastructure, ~/Documents/GitLab/meta_repo/streamd-cex-playbook
Already verified: <fact — source (this session, or the plan's evidence)> | none
Deliberately temporary, do not report: <e.g. a draft-only replace in go.mod> | none

Description:
~~~~
<MR description>
~~~~
```

A fresh session fills "Already verified" from the plan's evidence dir, with
the file each fact came from. MR-specific knowledge goes in this block, never
into an edited copy of the brief.

## Phase 2 — run the reviews

One codex run per MR, all in parallel, in the background:

```bash
mkdir -p "<run dir>/gocache"
GOCACHE="<run dir>/gocache" timeout 2400 codex exec -C "<path>" \
  -m "<model, default gpt-6.1-sol>" -c model_reasoning_effort=xhigh \
  --sandbox workspace-write --add-dir "<run dir>" \
  --output-last-message "<run dir>/review-<name>.md" \
  - < "<run dir>/prompt-<name>.md" > "<run dir>/review-<name>.log" 2>&1
```

The sandbox reads the whole disk, so sibling worktrees need no `--add-dir`;
adding them would make them writable. Expect 10–30 minutes per MR. When a run
ends, its worktree must be as clean as Phase 0 found it: delete leftover
`zz_panos_probe_*` files, and report anything else the reviewer changed
without discarding it.

## Phase 3 — verify each finding

Take the findings one at a time, before fixing any:

1. Read the cited code and trace the path. Is it reachable in production with
   the config each environment actually ships? Code nothing calls, or a
   setting no overlay sets, is not a defect.
2. Reproduce it. Behaviour in code: a failing test on the branch tip. Config,
   charts, migrations: the build, render or check that shows it, or a trace
   with `file:line` at each step.
3. Classify it:
   - **fix**: reproduced, and the fix stays inside this MR.
   - **decline**: refuted; keep one line of evidence and delete its repro
     files.
   - **needs sync**: only rebasing onto the target fixes it (a migration
     renumber, a view rebuilt on a stale body). Stop fixing that MR; it goes
     to Ryan with `/syncup`.
   - **Ryan**: real, but the fix is a design or rollout choice, or needs prod
     numbers.

Answer the reviewer's QUESTIONS from the code where you can; the rest go to
Ryan.

## Phase 4 — fix

Each fix starts from its Phase 3 test failing and ends with it passing. Keep
the change minimal and inside the MR's scope.

How fixes land:

- Draft MR with `others` = 0: fold each fix into the commit that introduced
  the code with `git commit --fixup=<sha>` (fixup commits are the one
  exception to committing through the commit skill), then
  `git rebase --autosquash "$(git merge-base origin/<target> HEAD)"`, which
  keeps the base where it is. `git range-diff <head>...HEAD` must show only
  your fixes. Push with the lease.
- Any other MR has been seen by someone: add new commits with the commit
  skill and push normally.

Before any push, run what CI runs. Read `.gitlab-ci.yml` and every file it
`include:`s (fetch remote includes with `glab api
"projects/<urlencoded project>/repository/files/<urlencoded path>/raw?ref=<ref>"`),
then run the same tasks locally, without their `--fix` flags. At minimum:

- Go: `go build ./...`, `go vet ./...`, tests for the touched packages,
  `go mod vendor` when the repo vendors, and `golangci-lint` over the module
  as CI runs it, never with `--new-from-rev`: CI lints whole functions, so a
  fix can push an unchanged function over gocyclo or nestif. Plus every other
  task CI runs, such as `log-linter` and `task migrations:check`.
- Frontend: typecheck, lint, and unit tests for the touched files.
- `go.mod` carries no `replace` to a local path, and every pin names a pushed
  SHA.
- When a fix changes something a sibling depends on (a pin, a proto field, a
  stacked base), update the sibling too.

To correct the MR description, write the full new text to a file and run
`glab mr update <iid> -R <group/project> --description-file <file>`. Without
`-R`, glab targets the repo of the current directory.

## Phase 5 — confirm the push

Check each remote head moved to the pushed SHA (`git ls-remote origin
<source>`). Then poll in the background until the pipeline for that SHA ends:

```bash
glab api "projects/<pid>/merge_requests/<iid>/pipelines?per_page=1"
```

If no pipeline exists for the SHA after a few minutes, start one once with
`glab api -X POST "projects/<pid>/merge_requests/<iid>/pipelines"`. An answer
of "The resulting pipeline would have been empty", or still no pipeline after
10 minutes, on an unapproved MR means CI is not configured to run yet
(tsdb-gateway runs MR pipelines only after approval): report "CI not run:
unapproved" and stop waiting. A failure your change caused goes back through
Phases 3–4; report any other.

## Phase 6 — report

Per MR, a table:

| # | Severity | Finding (`file:line`) | Outcome |
|---|---|---|---|

Outcome is `fixed in <sha>`, `declined: <evidence>`, `needs sync: <why>`, or
`for Ryan: <question>`.

Then: pushes (`branch old → new`), gates run, CI status, MR descriptions
changed, the merge order (say "unchanged" explicitly when it is), and MRs
behind their target (offer `/syncup`, never rebase here). End with "Nothing
was posted on any MR." Save the report as `<run dir>/report.md`.

## Refreshing the brief

`references/panos.md` is distilled from Panos's review threads on Ryan's MRs.
After Panos has reviewed new ones, collect every thread and fold any new lens
or catch into the brief:

```bash
python3 -I ~/.claude/skills/panos/scripts/threads.py <out.md>
```

## Common mistakes

- Fixing a finding because the reviewer sounded sure. A fix for a branch
  nothing calls adds code and review surface for nothing.
- `git rebase --autosquash origin/<target>`: on an MR that is behind, this
  silently rebases it onto the new target before the force push.
- `golangci-lint --new-from-rev` as the lint gate: CI then fails on the
  touched function's complexity.
- Resolving a rebase conflict in chart values by moving keys between blocks.
  After any rebase, diff `charts/**/values*.yaml` against the target.
- Leaving a local `replace` in `go.mod` at push time.
- Reporting "done" before the pipeline ends, or without the merge order.
