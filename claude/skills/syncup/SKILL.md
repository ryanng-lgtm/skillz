---
name: syncup
description: Use when the user wants one or more local repos brought up to date with their default branch, or their open GitLab MRs rebased onto their target branches — refresh main from origin, rebase the working branch onto it, resolve every conflict, including when the worktree has uncommitted changes, and push the rebased MR branches. Picks candidates from the current session and from the user's open MRs that have fallen behind, or from a named stack (om-chat, fe, tc, be). Trigger: /syncup [repo|stack ...], "sync up my repos", "sync the FE stack", "rebase everything on main", "get me on latest main", "update my MRs", "rebase my MRs".
---

# syncup — bring selected repos and MRs up to date

## Overview

syncup works in **units**. A unit is one branch in one clone, rebased onto one base:

| unit | base | runs in | pushed |
|---|---|---|---|
| MR, `needs=rebase` | `origin/<target>` | the worktree that has the source branch checked out, else a temporary worktree | yes |
| MR, `needs=restack` | the MR's target after that branch's own unit was pushed | same | yes |
| checked-out branch with no MR | `origin/<default>` | the checkout | no |

For each unit: rebase onto its base, resolve every conflict, hand uncommitted work back exactly as
unstaged/staged as it started, and push the unit if it is an MR. Units are processed **one at a
time, sequentially**, inline in the main thread — never via subagents, because conflict resolution
needs the full session context.

Default repo root: `~/Documents/GitLab`. Override with `--root DIR` or `SYNCUP_ROOT`.

The Bash tool runs zsh, where `$VAR:r…` is a modifier: always brace a variable followed by `:`
(`"${SHA}:refs/heads/${SRC}"`), as every snippet below does.

## Hard rules

- **Push only MR source branches**, only in Phase 7, only with `--force-with-lease` pinned to the
  SHA recorded in Phase 1. Never push the default branch, a protected branch, or a branch with no
  open MR. Never plain `--force`, never `--no-verify`.
- **Never `git stash`.** Dirty state travels as a temporary WIP commit (Phase 2). Reflog recovers a
  botched WIP commit; a botched stash pop is much worse.
- **Never `reset --hard`, `checkout -f`, `clean`, or `restore` on a repo with uncommitted work.**
- **Never switch the user's checkout.** An MR branch that is not checked out is rebased in a
  temporary worktree, and every temporary worktree is removed before its unit is reported.
- **Never `rebase --skip` on a commit that is not the WIP commit.** Use `--onto` only for a
  restack unit (Phase 4).
- Record every unit's pre-sync SHA *before* touching it. Those SHAs are the undo handles and must
  appear in the final report.
- Only touch the repos the user selected. Never widen the set, never touch submodules.
- Never edit `.git/config`, change remotes, or delete branches.
- If a unit cannot be finished safely, abort **that unit** back to its pre-sync state, do not push
  it, and keep going with the rest. Never leave a repo mid-rebase.

## Stacks

Named groups of repos that ship together. Paths are relative to the root.

| stack | repos |
|---|---|
| `om-chat` | `openmarket-internal`, `om-chat-cloud`, `tharamine-user-service`, `kiyotaka-chat-service` |
| `fe` | `kiyotaka-frontend`, `orange-v2-backend`, `tharamine-user-service`, `auth-service-backend`, `orange-shared` |
| `tc` | everything in `fe`, plus `titan-charts` |
| `be` | `meta_repo/` + `tsdb-gateway`, `replayer`, `kiyotaka-go`, `streamd`, `streamd-cex-playbook`, `stream-deduplicated`, `metadata-instrument` |

- `om-chat-cloud` is the GitLab `openmarket-chat`. The top-level `openmarket-chat` dir is the GitHub
  repo and is not in the stack.
- The `be` repos also have top-level clones (`tsdb-gateway`, `streamd`, ...). The stack means the
  `meta_repo/` ones.

## Phase 0 — pick the units

Never scan the whole root on a bare invocation. Build a short candidate set and scan only that
set. Offer the stacks only when the user named nothing and the session has touched no repos. Scan
the whole root only when the user asks for everything (`/syncup all`, "sync all my repos").

1. **Arguments.** If the user named repos or stacks, expand the stacks and use exactly that set.
   Resolve each repo to a path under the root, and ask for the path if one does not resolve. Skip
   step 2.
2. **Session repos.** Look back over this conversation for repos under the root that were worked on:
   files read or edited, commands run in them, commits or branches made. Use the summary if the
   session was compacted. Mentioning a repo by name is not enough. Record why each repo qualifies,
   in a few words.
3. **MRs.** Run:

   ```bash
   bash ~/.claude/skills/syncup/scripts/mrs.sh
   ```

   It lists the user's open GitLab MRs mapped to their local clones, one TSV row per MR and clone:
   `path  mr  source  target  behind  needs  worktree  local  merge_status  fetch`. `--help`
   defines every column. With arguments, keep only the rows whose `path` is in the argument set.
   - Every row with `needs=rebase` or `needs=restack` is an **MR unit**, whether or not its branch
     is checked out. When two clones match one MR, use the one whose `worktree` is set, else the
     first.
   - `local=ahead:N` means N local commits that are not on origin yet; the push will publish them.
     Put `N unpushed commits will be pushed` in the candidate's description.
   - `local=diverged:B/A` is not a candidate. List it once as `needs-you` with both counts: local
     and origin have both moved, and only the user knows which side is right.
   - `needs=ok` is an MR already current with its target. It is not a candidate, and any scan row
     for the same path and branch is dropped, so an MR branch is never rebased onto the default
     branch instead of its target.
   - `needs=?` rows are listed once and skipped: `fetch=no-source` is a source branch that is not
     on origin (usually a fork MR); path `-` is an MR with no local clone.
   - `fetch=failed` rows follow the `stale` rule below.
4. **Scan the candidates.** Pass the session repos (or the argument set) to the scanner. MR units
   need no scan; for one with `worktree` set, count its uncommitted files with
   `git -C <worktree> status --porcelain`.

   ```bash
   bash ~/.claude/skills/syncup/scripts/scan.sh <path> ...
   ```

   With no paths it scans every repo directly under the root, which is the `/syncup all` case only. It
   fetches in parallel (`--no-fetch` skips the fetch) and prints TSV:
   `name  branch  default  ahead  behind  dirty  state  path  fetch`. Only repos that need work are
   listed (`--all` includes clean ones). A repo the user named that comes back clean is reported as
   already up to date and is not synced.

   | state | meaning |
   |---|---|
   | `sync` | behind `origin/$DEF`, or on a non-default branch — real work to do |
   | `blocked` | cannot be synced unattended: detached HEAD, rebase/merge in progress, no `origin`, no resolvable default branch |
   | `stale` | **the fetch failed** — `ahead`/`behind` were computed from refs that could not be refreshed |

   A `sync` row whose branch is the source of an MR row (any `needs`) belongs to that MR: the MR
   unit replaces it, or `needs=ok` drops it. The remaining `sync` rows are default-branch units.

### Stop on `stale` — do not sync from unrefreshed refs

`stale` is a hard stop for that repo, not a warning. The counts are from the last successful fetch,
so "0 behind" may mean "50 behind, measured last month", and a rebase would silently do nothing
while reporting success.

If **every** row is `stale`, it is an auth problem, not a repo problem. Diagnose before going
further:

```bash
ssh-add -l                                  # "The agent has no identities" is the usual cause
ssh -o BatchMode=yes -T git@gitlab.com     # or git@github.com for GitHub remotes
```

The fix is usually `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`, which may prompt for a
passphrase. **Ask the user to run it themselves** — suggest they type `! ssh-add …` in the prompt —
then re-run the scanner. Do not proceed with `--no-fetch` and do not present a candidate table
built on stale refs.

5. **Ask.** Skip this step when the user passed arguments. Otherwise use one `AskUserQuestion`
   call, every question `multiSelect: true`:
   - **Detected:** the MR units and the `state=sync` default-branch units from steps 2–4, sorted
     dirty-first, then by `behind` descending. Label is the repo name, plus `!<iid>` for an MR
     unit. Description is the reason and state, e.g.
     `MR !2402 → main · 5 behind · 3 uncommitted · will force-push`,
     `MR !2410 → feat/base · restack · not checked out · will force-push`, or
     `edited this session · 12 behind`. With two or more candidates, the first option is **All**,
     which selects every candidate; its description lists the labels. Spread candidates that do
     not fit over extra questions, keeping one for stacks when it is asked. If they still do not
     fit, print a numbered list instead and ask for numbers, names, or `all`, and say how many were
     listed. If nothing was detected, say so, then ask only the stacks question in a fresh session,
     or stop otherwise.
   - **Stacks:** only when step 2 found no session repos. One option per stack. Description is its
     repo list. A session that has touched repos already says what to sync; leave the stacks out
     and mention that `/syncup <stack>` still works.

   If the user picks a stack, run steps 3–4 for its repos and sync only the MR units and
   `state=sync` rows. List the rest as already up to date.
6. List `blocked` rows once, with the reason, and say they are being skipped. Do not ask about them.
7. **Order.** Run a restack unit after the unit whose source is its target. When that unit was not
   selected or was not pushed, the restack unit's target did not move: run it as a plain rebase
   onto `origin/<target>` if `behind` > 0, and otherwise report it as up to date.

### Protected branches — confirm before rebasing

Some branches are long-lived release lines, not feature branches. Rebasing one onto `main`
rewrites shared history and is destructive. Treat a branch as protected if its name is
`production`, `staging`, `develop`, `release`, or matches `release/*`, `hotfix/*`, `rc/*`, or a
version pattern like `v4.1.0` / `v2/parity`.

Real examples in this root: `kiyotaka-frontend` sits on `production` (160 behind `main`),
`titanchart-enterprise` on `v4.1.0`, `wt-v2-desktop` on `v2/parity`.

If a selected unit's branch is protected, **do not rebase it**. Ask, once, per unit: fast-forward
the branch from its own upstream (`git pull --ff-only`) instead, or skip it? Only rebase a protected
branch if the user says so explicitly, in that turn, and never push one.

## Phase 1 — per unit, before touching anything

`$CLONE` is the repo path. `$WT` is the directory the unit runs in: the repo path for a
default-branch unit, the `worktree` column for an MR unit that is checked out.

**MR units — before the first push of the run**, fetch each clone once and record, for every MR
unit:

```bash
git -C "$CLONE" fetch --prune origin
git -C "$CLONE" rev-parse "origin/${SRC}"   # $PRE_REMOTE — the lease for the push
git -C "$CLONE" rev-parse "origin/${TGT}"   # $PRE_TGT — the fork point for a restack unit
```

Recording them all up front matters: once a base MR is pushed, `origin/<its source>` has moved,
and the restack unit stacked on it needs the old value. Then fast-forward the clone's local `$DEF`
with `git -C "$CLONE" fetch origin "${DEF}:${DEF}"` unless a worktree has `$DEF` checked out; a
failure is noted in the report, not fatal.

**MR unit that is not checked out** (`worktree` is `-`): add a temporary worktree.

```bash
TMP="$(mktemp -d "${TMPDIR:-/tmp}/syncup.XXXXXX")"
git -C "$CLONE" worktree add -q "$TMP/wt" "$SRC"                       # local branch exists
git -C "$CLONE" worktree add -q --detach "$TMP/wt" "origin/${SRC}"     # local=none
WT="$TMP/wt"
```

A temporary worktree is always clean, so Phase 2 does not apply to it. Its detached HEAD
(`local=none`) is expected.

Then, for every unit, read-only:

```bash
git -C "$WT" rev-parse HEAD          # pre-sync SHA — the undo handle
git -C "$WT" branch --show-current   # $BRANCH
git -C "$WT" diff --cached --name-only   # paths that were staged, to re-stage later
git -C "$WT" status --porcelain
```

Resolve the default branch `$DEF` from `refs/remotes/origin/HEAD`:

```bash
git -C "$CLONE" symbolic-ref -q --short refs/remotes/origin/HEAD   # → origin/main
```

Do not assume `main`. `kiyotaka-frontend` sits on `production`, other repos differ.

Abort the unit (and report it) if, in the user's checkout: HEAD is detached, a
rebase/merge/cherry-pick is in progress, there is no `origin`, or `$DEF` cannot be resolved.

## Phase 2 — carry dirty state as a WIP commit

Only if `git status --porcelain` is non-empty:

```bash
git -C "$WT" add -A
git -C "$WT" commit -q --no-verify -m "syncup-wip $(date +%s)"
```

`--no-verify` because pre-commit hooks must not block a temporary commit. `add -A` includes
untracked files so the rebase can conflict-resolve them in one pass. Record the exact WIP subject
line — Phase 5 refuses to unwind unless `HEAD` still carries it.

## Phase 3 — refresh the base

**MR unit with `local=behind:N`:** origin has commits the local branch lacks. Take them first:

```bash
git -C "$WT" rebase "origin/${SRC}"
```

With no WIP commit this is a fast-forward. With one, it carries the WIP commit across. Resolve
conflicts as in Phase 4.

**Default-branch unit:**

```bash
git -C "$WT" fetch --prune origin
```

Then, **without checking out**, fast-forward the local default branch:

```bash
git -C "$WT" fetch origin "${DEF}:${DEF}"     # only when $BRANCH != $DEF
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
| 0 | clean | `git merge --ff-only "origin/${DEF}"`, then Phase 6 |
| 0 | dirty | try `git merge --ff-only "origin/${DEF}"` **first** — see below |
| >0 | either | **stop.** Report and ask. |

With 0 ahead there is nothing to replay, so skip Phase 2 entirely and attempt the fast-forward
directly. A fast-forward does not touch the worktree, so uncommitted work is untouched and the
repo takes zero extra writes. Only if it fails with *"untracked working tree file would be
overwritten"* (an incoming commit adds a path the user has untracked) do you fall back: make the
Phase 2 WIP commit, `git rebase "origin/${DEF}"`, resolve, and unwind via Phase 5.

A non-zero pre-WIP ahead count means the user has real commits sitting on their default branch.
Do not rebase, do not merge, do not "clean it up". Report the count and the commit subjects, and
ask what they want before touching it.

Fast-forwarding a dirty worktree can also fail with *"untracked working tree file would be
overwritten"* when an incoming commit adds a file the user has untracked locally. The Phase 2 WIP
commit is what prevents this — it turns that untracked file into a tracked one so the rebase
resolves it as an ordinary conflict. Never delete the untracked file to make room.

## Phase 4 — rebase and resolve

Start the rebase for the unit's kind:

```bash
git -C "$WT" rebase "origin/${DEF}"                     # default-branch unit
git -C "$WT" rebase "origin/${TGT}"                     # MR unit, needs=rebase
FORK="$(git -C "$WT" merge-base HEAD "$PRE_TGT")"       # MR unit, needs=restack
git -C "$WT" rebase --onto "origin/${TGT}" "$FORK"
```

A restack unit's target was rewritten and pushed earlier in this run. A plain rebase onto it would
replay the old copies of the base MR's commits; `--onto` from the fork point with the old target
replays only the restack unit's own commits.

While the rebase is stopped:

1. `git -C "$WT" status --porcelain` — conflicted paths are the `UU`/`AA`/`DU`/`UD` rows.
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
3. `git -C "$WT" add <resolved paths>`
4. `GIT_EDITOR=true git -C "$WT" rebase --continue`
   — `GIT_EDITOR=true` is mandatory; without it the commit-message editor hangs the session.
5. If a commit becomes empty because its change is already upstream:
   `git -C "$WT" rebase --skip`. Say which commit was dropped and why.
6. Repeat until the rebase finishes.

Record, per conflict: file, what each side wanted, what you chose, one line each.

**Escape hatch.** If the same file conflicts a third time, or a resolution needs information the
repo does not contain, stop guessing:

```bash
git -C "$WT" rebase --abort
```

Then unwind Phase 2 (below), and report that unit as `needs-you` with the specific question. It is
not pushed.

## Phase 5 — hand the dirty state back

Only if a WIP commit was made. Verify first, then unwind:

```bash
git -C "$WT" log -1 --format=%s        # must still start with "syncup-wip"
git -C "$WT" reset --mixed HEAD~1      # changes return to the worktree, unstaged
git -C "$WT" add -- <paths that were staged in Phase 1>
```

`--mixed` (not `--soft`) is what restores the original shape: previously-untracked files go back to
untracked, previously-modified files go back to modified-unstaged. Re-staging the Phase 1 paths
restores a partial `git add` if the user had one.

If `HEAD` does **not** carry the WIP subject, the WIP commit was dropped as empty during the rebase
— every uncommitted change was already upstream. Do not reset. Say so explicitly in the report.

## Phase 6 — verify before claiming success

Per unit, all of these must hold (`$BASE` is `$DEF` or `$TGT`):

```bash
git -C "$WT" status --porcelain=v1     # no U-state paths
test ! -d "$(git -C "$WT" rev-parse --git-path rebase-merge)" &&
  test ! -d "$(git -C "$WT" rev-parse --git-path rebase-apply)"   # no rebase left behind, per worktree
git -C "$WT" log --oneline -5
git -C "$WT" merge-base --is-ancestor "origin/${BASE}" HEAD && echo "on latest $BASE"
```

For an MR unit, also check that no work, pushed or local, is about to be dropped:

```bash
git -C "$WT" cherry HEAD "$PRE_REMOTE"      # a "+" line is a commit with no equivalent in HEAD
git -C "$WT" cherry HEAD "<pre-sync SHA>"
```

Every `+` line must be a commit whose conflict you resolved in Phase 4, or the old copy of a base
MR commit for a restack unit. Any other `+` is lost work: abort the unit as `needs-you`.

Do not report a unit as synced until `merge-base --is-ancestor` passes. If the repo has a fast test
or typecheck the user has run before (`npm run typecheck`, `go build ./...`), conflicts touched
source files, and `$WT` is the user's checkout, run it and report the result. A temporary worktree
has no installed dependencies: say the check was not run there. Do not install dependencies to make
it run.

## Phase 7 — push MR units

Only MR units that passed Phase 6. Push from `$CLONE`, not the temporary worktree, so pre-push
hooks run where dependencies are installed:

```bash
SHA="$(git -C "$WT" rev-parse HEAD)"
git -C "$CLONE" log -1 --format=%s "$SHA"     # must not start with "syncup-wip"
git -C "$CLONE" push --force-with-lease="refs/heads/${SRC}:${PRE_REMOTE}" origin "${SHA}:refs/heads/${SRC}"
```

The lease is the Phase 1 SHA, not the remote-tracking ref: an editor's background fetch can move
`origin/<source>` and silently widen a bare `--force-with-lease`. A push also updates
`origin/<source>`, which is what the restack units stacked on this one rebase onto.

A rejected lease (someone pushed since Phase 1), a failing pre-push hook, or GitLab refusing a
force-push to a protected branch makes the unit `needs-you`. Leave the local rebase in place,
report the error, and never retry with `--force` or `--no-verify`.

Then remove the temporary worktree, if the unit had one:

```bash
git -C "$CLONE" worktree remove "$WT" && rmdir "$TMP"
```

If removal fails, report the path; do not `--force` it.

## Phase 8 — report

One line per unit, ranked: `needs-you` first, then `synced-with-conflicts`, then `synced`, then
`skipped` (including MRs already up to date and `needs=?` rows). An MR unit's line names the MR and
the push: `!2402 feat/x → main · pushed <old>..<new>`. In argument mode, where nothing was asked,
the notes Phase 0 puts in candidate descriptions (unpushed commits published, `diverged`) go on
the unit's report line.
Then the conflict decisions, grouped by repo. Then this footer verbatim:

```
Undo a local branch:  git -C <path> reset --hard <pre-sync SHA>   (uncommitted work is in the reflog)
                      git -C <path> branch -f <branch> <pre-sync SHA>   (a branch that is not checked out)
Undo a pushed MR:     git -C <path> push --force-with-lease=<source>:<new SHA> origin <old SHA>:refs/heads/<source>
Only MR source branches were pushed. Other rebased branches now diverge from origin — pushing them is yours.
Review a result:      lazygit -p <path>
```

Report the pre-sync SHA for every unit touched, including the ones that ended clean, and
`<old>`/`<new>` for every pushed MR.

## Anti-patterns

- Reporting "synced" without the `merge-base --is-ancestor` check.
- Pushing before Phase 6 passes, or with the WIP commit on `HEAD`.
- Retrying a rejected lease with `--force`, or pushing with `--no-verify` past a failing hook.
- Rebasing a restack unit with a plain `git rebase "origin/${TGT}"`.
- Switching the user's checkout to reach an MR branch instead of using a temporary worktree.
- `rebase --continue` without `GIT_EDITOR=true`.
- Fixing a conflict by taking one whole side because the merge is tedious. State the trade-off and
  pick deliberately.
- Running Phase 4 on the next unit while one is mid-rebase.
- Suggesting the user resolve conflicts in lazygit's merge tool as a substitute for resolving them
  here. lazygit is for their review pass afterward.
