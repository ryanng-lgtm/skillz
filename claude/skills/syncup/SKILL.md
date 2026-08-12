---
name: syncup
description: Use when the user wants one or more local repos brought up to date with their default branch — refresh main from origin, rebase the working branch onto it, and resolve every conflict, including when the worktree has uncommitted changes. Trigger: /syncup [repo ...], "sync up my repos", "rebase everything on main", "get me on latest main".
---

# syncup — bring selected repos up to date with main

## Overview

For each selected repo: fast-forward the default branch from `origin`, rebase the checked-out
branch onto it, resolve every conflict, and hand uncommitted work back exactly as unstaged/staged
as it started. Repos are processed **one at a time, sequentially**, inline in the main thread —
never via subagents, because conflict resolution needs the full session context.

Default repo root: `~/Documents/GitLab`. Override with `--root DIR` or `SYNCUP_ROOT`.

## Hard rules

- **Never push.** Not `push`, not `--force-with-lease`. Rebasing rewrites history; publishing that
  is the user's call in a later turn.
- **Never `git stash`.** Dirty state travels as a temporary WIP commit (Phase 2). Reflog recovers a
  botched WIP commit; a botched stash pop is much worse.
- **Never `reset --hard`, `checkout -f`, `clean`, or `restore` on a repo with uncommitted work.**
- **Never `rebase --skip` on a commit that is not the WIP commit**, and never `--onto` anything the
  user did not name.
- Record every repo's pre-sync `HEAD` SHA *before* touching it. Those SHAs are the undo handles and
  must appear in the final report.
- Only touch the repos the user selected. Never widen the set, never touch submodules.
- Never edit `.git/config`, change remotes, or delete branches.
- If a repo cannot be finished safely, abort **that repo** back to its pre-sync state and keep going
  with the rest. Never leave a repo mid-rebase.

## Phase 0 — pick the repos

1. If the user passed repo names as arguments, use exactly those. Resolve each to a path under the
   root; if one does not resolve, ask for the path. Skip Phase 0.2.
2. Otherwise run the scanner:

   ```bash
   bash ~/.claude/skills/syncup/scripts/scan.sh
   ```

   It fetches all repos in parallel (~20–60s for a large root, `--no-fetch` to skip) and prints TSV:
   `name  branch  default  ahead  behind  dirty  state  path  fetch`. Only repos that need work are
   listed (`--all` includes clean ones).

   | state | meaning |
   |---|---|
   | `sync` | behind `origin/$DEF`, or on a non-default branch — real work to do |
   | `blocked` | cannot be synced unattended: detached HEAD, rebase/merge in progress, no `origin`, no resolvable default branch |
   | `stale` | **the fetch failed** — `ahead`/`behind` were computed from refs that could not be refreshed |

### Stop on `stale` — do not sync from unrefreshed refs

`stale` is a hard stop for that repo, not a warning. The counts are from the last successful fetch,
so "0 behind" may mean "50 behind, measured last month", and a rebase would silently do nothing
while reporting success.

If **every** row is `stale`, it is an auth problem, not a repo problem. Diagnose before going
further:

```bash
ssh-add -l                                  # "The agent has no identities" is the usual cause
ssh -o BatchMode=yes -T git@github.com
```

The fix is usually `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`, which may prompt for a
passphrase. **Ask the user to run it themselves** — suggest they type `! ssh-add …` in the prompt —
then re-run the scanner. Do not proceed with `--no-fetch` and do not present a candidate table
built on stale refs.

3. Present the `state=sync` rows for selection, sorted dirty-first then by `behind` descending:
   - **16 or fewer candidates:** use `AskUserQuestion` with `multiSelect: true`, up to 4 questions
     of 4 options. One option per repo. Label = repo name. Description = its state, e.g.
     `on ryan/feature-flags-admin · 12 behind · 3 uncommitted`.
   - **More than 16:** print a numbered list instead and ask the user to reply with numbers, names,
     or `all`. Do not truncate silently — say how many were listed.
4. List `blocked` rows once, with the reason, and say they are being skipped. Do not ask about them.

### Protected branches — confirm before rebasing

Some checked-out branches are long-lived release lines, not feature branches. Rebasing one onto
`main` rewrites shared history and is destructive. Treat a branch as protected if its name is
`production`, `staging`, `develop`, `release`, or matches `release/*`, `hotfix/*`, `rc/*`, or a
version pattern like `v4.1.0` / `v2/parity`.

Real examples in this root: `kiyotaka-frontend` sits on `production` (160 behind `main`),
`titanchart-enterprise` on `v4.1.0`, `wt-v2-desktop` on `v2/parity`.

If a selected repo is on a protected branch, **do not rebase it**. Ask, once, per repo:
fast-forward the branch from its own upstream (`git pull --ff-only`) instead, or skip it? Only
rebase a protected branch onto the default branch if the user says so explicitly, in that turn.

## Phase 1 — per repo, before touching anything

Run these read-only and record the results in a session table:

```bash
git -C "$REPO" rev-parse HEAD          # pre-sync SHA — the undo handle
git -C "$REPO" branch --show-current   # $BRANCH
git -C "$REPO" diff --cached --name-only   # paths that were staged, to re-stage later
git -C "$REPO" status --porcelain
```

Resolve the default branch `$DEF` from `refs/remotes/origin/HEAD`:

```bash
git -C "$REPO" symbolic-ref -q --short refs/remotes/origin/HEAD   # → origin/main
```

Do not assume `main`. `kiyotaka-frontend` sits on `production`, other repos differ.

Abort this repo (and report it) if: HEAD is detached, a rebase/merge/cherry-pick is in progress,
there is no `origin`, or `$DEF` cannot be resolved.

## Phase 2 — carry dirty state as a WIP commit

Only if `git status --porcelain` is non-empty:

```bash
git -C "$REPO" add -A
git -C "$REPO" commit -q --no-verify -m "syncup-wip $(date +%s)"
```

`--no-verify` because pre-commit hooks must not block a temporary commit. `add -A` includes
untracked files so the rebase can conflict-resolve them in one pass. Record the exact WIP subject
line — Phase 5 refuses to unwind unless `HEAD` still carries it.

## Phase 3 — refresh the default branch

```bash
git -C "$REPO" fetch --prune origin
```

Then, **without checking out**, fast-forward the local default branch:

```bash
git -C "$REPO" fetch origin "$DEF:$DEF"     # only when $BRANCH != $DEF
```

This is the deliberate substitute for "checkout main, pull, checkout back". It reaches the same
end state — local `$DEF` equal to `origin/$DEF` — with no worktree churn and no risk to
uncommitted work. It fails loudly (non-fast-forward) if local `$DEF` has diverged; when that
happens, leave `$DEF` alone, note it in the report, and rebase onto `origin/$DEF` anyway.

### When `$BRANCH == $DEF` (already on the default branch)

There is no feature branch to rebase, but the WIP commit from Phase 2 has already made `HEAD`
one commit ahead — so `merge --ff-only` will refuse. Pick by the **pre-WIP** ahead count recorded
in Phase 1:

| pre-WIP ahead | worktree | do this |
|---|---|---|
| 0 | clean | `git merge --ff-only "origin/$DEF"`, then Phase 6 |
| 0 | dirty | try `git merge --ff-only "origin/$DEF"` **first** — see below |
| >0 | either | **stop.** Report and ask. |

With 0 ahead there is nothing to replay, so skip Phase 2 entirely and attempt the fast-forward
directly. A fast-forward does not touch the worktree, so uncommitted work is untouched and the
repo takes zero extra writes. Only if it fails with *"untracked working tree file would be
overwritten"* (an incoming commit adds a path the user has untracked) do you fall back: make the
Phase 2 WIP commit, `git rebase "origin/$DEF"`, resolve, and unwind via Phase 5.

A non-zero pre-WIP ahead count means the user has real commits sitting on their default branch.
Do not rebase, do not merge, do not "clean it up". Report the count and the commit subjects, and
ask what they want before touching it.

Fast-forwarding a dirty worktree can also fail with *"untracked working tree file would be
overwritten"* when an incoming commit adds a file the user has untracked locally. The Phase 2 WIP
commit is what prevents this — it turns that untracked file into a tracked one so the rebase
resolves it as an ordinary conflict. Never delete the untracked file to make room.

## Phase 4 — rebase and resolve

```bash
git -C "$REPO" rebase "origin/$DEF"
```

While the rebase is stopped:

1. `git -C "$REPO" status --porcelain` — conflicted paths are the `UU`/`AA`/`DU`/`UD` rows.
2. Read each conflicted file in full. Resolve it. Policy: **auto-resolve everything, including
   semantic conflicts**, then report each decision.
   - Both sides changed different things → keep both, in the order that compiles.
   - Lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `go.sum`, `Cargo.lock`) → take the incoming
     side, then regenerate from the manifest if the tool is available (`npm install --package-lock-only`,
     `go mod tidy`). Never hand-merge lockfile hunks.
   - Generated files (`*.pb.go`, `dist/`, snapshots) → take incoming, note that a regen may be needed.
   - `DU`/`UD` (modify/delete) → keep the file if the user's side modified it; delete only if the
     user's side is the deletion.
   - Never leave a conflict marker. Grep the resolved file for `<<<<<<<` before staging.
3. `git -C "$REPO" add <resolved paths>`
4. `GIT_EDITOR=true git -C "$REPO" rebase --continue`
   — `GIT_EDITOR=true` is mandatory; without it the commit-message editor hangs the session.
5. If a commit becomes empty because its change is already upstream:
   `git -C "$REPO" rebase --skip`. Say which commit was dropped and why.
6. Repeat until the rebase finishes.

Record, per conflict: file, what each side wanted, what you chose, one line each.

**Escape hatch.** If the same file conflicts a third time, or a resolution needs information the
repo does not contain, stop guessing:

```bash
git -C "$REPO" rebase --abort
```

Then unwind Phase 2 (below), and report that repo as `needs-you` with the specific question.

## Phase 5 — hand the dirty state back

Only if a WIP commit was made. Verify first, then unwind:

```bash
git -C "$REPO" log -1 --format=%s        # must still start with "syncup-wip"
git -C "$REPO" reset --mixed HEAD~1      # changes return to the worktree, unstaged
git -C "$REPO" add -- <paths that were staged in Phase 1>
```

`--mixed` (not `--soft`) is what restores the original shape: previously-untracked files go back to
untracked, previously-modified files go back to modified-unstaged. Re-staging the Phase 1 paths
restores a partial `git add` if the user had one.

If `HEAD` does **not** carry the WIP subject, the WIP commit was dropped as empty during the rebase
— every uncommitted change was already upstream. Do not reset. Say so explicitly in the report.

## Phase 6 — verify before claiming success

Per repo, all four must hold:

```bash
git -C "$REPO" status --porcelain=v1     # no U-state paths
git -C "$REPO" rev-parse --git-dir       # no rebase-merge/ or rebase-apply/ left behind
git -C "$REPO" log --oneline -5
git -C "$REPO" merge-base --is-ancestor "origin/$DEF" HEAD && echo "on latest $DEF"
```

Do not report a repo as synced until `merge-base --is-ancestor` passes. If the repo has a fast test
or typecheck the user has run before (`npm run typecheck`, `go build ./...`), and conflicts touched
source files, run it and report the result. Do not install dependencies to make it run.

## Phase 7 — report

One line per repo, ranked: `needs-you` first, then `synced-with-conflicts`, then `synced`, then
`skipped`. Then the conflict decisions, grouped by repo. Then this footer verbatim:

```
Undo any repo:  git -C <path> reset --hard <pre-sync SHA>   (uncommitted work is in the reflog)
Nothing was pushed. Rebased branches now diverge from origin — force-push is yours to run.
Review a result:  lazygit -p <path>
```

Report the pre-sync SHA for every repo touched, including the ones that ended clean.

## Anti-patterns

- Reporting "synced" without the `merge-base --is-ancestor` check.
- `rebase --continue` without `GIT_EDITOR=true`.
- Fixing a conflict by taking one whole side because the merge is tedious. State the trade-off and
  pick deliberately.
- Running Phase 4 on repo N+1 while repo N is mid-rebase.
- Force-pushing "to finish the job".
- Suggesting the user resolve conflicts in lazygit's merge tool as a substitute for resolving them
  here. lazygit is for their review pass afterward.
