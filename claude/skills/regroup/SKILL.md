---
name: regroup
description: Use when a branch's commits need cleaning up for review — a finished run left many TDD-style commits (red/green, wip, "fix test") on a branch about to become an MR, commits mix tests and code, a commit is too big to review, or Ryan asks to squash, regroup, tidy or clean up commits. Works on any branch, whatever its commit count. Trigger: /regroup [--base REF].
---

# regroup — rewrite a branch's commits for the reviewer, code unchanged

The reviewer reads the MR commit by commit. `/regroup` rewrites `base..HEAD`
into commits that each make one step of the change, in reading order, and
proves the code at the tip is byte-identical to before.

```bash
R=~/.claude/skills/regroup/scripts/regroup.py
python3 -I $R <stats|apply|check> ...      # from inside the repo
```

The base defaults to the merge base with `origin/HEAD` (then `origin/main`,
`origin/master`, `main`, `master`); pass `--base` for a stacked branch.

## Before

- The run is finished and the suite passed at `HEAD` after its last commit.
- No uncommitted changes to tracked files (`apply` refuses them); untracked
  files are fine.
- The branch has no merge commits; rebase it first (`/syncup`).
- Already pushed: the rewrite needs a force push, which is Ryan's call. If
  the MR has review comments or approvals, tell him the reviewer loses their
  place before he decides.

## 1. Read

```bash
python3 -I $R stats          # prints the base it used
git diff <base>..HEAD
```

`stats` lists each commit's counted lines, kind (code, test, testdata,
docs, generated, or mixed) and problems, then the layout problems, then
every file the branch changes with its kind. Read what each commit does
from its diff: old messages like `wip fix rounding` are often wrong. If
`stats` shows no problems and the code commits each make one step, say so
and stop.

## 2. Plan

The layout, in this order:

1. **Code**, grouped by concern in reading order: schema, migrations, types
   and refactors the change builds on first; then core logic; then its
   callers, wiring and config. Lockfiles, vendored and generated files go
   with the change that produced them (`go.sum` with `go.mod`) and don't
   count toward the cap. One that no change on the branch produced gets
   its own `chore:` commit among the code commits.
2. **All testdata in one commit**: fixtures and golden files.
3. **All tests in one commit**, helpers included.
4. **All docs in one commit**.

Only code commits have a cap: 600 changed lines (added plus deleted).
Testdata, tests and docs stay one commit each, whatever their size. Code
over 600 splits by file, or by a file's version at an existing commit of
the branch (`path@<sha>`). A single file over 600 that no existing commit
splits stays whole: never write a partial version that never existed.

When the defaults misclassify a path (a test helper package, `SKILL.md` as
code in a skills repo), map it in the plan's `kinds` (fnmatch; `*` crosses
`/`) and pass `--plan` to `stats` and `check`. `kinds` fixes
misclassification only: a data file outside the test directories is code,
and no path is remapped to get under the cap.

Messages follow the `/commit` rules: one summary line in the repo's style,
at most 3 bullets, no AI trailer.

Write the plan to the scratchpad:

```json
{
  "commits": [
    {"message": "feat(rates): look up rates by currency", "paths": ["calc/rates.py@046056b"]},
    {"message": "feat(rates): cache lookups", "paths": ["calc/rates.py"]},
    {"message": "test(rates): cover lookup and cache", "paths": ["tests/test_rates.py", "internal/testutil/db.go"]},
    {"message": "docs: describe rate lookup", "paths": ["README.md"]}
  ],
  "kinds": {"internal/testutil/**": "test"}
}
```

A bare path takes the file as it is at the tip; every changed file must end
at its tip version.

## 3. Apply

```bash
python3 -I $R apply plan.json --dry-run      # until it prints no problems
python3 -I $R apply plan.json
```

`apply` builds the commits off to the side and refuses when a changed file
is missing from the plan, the tip's tree differs from the branch, a commit
mixes kinds or has over 600 lines of code across several files, or the
layout is off (order; testdata, tests or docs spread over several commits).
Only then does it save the old tip as `refs/regroup/<branch>/<UTC time>`
and move the branch.

## 4. Verify

```bash
python3 -I $R check --against refs/regroup/<branch>/<time> --exec "<build>" [--link node_modules]
```

- `--against`: the tip's tree must match the backup's. Identical trees
  mean the suite result at the old `HEAD` still holds; no rerun needed.
- `--exec` runs at every commit in a temporary worktree. Give it the repo's
  build, not its tests: the code commits come before the tests commit, so
  tests the change updates fail until then. Go `go build ./...`,
  TypeScript `npx tsc --noEmit`, Rust `cargo check`, Python an import of
  every module the branch changes
  (`python3 -I -c 'import calc.rates, calc.cli'`; `compileall` checks
  syntax only). `--link` links ignored directories (`node_modules`) into
  that worktree.
- A commit that fails the build needs a file from a later commit: move it
  earlier, then `git reset --keep <backup>` and apply again. A plan's
  `@<sha>` entries name the old commits, so always re-apply from the backup.

## 5. Report

Show Ryan the old and new `git log --oneline` with each commit's size
(`stats` before and after), the backup ref and the check result. Never
push. A branch that was already pushed goes up with
`git push --force-with-lease` only on his go.

Undo: `git reset --keep <backup>`. Backups stay under `refs/regroup/`, out
of the branch list (`git for-each-ref refs/regroup`). Delete them with
`git update-ref -d <ref>` once the MR has merged.

## Common mistakes

- Making up a halfway version of one big file to get under 600 lines.
- Running the test suite at every commit, then moving tests back into a
  code commit to make an intermediate commit pass.
- Rewriting by hand with `reset` and `add`, without proving the tree
  unchanged.
- Saving the backup as a branch and leaving it in the branch list.
