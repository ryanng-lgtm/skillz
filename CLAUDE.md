# CLAUDE.md

This repository is the single source of truth for Ryan's agent setup: skills and global instructions for Claude Code and Codex. `install.sh` symlinks everything into `~/.claude` and `~/.codex`, so an edit here is live on this machine immediately and on other machines after their next pull.

## Layout

- `claude/skills/<name>/SKILL.md` — a Claude skill, plus any scripts or references it ships. `install.sh` links only directories that contain a `SKILL.md`. A slash command is a skill too: Claude Code gives every skill a `/name`, so do not add a `commands/` directory.
- `codex/skills/<name>` — a Codex skill. A skill that works the same under both agents is stored once in `claude/skills/`, with a relative symlink here (`../../claude/skills/<name>`), and written for both agents (name both triggers, `/name` and `$name`). It can carry `agents/openai.yaml` for Codex's skill list. Keep a separate copy only when the Codex version has to differ.
- `claude/CLAUDE.md` and `codex/AGENTS.md` — global instructions, linked to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`. They load in every project, so guidance about this repo belongs in this file, not there. They carry the same rules in each agent's terms; change one, change the other.

The skill name is its directory name and must match the `name` field in the frontmatter. Frontmatter requires `name` and `description`. The `description` carries the trigger phrases that decide when the skill fires, so write it to be matched against, not skimmed.

`openmarket` and `om-chat` ship with the `om` CLI and are vendored here only so both agents get the same copy. Do not edit them by hand.

## Adding, removing, or renaming a skill

Update the matching table in `README.md` (Claude or Codex) in the same change. The tables are the only full list; a skill missing from them is invisible. The vendored skills are the one exception.

On a rename or removal, also update every mention of the old name in `claude/CLAUDE.md`, `codex/AGENTS.md`, and other skills, and remove the Codex symlink if there is one. `install.sh` drops the dead links it leaves under `~/.claude` and `~/.codex`.

## Editing docs

`README.md`, this file, and skill bodies describe the present state, not the history of how they got there. Use the `writing-instructions` skill, when it is installed, for skill bodies and instruction files.

## Sync

A Claude Code `Stop` hook runs `sync.sh` at the end of every turn. It stages everything with `git add -A`, commits, and pushes to `origin/main`.

- Anything left in the working tree when a turn ends is published. Keep scratch files outside the repo.
- Commit a finished change yourself with the `commit` skill, so it gets a real message. Otherwise sync commits it as `skills(<name>): update (…)`.
- `touch .sync-hold` pauses syncing; `rm .sync-hold` resumes it.
- Never force-push. Other machines push here too. On a rebase conflict, sync leaves a `.sync-conflict` note; resolve it as the note says.

## Verifying a change

- After adding, renaming, or removing a skill, run `./install.sh --links-only`. It must report no `SKIP` lines, and the new links under `~/.claude/skills/` and `~/.codex/skills/` must resolve into this repo. Run plain `./install.sh` after changing `install.sh` or `hook-install.sh`.
- A skill that ships tests keeps them in `scripts/tests/`. After changing that skill, run `python3 -m unittest discover -s tests` from its `scripts/` directory.
