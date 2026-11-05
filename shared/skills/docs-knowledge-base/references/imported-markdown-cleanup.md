# Cleaning up imported markdown

Docs converted from Word/Google Docs (pandoc-style) arrive with damage that
renders badly and is hard for an agent to parse. Look for:

- **Squashed lists:** `The app should: - increase X; - reduce Y; - ...` or
  `Recommended sequence: 1. A. 2. B.` inside one wrapped paragraph.
- **Double-hyphen dashes:** `2--4`, `A--M` (should be `2–4`).
- **Fence info strings with a space:** ```` ``` json ```` (should be
  ```` ```json ````).
- **Padded numbered items:** `1.  Full-screen PWA.`
- A leftover unnumbered import stub beside the numbered docs. The checker
  doesn't catch it.

Decisions documents the owner pastes in later (e.g. a V0 decisions file) have the
same damage. Fold their content into the topic docs as clean lists. Don't
copy the damage across.

## Fix it with a script, not by hand

Process each doc body paragraph by paragraph (split on blank lines, skip
frontmatter, fenced code, headings, `>` quotes, tables and `[NNN]:` link
definitions):

1. Join the paragraph's lines, then replace `(?<=\w)--(?=\w)` with `–`.
2. If it matches `^(.*?:)\s(-\s.*)$`, split the tail on `(?:^|\s)-\s`,
   strip trailing `;`, and emit the lead-in, a blank line, then `- item`
   lines.
3. If it matches `^(.*?:)\s(1\.\s.*)$`, split on `(?:^|\s)\d+\.\s` and
   emit a numbered list.
4. Otherwise re-wrap it with `textwrap.fill(width=76,
   break_on_hyphens=False)`, using hanging indents for list items.
5. Replace ```` ```\s+(\w+) ```` with ```` ```\1 ````, and collapse 3+
   newlines to 2.

Afterwards:

- grep for leftover `--` outside frontmatter. Numbered-list lines were
  skipped by step 1, so fix them separately.
- Print every changed body and read it once before committing. Lead-ins
  like `Home: - a - b` inside an example become `Home:` plus a list, which
  is correct, but check for any list that was split in the wrong place.
- Run `build-index.py --check`, then commit.

For the one-match `rep` helper and write-at-the-end pattern, see
"Scripted multi-doc edits" in SKILL.md (under "Writing or updating docs").
