Generate a condensed MR markdown for the changes on the current branch.

Rules:
- Final output must be a single inline markdown code block the user can click to copy/paste.
- No file hyperlinks anywhere — refer to files/symbols using backtick code spans (e.g. `sentry.util.ts`, `V2StreamingError`).
- Keep the final markdown brief — terse bullet points, no fluff. Match length to change size; a small change gets a few short bullets.
- Write so a non-technical reader understands it. Describe user-facing behavior and impact, not implementation. Avoid jargon (chunk, lazy-load, fall-through, refs); name files/symbols only when they add clarity.
- First line of the code block is the MR title: imperative, ≤ 72 chars, no trailing period. Match the repo's commit convention if it has one (e.g. Conventional Commits `type(scope): summary`). Blank line after it, then the sections.
- Below the title, exactly four sections: `## Summary`, `## Problem`, `## Solution`, `## How to test`.
- `## How to test` must be numbered steps a reviewer can follow in whatever form the project runs — app, service, CLI, library test suite: where to go, what to do, what to look for. Prefer steps that mirror how the change was actually reproduced/verified during the session over steps invented from the diff.

Steps:
1. Determine the base branch (usually `main`) and run `git log --oneline <base>..HEAD` plus `git diff <base>..HEAD --stat` to understand what changed on the branch. Read commit messages and diffs as needed to understand what changed, why it changed, and what the changes do.

2. Recall the current session's context for testing evidence: the symptom/bug that was reproduced, the exact steps or scenario used to reproduce it, how the fix was verified (manual steps, test runs, probes), and any setup preconditions (env vars, feature flags, fixtures, required accounts or data). If this session has no relevant context (e.g. fresh session), infer plausible test steps from the diff and commit messages instead, and keep them conservative.

3. Draft an MR markdown from that rundown: the title line, then four sections:
   - `## Summary` — one or two sentences on the overall change.
   - `## Problem` — what was broken / missing / motivating the work.
   - `## Solution` — what the change does, as bullet points.
   - `## How to test` — numbered, concrete verification steps from step 2, including the expected result at the end (what the reviewer should see when it works). Note preconditions first if any.

4. Simplify the draft in at least 3 passes, keeping the title and all four sections each time:
   - Pass 1 — cut: remove repetition, filler, and any bullet that doesn't change what the reader knows.
   - Pass 2 — de-jargon: reread as a non-technical reader; replace remaining jargon with plain words, drop implementation detail that doesn't affect behavior.
   - Pass 3 — shorten: compress what's left to the shortest version that still conveys intent.
   Repeat if a pass still finds things to fix.

5. Strip any markdown file hyperlinks (`[text](path)`) and replace with backtick code spans of just the filename or symbol. Then output the entire MR markdown wrapped inside a single fenced ```markdown code block so the user can click to copy.
