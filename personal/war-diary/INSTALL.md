# Install the `war-diary` Claude Code skill

Paste this message into a fresh Claude Code session. You've been given three files
alongside it: `SKILL.md`, `parse-atom.py`, and `scan-sessions.py`.

---

You are helping me install a personal Claude Code **skill** called `war-diary`. A
skill is a folder under `~/.claude/skills/<name>/` containing a `SKILL.md` plus
optional helper scripts; Claude Code auto-discovers it on the next session.

I have three files for it: `SKILL.md`, `parse-atom.py`, `scan-sessions.py`. Do this:

1. Create the directory `~/.claude/skills/war-diary/`.
2. Place all three files inside it, keeping their exact names:
   - `~/.claude/skills/war-diary/SKILL.md`
   - `~/.claude/skills/war-diary/parse-atom.py`
   - `~/.claude/skills/war-diary/scan-sessions.py`
   (If you don't have the file contents directly, ask me for them or for their
   current location, then move/copy them in.)
3. Make the scripts executable:
   `chmod +x ~/.claude/skills/war-diary/parse-atom.py ~/.claude/skills/war-diary/scan-sessions.py`
4. Verify:
   - `python3 ~/.claude/skills/war-diary/parse-atom.py --help` prints usage.
   - `python3 ~/.claude/skills/war-diary/scan-sessions.py --help` prints usage.
   - `~/.claude/skills/war-diary/SKILL.md` begins with `---` frontmatter containing `name: war-diary`.
5. Confirm it's installed and tell me I can invoke it with `/war-diary` or by saying
   "update my war diary" and providing my GitLab activity `.atom` file.

## What it does
Turns a day of work into per-person `Team/<Name>/` daily-log notes plus matching
Kanban cards on a "War Diaries" Obsidian board, pulling from three sources:
- a GitLab per-user `.atom` feed (approvals / MR opens-merges / comments),
- `git log` (authored commits),
- the day's Claude Code session transcripts (in-session analysis/planning/docs that
  never hit GitLab).

## What I need to supply at run time
- My GitLab activity feed: download from `https://<my-gitlab-host>/<my-username>.atom`.
- My Obsidian vault path for the War Diaries board.

## Portability notes
- The scripts have no hardcoded personal paths. `scan-sessions.py` defaults to
  `~/.claude/projects`; `parse-atom.py` takes the feed path as an argument.
- `SKILL.md` assumes a specific team layout: an Obsidian vault at
  `…/Obsidian/Frontend/War Diaries/` with a `README.md`, a `War Diaries.md` Kanban
  board, and per-person `Team/<Name>/` notes. If my board layout differs, tell me
  which parts of `SKILL.md` to adjust (vault path, lane names, note conventions).
- Requires `python3` (standard library only — no pip installs).
