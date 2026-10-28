---
name: mr-markdown
description: Generate a condensed MR markdown for the changes on the current branch. Use when the user invokes /mr-markdown or $mr-markdown, or asks for an MR/PR description for the branch — a single copyable code block with title, Summary, Problem, Solution, and How to test.
---

# MR markdown

Generate a condensed MR markdown for the changes on the current branch.

Rules:
- Final output must be a single inline markdown code block the user can click to copy/paste.
- No file hyperlinks anywhere — refer to files/symbols using backtick code spans (e.g. `sentry.util.ts`, `V2StreamingError`). The only links are related MRs, under `## Dependencies`.
- The final MR is at most 200 words, not counting a diagram. Match length to change size: a small change needs far fewer.
- Write so a non-technical reader understands it. Describe user-facing behavior and impact, not implementation. Avoid jargon (chunk, lazy-load, fall-through, refs); name files/symbols only when they add clarity.
- First line of the code block is the MR title: imperative, ≤ 72 chars, no trailing period. Match the repo's commit convention if it has one (e.g. Conventional Commits `type(scope): summary`). Blank line after it, then the sections.
- Below the title, four sections: `## Summary`, `## Problem`, `## Solution`, `## How to test`. Add `## Dependencies` between Solution and How to test when the change has related MRs.
- `## How to test` must be numbered steps a reviewer can follow in whatever form the project runs — app, service, CLI, library test suite: where to go, what to do, what to look for. Prefer steps that mirror how the change was actually reproduced/verified during the session over steps invented from the diff.

The MR is written in three stages. Each stage saves its version to a file in a working directory, and the next stage starts from that file. Create the directory with `mktemp -d "<parent>/mr-markdown.XXXXXX"`, where `<parent>` is this session's scratchpad directory, else `${TMPDIR:-/tmp}`. `<dir>` below is the path it prints. Delete it once the final block is printed.

Steps:
1. Determine the base branch (usually `main`) and run `git log --oneline <base>..HEAD` plus `git diff <base>..HEAD --stat` to understand what changed on the branch. Read commit messages and diffs as needed to understand what changed, why it changed, and what the changes do.

2. Recall the current session's context for testing evidence: the symptom/bug that was reproduced, the exact steps or scenario used to reproduce it, how the fix was verified (manual steps, test runs, probes), and any setup preconditions (env vars, feature flags, fixtures, required accounts or data). If this session has no relevant context (e.g. fresh session), infer plausible test steps from the diff and commit messages instead, and keep them conservative.

3. **Stage 1, full draft** (`<dir>/1-draft.md`). Use as many words as the change needs. The title line, then:
   - `## Summary` — one or two sentences on the overall change. Add a mermaid diagram only when the user asked for one, or when the change reworks a flow that those sentences cannot make clear. Most MRs have no diagram.
   - `## Problem` — what was broken / missing / motivating the work.
   - `## Solution` — what the change does, as bullet points.
   - `## Dependencies`, only when the change has related MRs: one this MR needs merged first, one that needs this MR, or the same change in another repo. Find them in the session and in the branch's target (a target other than the default branch is another MR's branch). One bullet per MR: its full GitLab reference (`openmarketxyz/go-backend/kiyotaka-go!79`, or `!79` within the same project), which GitLab renders as a link, then how it relates, merge order first, saying when it has already merged. Take references from the session or `glab`, never guess one.
   - `## How to test` — numbered, concrete verification steps from step 2, including the expected result at the end (what the reviewer should see when it works). Note preconditions first if any.

4. **Stage 2, cut to 200 words** (`<dir>/2-short.md`). Cut content, never grammar: drop repetition, implementation detail that does not change behavior, and any sentence or bullet that does not change what the reader knows. Sentences stay whole. The title, every section, each test step's expected result and every dependency stay. Count the words outside a diagram:

   ```bash
   perl -0pe 's/^\x60{3}mermaid.*?^\x60{3}//msg' <dir>/2-short.md | wc -w
   ```

5. **Stage 3, make it read like a person wrote it** (`<dir>/3-final.md`). Rewrite every sentence that has:
   - A semicolon, or a dash used as punctuation (`—`, `–`, ` - `). Make it two sentences, or use a comma or parentheses.
   - Ultra-condensed wording: dropped articles, fragments standing in for sentences, colon-chained lists, arrows, `w/`, `&` or `+` for "and", slash pairs such as `read/write`, made-up abbreviations. "A fraction, like the other ratios. Under two bars: NULL." becomes "Like the other ratios it is a fraction, and it is NULL for a market with fewer than two bars."
   - Jargon a reviewer from another team would stop at. Use the plain word. File, symbol and flag names stay exact.
   - AI prose: "ensure", "robust", "seamless", "leverage", "comprehensive", "not just X but Y", lists of three, a trailing ", ensuring …" clause, a closing recap. The full list is in `~/.codex/skills/humanize/references/tells.md`, and the doc register in `voice.md` beside it is how Ryan writes MRs.

   Then the stage 2 count on `3-final.md` is still 200 or less, and this prints nothing (code is skipped):

   ```bash
   perl -0pe 's/^\x60{3}.*?^\x60{3}//msg; s/\x60[^\x60\n]*\x60//g' <dir>/3-final.md | grep -E ';|—|–|→|->|[^[:space:]] - '
   ```

   If a fix pushes the count over 200, cut more content. Never go back to fragments.

6. Replace any markdown file hyperlinks (`[text](path)`) in `3-final.md` with backtick code spans of just the filename or symbol. Then output it wrapped inside a single fenced ```markdown code block so the user can click to copy. When the MR has a fenced block of its own, such as a diagram, the outer fence takes four backticks. Then delete `<dir>`.
