---
name: war-diary
description: Use when updating the Frontend War Diaries from a GitLab activity .atom export and the day's Claude Code sessions — turning a day's GitLab work (pushes, MRs, approvals), in-session work (analysis, planning, docs), and undocumented work into Team/<Name>/ daily-log notes (filed by status into Today/Completed/Investigations and Plans/Running Work) and matching Kanban cards.
---

# War Diary

## Overview

Turn a day of GitLab activity into the Frontend **War Diaries** board: per-person
`Team/<Name>/` notes with a running `## daily log`, and one Kanban card per work
item in `War Diaries.md`.

**Core principle: log reality.** Every log entry traces to a real GitLab action
(commit, MR, approval) or work the user explicitly reports. Never invent progress.

**Three sources, each blind to the others:**
- **`.atom` feed** — a per-user GitLab feed (`https://<host>/<username>.atom`)
  surfaces **review/MR activity** (approvals, MR opens/merges, comments) that local
  `git log` cannot see. It is a **rolling ~20-entry window**: same-day entries age
  out as new ones land, so a day's activity can vanish entirely from a later export.
  Export early, keep each dated export, and **diff successive exports** — the newer
  one is not a superset. Older work it never had needs `git log`.
- **`git log`** — authored commits, including ones not yet in an MR.
- **Claude Code sessions** — analysis, planning, and doc authoring (e.g. Obsidian
  notes) often happen entirely in-session and never touch GitLab. `scan-sessions.py`
  digests the day's transcripts. This includes **VSCode / IDE-extension** sessions:
  they share the same `~/.claude/projects/` store as the CLI, so the scan covers them.

## When to use

- User provides a GitLab `.atom` export and asks to update their war diary / board.
- Triggers: "update my war diary", "log my day", "/war-diary <file>.atom".

## Inputs

1. The `.atom` file path (required for review/MR activity).
2. The vault root: `…/Obsidian/Frontend/War Diaries/` (README + `War Diaries.md` + `Team/`).
3. The person's name → `Team/<Name>/`.
4. The day's Claude Code sessions (auto-scanned from `~/.claude/projects/`, CLI + IDE) — no input needed.

**Read `README.md` in the vault root first** — it is the source of truth for
conventions and changes over time. Follow what it says over this skill if they differ.

## Folder layout (`Team/<Name>/`) — placement matters

Notes are filed into status/type subfolders. The note's **content/creation is unchanged**;
what's new is **where it lives**, and that it **moves** as its status changes.

- **`Today/`** — work done today (from sessions or GitLab activity) that isn't yet
  merged and isn't a pure plan. Default home for new in-progress dev work.
- **`Completed/`** — work merged into `main` / shipped.
- **`Investigations and Plans/`** — pure audits, investigations, and plans (no shipped
  code). **Not carded individually** — they surface on the board as one rollup card,
  `[[Investigations and Plans]]` (the Running Work index below).
- **`Running Work/`** — curated, perpetual notes. **Never create new notes here.** It holds:
  - `Code review & approvals.md` — rolling review/approval log; append review activity
    here, never a per-MR note.
  - `Investigations and Plans.md` — a dated index linking each note in
    `Investigations and Plans/`: `- YYYY-MM-DD: [[Note]]` (group sub-bullets under a date).
    This index **is the single board card** for everything in `Investigations and Plans/`.
  - long-running studies (e.g. `TC Enterprise codebase study.md`).

Wikilinks resolve by **filename**, so a note keeps the same `[[name]]` and the same
board card no matter which subfolder it sits in — moving between folders never breaks
the link.

## Process

### 0. Reconcile board ↔ notes first (notes are the source of truth)
The Kanban plugin / Obsidian sync periodically rewrites, trims, or fully reverts
`War Diaries.md`, dropping cards. The notes are the durable record; the board is
reconstructable from them. Before logging, check every note (across all subfolders)
has a card:
```
cd "<vault root>" && while IFS= read -r n; do \
  grep -qF "[[$n]]" "War Diaries.md" || echo "MISSING CARD: $n"; \
done < <(find "Team/<Name>" -name '*.md' ! -path "*/Investigations and Plans/*" -exec basename {} .md \;)
```
`Investigations and Plans/` notes are excluded — they share the one `[[Investigations
and Plans]]` rollup card. Instead confirm each is listed in `Running Work/Investigations
and Plans.md`. Refill any missing cards (lane = the note's status). If the whole board
reverted to an old state, rebuild this person's cards from their notes and leave everyone
else's cards untouched. If a note's own content reverted (lost daily-log entries), restore
it from this session's record before appending the new day.

### 1. Gather the day's work (all three sources)
- **GitLab feed:** `parse-atom.py FEED.atom --date YYYY-MM-DD` (see `--help`) —
  groups by action, extracts `!NNNN` MR numbers + titles.
- **Commits:** `git log --author="<name>" --since=<date> --date=short` for commits
  not reflected as MRs. Use **MR numbers (`!NNNN`)** over commit hashes when the feed
  gives one. Note the feed's window and say what falls outside it.
- **Claude sessions:** `scan-sessions.py --date YYYY-MM-DD` (add `--grep Obsidian`
  to focus on doc/planning work). Catches in-session work with no GitLab trace —
  architecture studies, port plans, research notes. Covers CLI **and VSCode/IDE**
  sessions (shared store). Read the digest for intent + files touched; map
  files-under-`Obsidian/` to a work item.

### 2. Confirm + fill gaps with the user
The three sources cover most of it. Still ask for anything they leave out —
meetings, decisions, pairing. Treat the session digest as leads to confirm, not
facts to log verbatim. Do not fabricate; if they add nothing, skip.

### 3. Compile → place the note (ASK if unsure)
Group work by **work item / theme**, not per-commit. Then, per theme:

1. **Relates to an existing note** (search ALL subfolders of `Team/<Name>/`) → update
   that note in place: append `- YYYY-MM-DD — what happened (!NNNN)` under `## daily log`
   (respect existing `### sub-headings`; on a shared item prefix the name
   `- 2026-06-16 #alice — …`). Then **re-file** it if its status changed (step 5).
   Never make a duplicate.
2. **New note** → create it (title/body as before: `# <Title>`, area prefix optional,
   then `## daily log`), and place it by type/status:

| Today's work is… | Where it goes |
|---|---|
| review / approval activity | **no new note** — append to `Running Work/Code review & approvals.md` |
| a pure audit / investigation / plan | new note in **`Investigations and Plans/`**, AND add `- YYYY-MM-DD: [[Note]]` to `Running Work/Investigations and Plans.md` |
| already merged into `main` / shipped | new note in **`Completed/`** |
| otherwise (in-progress dev work today) | new note in **`Today/`** |

**Never create notes in `Running Work/`** — only update the curated ones there.

### 4. Decide each card's lane
Lane = status. Infer, then **confirm with the user** — only they know true status.

| Signal | Lane | Usual folder |
|--------|------|--------------|
| MR merged / shipped to prod | Done | `Completed/` |
| MR open, awaiting review | In Review | `Today/` or `Investigations and Plans/` |
| Branch pushed, no MR yet / actively coding | In Progress | `Today/` |
| Ongoing/continuous (e.g. code review) | In Progress | `Running Work/` |
| Queued, not begun | Not Started | — |

Folder and lane usually line up, but the **user's status call wins** — keep them consistent.

### 5. Add / move the Kanban card + re-file the note
Edit `War Diaries.md`. **Card model:** `Today/`, `Completed/`, and In-Review items each
get their own card; `Running Work/` notes each have one (Code review & approvals, the
Investigations index, long-running studies). `Investigations and Plans/` notes do **not** —
they roll up under the single `[[Investigations and Plans]]` card, so instead add them to
`Running Work/Investigations and Plans.md`.
- New card-bearing note → add a card. Existing note whose status changed → move its card's lane.
- Card shape (tag line is **tab-indented**):
  ```
  - [ ] [[Note Filename Without Extension]]
  	#name
  ```
- **The wikilink text MUST equal the note filename exactly** (minus `.md`) or the link
  won't resolve. Subfolder doesn't matter (filename resolution); a rename does — re-read
  the board and align.
- Match the board's existing whitespace exactly (tabs, blank lines between lanes).
- **Re-file the note** to match its status: a `Today/` item that merged → move to
  `Completed/` (and set its card to Done); an investigation that ships → `Completed/`.
  Moving folders does not change the card link, but the lane must follow the status.
- Two owners on one item → both tags on one card (`#alice #bob`), note in the driver's
  folder, both log into it. Never a second card/note for the same thing.

## Common mistakes

- **Note created, card forgotten.** Every note needs a matching board card. Do step 5.
- **New note in the wrong folder.** Place by status/type (step 3); never create notes in
  `Running Work/`. Pure plans/audits → `Investigations and Plans/` + the dated index entry.
- **Forgetting to re-file.** When a `Today/` item merges, move it to `Completed/` and set
  its card to Done. Re-file every run, not just on creation.
- **Per-MR review notes.** Review/approval activity is one rolling note —
  `Running Work/Code review & approvals.md` — not a note per MR.
- **Wikilink ≠ filename.** Renamed notes break links; re-read the board and align. (Folder moves are safe.)
- **Commit hash where an MR exists.** Prefer `(!NNNN)` — clickable, matches team style.
- **Trusting the board's card set.** It gets trimmed/reverted; reconcile from notes (step 0) before and after.
- **Treating a newer `.atom` as a superset.** Rolling window; earlier same-day entries roll off — diff exports.
- **Logging only GitLab.** In-session analysis/planning/docs (CLI or VSCode) leave no commit; run `scan-sessions.py`.

## Files
- `parse-atom.py` — categorize a `.atom` feed (`--date`, `--since`, `--json`). Run `--help`.
- `scan-sessions.py` — digest the day's Claude Code sessions (CLI + VSCode/IDE, shared
  `~/.claude/projects/`): intent, files touched, commits (`--date`, `--grep`, `--base`). Run `--help`.
