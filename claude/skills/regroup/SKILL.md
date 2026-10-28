---
name: regroup
description: Use when a branch's commits or tests need cleaning up for review — a finished run left many TDD-style commits (red/green, wip, "fix test") or a pile of near-duplicate tests on a branch about to become an MR, commits mix tests and code, a commit is too big to review, or Ryan asks to squash, regroup, tidy or clean up commits or trim tests. Works on any branch, whatever its commit count. Trigger: /regroup [--base REF].
---

# regroup — trim a branch's tests and rewrite its commits for the reviewer

The reviewer reads the MR commit by commit, and CI runs every test the MR
adds on every pipeline after it. `/regroup` trims the tests the branch adds
to the absolutely necessary ones, then rewrites `base..HEAD` into commits
that each make one step of the change, in reading order. Only tests and
testdata change; the script proves everything else at the tip unchanged.

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
from its diff: old messages like `wip fix rounding` are often wrong.

## 2. Trim the tests

Agent-written tests bloat, and CI runs every one on every pipeline from now
on. Keep only the tests that are absolutely necessary: delete by default,
and make each test you keep earn its place.

**REQUIRED SUB-SKILL:** test-audit. Its junk patterns name tests to delete.

A test the branch adds stays only when you can write down both answers:

1. **The bug it catches**: a mistake someone could plausibly make in code
   this branch adds or changes, which a user, caller or contract would see.
2. **Why no other kept test catches it.** One test per behavior; of two
   that catch the same bug, keep the one with the exact assertion.

Everything else goes, however thorough it looks:

- one case per value through the same code: keep one at most, with a value
  that tells a real result from a default (not 0 or empty). A table only
  when each value runs its own hand-written code;
- a happy path that a kept regression or edge test already runs;
- tests of defaults, constructors, getters, constants, data tables, types,
  or of the language, a framework or a library (argparse rejecting a
  missing argument);
- smoke tests ("does not raise", "prints something"), tests that a mock was
  called, and tests that cannot fail (a value compared with itself, no
  assertion);
- tests of private helpers that a kept public-path test already runs.

A bug fix keeps one regression test, once you have seen it fail on the code
before the fix.

- Trim only test cases this branch adds. Cases already on the base stay,
  even where the branch edits them (a rename) or they duplicate each other;
  name the duplicates in the report.
- Delete testdata and test helpers that only removed tests used.
- Coverage informs the answers; it is not a quota. Run the coverage tool
  before and after (Go `go test -coverprofile`, TypeScript the runner's
  `--coverage`, Python `coverage run`, or without it
  `python3 -m trace --count --missing -C <dir> --module unittest discover ...`,
  which marks lines that never ran with `>>>>>>` in `<dir>/*.cover`) and
  check the code lines `git diff -U0 <base>` lists. A changed line that
  stops running gets a test only when that test has both answers;
  otherwise report it as untested.
- The trim removes, folds and renames tests; it never adds coverage the run
  did not have. Report the gaps instead, such as per-value code no test
  ever ran.
- The trim changes tests and testdata only. Code it shows to be dead or
  untested stays as it is, with no new test written for it; report it.

Run the suite, then commit the trim on the branch with `/commit` before
planning. The plan takes test files at the tip, so the trim folds into the
one tests commit and `apply`'s tree check covers it.

If `stats` showed no problems, the code commits each make one step and the
trim removed nothing, say so and stop.

## 3. Plan

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

## 4. Apply

```bash
python3 -I $R apply plan.json --dry-run      # until no "!" lines; "~" lines are notes
python3 -I $R apply plan.json
```

`apply` builds the commits off to the side and refuses when a changed file
is missing from the plan, the tip's tree differs from the branch, a commit
mixes kinds or has over 600 lines of code across several files, or the
layout is off (order; testdata, tests or docs spread over several commits).
Only then does it save the old tip as `refs/regroup/<branch>/<UTC time>`
and move the branch.

## 5. Verify

```bash
python3 -I $R check --against refs/regroup/<branch>/<time> --exec "<build>" [--link node_modules]
```

- `--against`: the tip's tree must match the backup's. Identical trees
  mean the suite result after the trim still holds; no rerun needed.
- `--exec` runs at every commit in a temporary worktree. Give it the repo's
  build, not its tests: the code commits come before the tests commit, so
  tests the change updates fail until then. Go `go build ./...`,
  TypeScript `npx tsc --noEmit`, Rust `cargo check`. Python: import every
  module the package has at that commit (`compileall` checks syntax only),
  with plain `python3`; `-I` drops the repo root from the import path.
  ```python
  # <scratchpad>/build.py, run as --exec "python3 <scratchpad>/build.py"
  import importlib, pkgutil, sys
  sys.path.insert(0, "")
  import calc
  for m in pkgutil.walk_packages(calc.__path__, "calc."):
      importlib.import_module(m.name)
  ```
  `--link` links ignored directories (`node_modules`) into that worktree.
- A commit that fails the build needs a file from a later commit: move it
  earlier, then `git reset --keep <backup>` and apply again. A plan's
  `@<sha>` entries name the old commits, so always re-apply from the backup.

## 6. Report

Show Ryan:

- the old and new `git log --oneline` with each commit's size (`stats`
  before and after), the backup ref and the check result;
- each kept test with its two answers, the removed tests grouped by why,
  and the test count and test lines before and after;
- duplicate base tests left alone, dead code, and changed code lines no
  test runs, whether the trim stopped them or they never ran.

Never push. A branch that was already pushed goes up with
`git push --force-with-lease` only on his go.

Undo the regroup with `git reset --keep <backup>`; when there is a trim
commit, `<backup>^` is the tip before the trim. Backups stay under
`refs/regroup/`, out of the branch list (`git for-each-ref refs/regroup`).
Delete them with `git update-ref -d <ref>` once the MR has merged.

## Common mistakes

- Keeping a test because it adds coverage or looks thorough, without
  naming the bug only it catches.
- Deleting the only test of per-value hand-written code because another
  value's function "has the same shape".
- Trimming tests that were already on the base.
- Trimming after `apply`, so the tests land in a second tests commit.
- Making up a halfway version of one big file to get under 600 lines.
- Running the test suite at every commit, then moving tests back into a
  code commit to make an intermediate commit pass.
- Rewriting by hand with `reset` and `add`, without proving the tree
  unchanged.
- Saving the backup as a branch and leaving it in the branch list.
