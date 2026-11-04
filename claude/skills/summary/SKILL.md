---
name: summary
description: >-
  Use when a loop-me-in run, an unattended brief or a long working session
  ends or pauses and the user needs to know where things stand: which repos
  were touched, the order their MRs or PRs merge in, and what is left for them
  to do. Trigger: /summary, $summary, "give me a rundown", "which repos were
  touched", "merge order?", "what's left for me", "remaining actions".
---

# summary — which repos, what merges first, what's left for the user

## Overview

At the end of a run or a long session the user needs one answer: what changed where, what merges in what order, and what only they can do. The session's memory drifts from the repos: a hook pushed a branch, a teammate merged an MR, a pipeline went red after the last look.

**Core principle: every state you report is read from the repo or the forge now, not recalled from the session.** The session tells you where to look; the live read decides what you write.

## Procedure

1. **List what the session touched.** Every repo and worktree it edited, committed in, pushed, or opened an MR or PR for, with the branch, including repos changed only locally or holding uncommitted work. When the session ran a brief, its ground truth, process ledger and findings log name them. Done when nothing the session wrote to is missing.
2. **Read each one's live state** with read-only commands:

   ```sh
   git -C <worktree> status --short --branch      # uncommitted work, ahead/behind upstream
   git -C <worktree> log --oneline <base>..HEAD   # the branch's own commits
   glab mr list --source-branch <branch>          # or: gh pr list --head <branch>
   glab mr view <n>                               # or: gh pr view <n>
   ```

   Note per repo: commits, pushed or not, MR or PR link and state (draft, open, approved, merged, conflicting), pipeline result. Where the read contradicts what the session believed, the read wins, and say so in one line.
3. **Work out the merge order from dependencies**, not from the order the work was done: a library before its consumers, with the consumers' re-pin between them; a migration before the code that reads it; a producer deployed before a consumer that needs its new field; docs after the behaviour they describe. Give each step its reason and any action between merges (re-pin, rebase, renumber a migration, deploy before the next merge). Changes that depend on nothing say "any order".
4. **Collect what only the user can do:** approvals, merges, a go-ahead to push, deploys, answers to open questions, messages to other people, checks you have no access to, and processes the session left running (stop them, or confirm they should keep running). Work you can do yourself goes in only when it waits on their word, as "say go and I'll …".
5. **Reply in the shape below**, and nothing after it.

## The shape

```markdown
## Repos touched

| Repo | Branch / MR | State | What changed |
|---|---|---|---|
| <repo> | `<branch>`, [!123](<url>) | 3 commits, pushed, MR open, pipeline green | <one line> |

Not shipping: <uncommitted or local-only work that must not go out as it is, such as a local `replace` or debug code>.
Not touched: <repos a reader would expect to change, and why they didn't>.

## Merge order

1. **<repo> !<n>**: <why it goes first: what depends on it>.
   Then: <the step between this merge and the next, if any>.
2. ...

## Your actions

1. **<Verb> <object>**: <the link, command or full question with its options>. <What happens next, e.g. "say go and I'll re-pin both consumers".>
```

- Drop the "Not shipping" and "Not touched" lines when they have nothing to say.
- One MR: the merge order is "One MR; nothing to order."
- Nothing left for the user: "Your actions: none." Never invent one.
- Blocking actions first; label the rest "optional".
- Each action works from the message alone. Write the question itself with its choices, never "answer question 2".
- Plain words. No phase codes, internal shorthand or labels the user didn't use.

## Rules

- **Report, don't fix.** Change nothing: no repo, MR or PR, file, memory or process, even to correct a mistake you spot while reading. A fix you find goes in the reply, as a correction or as one of the user's actions.

## Common mistakes

- **Reporting state from memory.** "Nothing is pushed" after a hook pushed, "MR open" an hour after it merged. Read it before you write it.
- **Merge order in the order the work was done.** The order comes from what depends on what. A step without its reason gets merged out of order.
- **A question the user can't answer from the message.** "Decide step 2" sends them back through the session to find out what step 2 was. Write the question and the options in the action.
