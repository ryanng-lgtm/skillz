# Docs knowledge base — conventions

Default documentation directory. Durable operational notes live here:
things learned once that would otherwise cost a round trip to rediscover.
Memory only holds a pointer to `INDEX.md`, so this directory is the source
of truth for "what exists".

**Start at `INDEX.md`.** Read it before substantial work, and record anything
durable (an app, a cron job, a data store, an infra decision) in the same
turn it's produced.

## Layout

```
INDEX.md                  top level: how to look things up + generated area table
ABOUT.md                  who the owner is (personal context)
CLAUDE.md                 this file
scripts/build-index.py    regenerates every INDEX.md table from frontmatter
<area>/INDEX.md           area frontmatter + generated table of its docs (and sub-areas)
<area>/NNN Title.md       the docs
<area>/<sub>/INDEX.md     optional sub-area, same shape (e.g. shopping/clothes-hunting/)
<area>/<sub>/NNN Title.md its docs, numbered per sub-area
```

- An **area** is one project or one infra domain (e.g. `calorie-tracker/`,
  `k3s/`). Folder names are lowercase and kebab-case.
- Create an area when its first doc is written. Every numbered doc lives in
  an area; none sit at the top level.
- **Sub-areas** nest a specific effort under a general area: the general
  area holds the reusable tooling and rules, and the sub-area holds what's
  specific to one effort. For example, `shopping/` holds shop access and
  browsing, and `shopping/clothes-hunting/` holds the garment briefs.
  - Use a sub-area for that split, or once an area gets unwieldy (roughly 10+
    docs).
  - `build-index.py` handles any depth. A parent's INDEX gets a generated
    sub-area table. The top-level table lists only top areas, and their doc
    counts include sub-areas.
  - Cross-reference a sub-area doc as `[clothes-hunting/001]` from its parent,
    or `[shopping/clothes-hunting/001]` from elsewhere, with a relative link
    definition.

## Frontmatter (required)

Every doc starts with this block. It works like skill frontmatter: the
indexes are built from it, so a reader can decide whether to open a doc
without reading its body.

```yaml
---
description: "What's in it and when to read it, in one or two sentences. Name the concrete things someone would search for."
tags: [area-name, topic, tool, table-name]
status: current            # or: superseded by NNN
updated: YYYY-MM-DD
host: myhost (192.168.0.10)     # optional
---

# Title
```

- **`description` is the part that matters most.** Write it for a reader who
  doesn't know the doc exists. Update it in the same change as the body
  whenever the scope shifts.
- Tags are lowercase and kebab-case. The first tag is the area, followed by
  the search terms someone would actually use: tools, table names, concepts.
- Each area's `INDEX.md` has the same frontmatter plus `related:` (skills,
  cron jobs, URLs, repo paths) and optionally `improvement:` plus
  `tooling:` (see "Continuous improvement"). Beneath it go a line or two of reading order
  and the generated table.

**After adding, moving or renaming a doc, or editing its frontmatter**, run:

```bash
python3 <docs>/scripts/build-index.py          # rewrite the tables
python3 <docs>/scripts/build-index.py --check  # validate only
```

The script rewrites only the `## Contents` section, up to the next heading. It
fails on:

- missing frontmatter fields
- undefined `[NNN]` references
- broken relative links
- a numbered doc sitting at the top level

## Filenames and links

- Name docs `NNN Title In Title Case.md`. `NNN` is zero-padded and numbered
  **per area**, in order of creation starting at `001`. The next number is
  the highest in that folder plus one. Never reuse or renumber, because the
  number is an identity, not a ranking.
- Filenames use spaces, not hyphens. Quote the paths in shell commands.
- Cross-references use reference-style links. Within the area, write `[002]`
  with a definition `[002]: ./002%20Title.md`. Across areas, write `[k3s/002]`
  with `[k3s/002]: ../k3s/002%20Title.md`. Put the definitions at the bottom
  of the doc.
- In an Obsidian vault, use the vault's own link style instead: wikilinks
  (`[[k3s/002 Title]]`) or inline markdown links. Obsidian's graph,
  backlinks and rename updates skip reference-style definitions.
  `build-index.py` checks wikilinks and embeds as well, and reports a bare
  `[[Title]]` that matches more than one file.
- **Temporary docs** (handoffs, one-off briefings, requests for another agent
  or a human) are named `TMP Title.md`, with no number and no frontmatter.
  - The script ignores them.
  - Once they've been acted on, fold any lasting facts into a numbered doc
    and delete the TMP file.
  - Never cite one as a source of truth.

## Content

- **Facts, not a ledger.** Docs describe current state, rules, data
  contracts and decisions with their one-line reason. The history of how
  something got that way belongs in git or session history, not here.
  - Routine fixes aren't recorded.
  - A gotcha is recorded only if it cost real time, with the failure mode
    stated specifically.
- A useful shape, loosely: decision/outcome → how it's set up (paths, config,
  exact working commands) → gotchas.
- Record measured numbers, not estimates, and say when something was
  verified.
- **Split a doc** when a part of it is regularly needed on its own. A single
  file that has to be read end to end is fine.
- Per-repo working notes go in that repo's own `CLAUDE.md`, not here.

## Continuous improvement

An area whose `INDEX.md` frontmatter has `improvement: continuous` lets
the agent extend that project's tooling on its own, without asking first.
`off` (or no field) means every change is proposed first. The flag goes on
the area only, never on individual docs. Only the owner sets or changes it.

A `continuous` area must also name its tooling dir:

```yaml
improvement: continuous
tooling: ~/workspace/calorie-tracker-ui/hermes
```

The tooling dir is the only place the mode lets the agent change code on its
own. It must be inside a git repo and hold:

- `README.md`: what the tooling is and the exact test command.
- `tests/`: tests that must pass before every commit.
- `BY-HAND.md`: the by-hand list (below).

`build-index.py` enforces all of this: an unknown mode, a missing
`tooling:`, a dir outside git, or a missing file fails the check. Once any
area is `continuous`, the top-level index shows each area's mode.

### The by-hand list (`BY-HAND.md`)

This is how repeat needs are told apart from one-offs.

- **When:** the agent had to do something with ad-hoc code or SQL because the
  tooling had no command for it.
- **Before doing it**, read the list. If the need is already there, it's
  the second occurrence: build it as a feature and delete the line.
  Otherwise, add a line.
- **Format:** one line per need, `- YYYY-MM-DD: <need> — <what was done>`.
  Describe the need, not the exact command, so a similar request matches it
  later.
- **Pruning:** lines older than ~60 days that never recurred are deleted,
  because they were one-offs.
- The file is committed with the tooling, and keeps only a one-line header
  pointing here, so the rules live in one place.

### What qualifies

A feature the agent itself needs while working on the project, and will need
again:

- **Recurring by nature** (a scheduled report, a check run every session):
  build it on first need, with no by-hand entry.
- **Otherwise, build it the second time** (see the by-hand list).
- **Extend what exists** (a new command in the existing CLI) rather than
  adding scripts. A one-off query is never committed.

### Allowed without asking

- Add or improve commands, scripts and their tests in the tooling dir.
- Update the matching skill and docs.
- Fix bugs in that tooling.

### Still needs the owner's approval

- Schema migrations. Apps share their DBs with the agent.
- Deploys: the plan/apply gate is unchanged.
- Deleting or rewriting stored data.
- Changing how an existing feature behaves for the owner, as opposed to how it
  works for the agent.
- New cron jobs, or anything that messages the owner on a schedule.
- New dependencies, and anything outside the tooling dir.

### How

1. Tests must pass before every commit, and new commands get tests.
2. Each commit message starts with the agent's name as a prefix (e.g.
   `hermes:`).
3. Test against a copy of any live data, never the real store.
4. Don't change it silently: tell the owner in one line in the reply of the turn
   it happened, e.g. "added a `week` command to calorie.py".

## Maintenance

This directory is a git repo (local, branch `main`). Commit after each
change with a short message saying what changed. Run `build-index.py --check`
first. Commits are the history, so docs stay facts, not a ledger.

- Small corrections: edit in place and bump `updated`.
- A reversed decision: write a new doc, set the old one's `status:
  superseded by NNN`, and link forward from it.
