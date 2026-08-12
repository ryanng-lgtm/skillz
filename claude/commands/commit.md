Commit the currently staged changes.

Rules:
- Only commit what is already staged (do NOT stage additional unrelated files)
- Group/separate commits logically if necessary — unstage and re-stage subsets when the diff spans distinct concerns
- Keep the description as brief as possible
- Write a short commit message: one summary line + max 3 bullet points in the body
- Keep bullet points simple and direct — no fluff
- Do NOT add any AI/co-authored-by watermark
- If nothing is staged, tell the user and stop

Steps:
1. Run `git diff --cached --stat` to see what's staged. If nothing is staged, stop.
2. Run `git diff --cached` to understand the actual changes.
3. Run `git log --oneline -5` to match the repo's commit style.
4. Write the commit message and commit.