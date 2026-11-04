# Enforce mode

`/test-audit enforce [path|rev]` prunes first: every test case in scope is
deleted unless it earns its place. Audit mode's retention bar and candidate
evidence do not apply here; the two answers below are the only way a test
stays.

## Scope

- A path: every test case under it, including cases already on the base
  branch.
- A commit or range: the test cases it adds.
- Neither: the test cases the current branch adds over its merge base with
  `origin/HEAD` (then `origin/main`, then `main`). Cases already on the base
  stay, even where the branch edits them or they duplicate each other; name
  the duplicates in the report.

## The bar

A test case stays only when you can write down both answers:

1. **The bug it catches**: a mistake someone could plausibly make in the code
   it tests, which a user, caller or contract would see. For a case already
   on the base, read the commit that added it first: one added with a bug fix
   names its bug.
2. **Why no other kept test catches it.** One test per behaviour; of two that
   catch the same bug, keep the one with the exact assertion.

Everything else goes, however thorough it looks:

- one case per value through the same code: keep one at most, with a value
  that tells a real result from a default (not 0 or empty). A table only
  when each value runs its own hand-written code;
- a happy path that a kept regression or edge test already runs;
- tests of defaults, constructors, getters, constants, data tables, types,
  or of the language, a framework or a library (argparse rejecting a missing
  argument);
- smoke tests ("does not raise", "prints something"), tests that a mock was
  called, and tests that cannot fail (a value compared with itself, no
  assertion);
- tests of private helpers that a kept public-path test already runs;
- anything matching a [junk pattern](SKILL.md#junk-patterns).

A bug fix keeps one regression test, once you have seen it fail on the code
before the fix.

## Procedure

1. **Baseline.** Run the suite and the coverage tool (Go
   `go test -coverprofile`, TypeScript the runner's `--coverage`, Python
   `coverage run`, or without it
   `python3 -m trace --count --missing -C <dir> --module unittest discover ...`,
   which marks lines that never ran with `>>>>>>` in `<dir>/*.cover`). Record
   the test count and test lines in scope. A case that already fails is
   reported as a possible product bug, not pruned. Done when the suite result
   is recorded.
2. **Ledger.** Mark every case in scope: keep, with both answers, or delete,
   with the item above it matches. Done when no case is unmarked.
3. **Trim.** Delete the cases marked delete, fold per-value cases into the one
   kept, and delete testdata and test helpers that only removed cases used.
4. **Re-check.** Run the suite and coverage again. A code line that stopped
   running gets back the deleted case that ran it only when that case has
   both answers; otherwise report the line as untested. Done when the suite
   passes.
5. **Report**, as below.

## Rules

- Change tests, testdata and test helpers only. Production code the trim
  shows to be dead, untested or kept alive only by tests stays as it is;
  report it for an audit-mode follow-up.
- Never add a test or coverage the scope did not have, whether by a new case
  or by changing a kept case's input or assertion. Report the gap.

## Report

- each kept case with its two answers;
- the deleted cases, grouped by why;
- the test count and test lines before and after, and the suite result;
- base duplicates left alone, untested lines, dead code and test-only seams.

## Common mistakes

- **Keeping a test because it adds coverage or looks thorough, without
  naming the bug only it catches.**
- **Deleting the only test of per-value hand-written code because another
  value's function "has the same shape".**
