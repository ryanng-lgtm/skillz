# Docs index

The starting point for "what exists and where is the detail". Conventions are
in [CLAUDE.md](./CLAUDE.md), and personal context about the owner is in
[ABOUT.md](./ABOUT.md).

**When to read it:** before any substantial work, skim this file. If a
session produces something durable (an app, a cron job, a data store, an
infra decision), record it in the same turn:

- For an existing area: add or update a doc there and run the index script.
- For something new: create an area folder, or list it under "Without an
  area folder yet".

**How to look something up:**

1. Scan the area table below and open the matching area's `INDEX.md`. It lists
   each doc's description and tags, the same way a skill's frontmatter works.
2. Open only the doc that matches.
3. For a blind search across everything, grep the docs dir. To search
   descriptions and tags only, grep `^(description|tags):.*<term>`.

The area table is **generated** from each area's `INDEX.md` frontmatter by
`python3 scripts/build-index.py`, so don't edit it by hand.

## Areas

<!-- BEGIN GENERATED (scripts/build-index.py) -->
<!-- END GENERATED -->

## Without an area folder yet

Things that exist (a skill, a cron job) but have no docs. Give one an area
folder when it gets its first doc.
