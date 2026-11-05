# Test-pruning campaign

Campaign mode prunes one subsystem's whole test surface in one coherent change,
such as a plugin or core area. The value bar, retention bar, candidate evidence,
and validation in [SKILL.md](SKILL.md) apply to every lane. This file adds the
order of work for a full campaign. Each step ends on its completion criterion;
do not start the next step early.

## 1. Baseline

Record the subsystem's test and support line counts and every test file's
pass/fail state at a pinned base commit. Keep baseline failures in their own
list and investigate their causes; a failing test can expose a real product
defect. Record checks that cannot run separately from failures.

Done when every in-scope test file has a recorded baseline result. If a required
check cannot run, report the missing baseline evidence before proceeding with
dependent deletions.

## 2. Lanes and inventory

Split the surface into **lanes** along production owner boundaries, not file
prefixes. Include the subsystem's cases at shared boundaries and its QA and
live-proof harness tests where they exist.

Done when every test file and QA scenario the subsystem owns belongs to exactly
one lane.

## 3. Read-only ledger per lane

Assign each lane to a read-only agent when delegation is available; otherwise
process the lanes sequentially. Read every assigned test in full, including
parameter tables. Read the production owners and their entry points, callers,
history, and CI routing. Each test declaration goes into a written **ledger**
with one mark. A parameterized test is one declaration unless its rows need
different marks; then mark each row.

- `R`: retain, naming the contract and the bug it catches; a retained test that
  only moves to a better-named file stays `R` with the move noted;
- `F`: retain the contract but repair the assertion, such as a vacuous negative
  that passes when only one of several items is missing;
- `C`: consolidate, naming the owner that absorbs the assertion first: a sibling
  table case, a stronger boundary suite, or the shared owner in another package;
- `D`: delete, naming the proof that remains, or why no contract exists.

Judge a test by its assertions, not its name. Check that negative assertions
actually reject the behavior named by the test.

Done when every declaration in the lane has a mark and an evidence line.

## 4. Layer plan per lane

Treat the per-test ledger as input, not as the edit list. A second read-only
pass, starting from the ledger, looks for redundant **layers**: suites that
replay a shared implementation through mocked collaborators around stronger
boundary tests. Name the **keeper** suite for each contract. Prefer the real
transport boundary with a fake network over a mocked collaborator when the
contract concerns transport behavior. Correct any ledger errors this pass
finds.

Done when each lane plan names its retired files, its keeper per contract, the
assertions to carry into keepers, and the test-only production seams unlocked.

## 5. Cutover

Edit lane by lane. Serialize changes to shared harnesses and support files
through one owner. With each lane, remove the test-only production seams it
unlocks: injection parameters, getters, reset exports, and indirection layers.
Register moved suites in CI routing and test inventories where those exist.
Update shrink-only line-cap baselines if the repository uses them. Record
durable test-ownership rules in the subsystem's existing development guidance,
drawn from mistakes the campaign actually found.

Done when every lane plan is applied and each lane's keepers pass, with any
reproduced baseline defects tracked for step 7.

## 6. Preservation review

Before claiming completion, have independent reviewers compare deleted
coverage against the keepers, one reviewer per boundary group, when available.
Otherwise perform a separate review pass and report the lack of independent
review. Look for contracts that lost their only proof and assertions that
cannot fail, such as a rejection row the production code never reaches.

For each restored contract, make one deliberate **mutation** of the production
owner and confirm the keeper goes red for the intended reason. Preserve the
pre-mutation source and restore it byte for byte before continuing. Use an
isolated checkout if other work could change the same files.

Done when every reported gap is restored or rejected with source evidence, and
every restored contract has a caught mutation.

## 7. Product defects

Investigate a baseline failure that survives into a keeper as a potential
product defect. Fix confirmed defects within the authorized scope at their
owner, keeping those fixes separate from test pruning. Prove each fix through
the real user flow, with a **control** run that removes only the fix and shows
the old behavior. Preserve and restore the candidate source around the control
run. Record unrelated product discrepancies as follow-ups instead of fixing
them in the campaign.

Done when each repaired defect has a failing control and a passing candidate
on the same harness, and unresolved defects are explicitly reported.

## 8. Reconcile and hand off

If the target branch has advanced, reconcile the campaign with it. For a long,
many-commit campaign, prefer merging the target branch over rebasing unless
repository policy requires otherwise. When the target branch modified a file
the campaign deleted, preserve each added or changed contract in its keeper.
Keep the deletion only if every contract still has adequate proof. Rerun the
whole subsystem suite and repeat applicable live proof on the reconciled head.

For large diffs, verify that review covered the complete file inventory even if
a tool truncates its display. Record any authorized exceptions in the review
evidence; do not weaken checks to make the campaign pass.

Hand off with the [SKILL.md](SKILL.md#handoff) report, plus:

- baseline and final test/support line counts, with production counted separately;
- lanes, retired layers, and keepers;
- preservation gaps found and their mutations;
- product defects with control and candidate proof;
- unavailable checks and review limitations.
