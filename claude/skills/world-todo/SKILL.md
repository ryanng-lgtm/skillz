---
name: world-todo
description: >-
  Plan OM World service tasks, features, and fixes with frontier-agent
  drafting and review, demuddy, a shared OpenScape handoff, and Task Index
  updates. Apply to every such change, however small, unless the user
  explicitly overrides the workflow. Trigger: $world-todo or /world-todo.
---

# World Todo

Every OM World task gets the five steps below before implementation.
Scale detail to the task, never skip steps because the change is small.
An explicit user override takes precedence.

Apply to om-world-service work and related changes in neighboring repos.
Discover ownership from current code. Ordinary factual questions do not
create tasks. Maintaining this skill does not recursively invoke it.
A planning request authorizes planning only. Continue already authorized
implementation after its planning gates are met.

Read repository instructions and follow their code-discovery rules. Inspect
current source and tests, rather than carrying forward architecture claims.
Read `demuddy`, `ivtg`, or `llm-council` from the active host's skills directory
when invoked. Search for a missing skill before reporting a blocked step.
Never claim a substitute ran as the named skill.

## Route and clarify

For a bugfix, offer `$ivtg` investigation before choosing that workflow.
Invoke it only after opt-in; continue independent evidence gathering while
awaiting the answer. An unanswered offer is not consent. A declined offer
still follows all five steps. If accepted, reuse its investigation and review
as step 1, respecting its plan-only boundary and revision limit. Reuse the
known session title and repo set; ask only for missing information.

For a feature, interactively probe the expected behavior, boundaries, failure
cases, and acceptance criteria. Validate feasibility against actual code.
Resolve material choices with the user; do not invent their answers.
Always require TDD: specify meaningful failing behavioral tests, minimal
implementation to pass them, then refactoring. During implementation, run
the tests and establish the expected failure before writing the feature.
Record actual results separately from proposed checks.

For other tasks, ask about unknowns that materially affect the plan. The
five-step workflow still applies.

### Feature planning modes

Codex must use actual Plan mode for feature specification and review. Use
the host's mode control if exposed. Otherwise ask the user to select Plan
mode, explaining that the host has not exposed a callable switch. A written
plan or planning tool does not change the active mode. Continue independent
read-only discovery while the required switch is pending.

Draft the plan, probe specifications, and fold in the independent review in
Plan mode. Obtain user approval of the concrete reviewed plan. Then return
to actual Default mode through the host control or the user's action and
persist the final plan before steps 2–5. A mode switch alone is not approval.

Claude performs the same interactive specification, review, and approval
without requiring a mode switch. Do not request approval again for an
unchanged plan already approved in this session.

Persist drafts in the dated plans directory when the active host permits
plan-file writes. If Plan mode forbids filesystem writes, keep the draft in
the host's planning artifact until Default mode, then save it before any
implementation. Never bypass a host restriction to satisfy a file rule.

## Five required steps

### 1. Draft and independently review the plan

Use a frontier model agent to draft and a separate frontier model agent to
review. Select available frontier models from the host, not an obsolete
model name copied from another skill. Both agents inspect relevant source
and tests. Give the reviewer the draft and raw evidence, and require its own
check of feasibility, failure cases, ownership, and acceptance criteria.
Agents are read-only; the coordinator owns plan-file edits.

Fold findings into the plan. Reuse the reviewer to verify material fixes.
An unresolved blocker stays explicit and prevents a ready verdict. Respect
ivtg's revision limit when active; stop at unresolved blockers rather than
starting an extra revision loop or declaring the revised plan clean.

The final plan includes expected behavior, scope and non-goals, owning repos
and revisions, source citations, ordered implementation, acceptance tests,
dependencies, risks, and unresolved decisions. Distinguish verified behavior
from proposals. Include the TDD sequence for every feature.

Run `date +%F` and use `~/.codex/plans/YYYY-MM-DD/<task-slug>.md` or
`~/.claude/plans/YYYY-MM-DD/<task-slug>.md`. Resolve the existing plan-root
symlink; do not choose a different nested Obsidian vault. Never save at the
plans root or commit session-authored plans/specs into project repositories.

### 2. Run demuddy

Once review findings are folded in and required approval is recorded, run
`$demuddy` on the explicit dated plan path. Follow its candidate, coverage,
diff, and replacement procedure. Preserve requirements, citations, risks,
unknowns, and review status. Editorial cleanup cannot resolve a blocker.
If substantive changes are needed, return to review and renew approval only
for changed decisions. Do not publish an unresolved plan as ready to build.

### 3. Publish the shared handoff

Read the current `/Users/ryan/Syncthing/OpenScape/Docs/Documentation Map.md`,
root `000 Task Index.md`, and relevant owner notes before choosing a name.
Copy the cleaned plan as a regular Markdown file into
`/Users/ryan/Syncthing/OpenScape/Docs/`. Use the local readable Title Case
convention, for example `World Chat Todo Rendering.md`, not a dated slug.
Keep filenames unique across the shared tree. Reuse the same destination
for the same task on reruns. Never overwrite an unrelated same-name note.
A symlink to the plans vault does not satisfy shared publication.

### 4. Update Task Index and its owning task

Use the existing root `000 Task Index.md`, not a new index under `Docs`.
Follow the current Documentation Map: root numbered notes own unfinished
work, Docs holds handoffs, and Archive holds historical evidence.
Update the existing owning task, or allocate the next unused number if this
work has no owner. Preserve task IDs and never reuse a retired number.
Update the owner and index together with status, next action/dependency,
acceptance criteria, and a link to the new handoff. Planning is not delivery.

### 5. Reconcile related knowledge-base references

Audit the knowledge base for references to this task, old titles/paths, and
claims that its plan is missing. Update relevant owner, index, documentation
map, dependencies, and direct references where needed. Preserve historical
claims in Archive as historical; do not rewrite receipts into current status.
Do not sweep unrelated notes or Syncthing version/backup directories.

Use portable `[[Unique Filename]]` wikilinks. Preserve headings and aliases;
escape alias pipes in table cells. Verify changed targets and headings exist.
Where a local code citation requires a checkout, retain its repo/revision
context. Make shared note links usable without the author's vault paths.

Before rewriting existing shared files, keep a backup outside the synced
tree and record their current content/hash. Recheck immediately before each
write. If incoming sync edits changed a file, reread and merge task-owned
changes; surface conflicts rather than overwriting them. Repeated runs must
not duplicate documents, index entries, or links. Do not infer remote sync
completion from a successful local write.

## Agent budget and difficult decisions

Keep the whole task within five agents, counting the coordinator and all
delegates conservatively, and honor a lower runtime concurrency limit.
Reserve two frontier workers for drafting/review. Reuse them for revisions;
delegates must not create extra agents without a reserved slot. Count agents
inside invoked skills too. If subagents are unavailable, run the roles
sequentially in the main thread as Ryan's standing fallback requires, and
report that the review was not independent. Disclose unavailable frontier
models and seek a user override before substituting a lower model class.

For a hard decision with real tradeoffs, run `$llm-council` on a neutral
question grounded in the code and constraints. Use available cheaper models
for council work, reserving frontier models for the plan and its review.
Keep all five council lenses, anonymized review, and synthesis. Adapt its
agent fan-out to the remaining budget: reuse cheaper workers for sequential
role passes rather than spawning new reviewers/chairmen. Disclose reduced
independence from reused contexts. Never silently upgrade council cost.
If cheaper models are unavailable, report that limitation and ask how to
proceed. A council recommendation does not replace user specification approval.

## Finish

Verify the dated final plan, the real Docs copy, consistent owner/index
status, and affected links. Compare plan content between copies; explain any
publication-only link adjustments. Report the plan and handoff paths, task
ID/status, review outcome, and blockers. Do not claim checks ran when merely
planned. Preserve the current authorization boundary, including ivtg's
plan-only endpoint. After authorized implementation, update task status and
record validation against the actual build in Archive as the local map asks.
