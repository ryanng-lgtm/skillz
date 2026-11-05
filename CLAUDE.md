# CLAUDE.md

This repository is the single source of truth for Ryan's agent setup: skills and global instructions for Claude Code and Codex. Its shared half is also the `skillz` plugin that other developers install from GitHub. `install.sh` symlinks everything into `~/.claude` and `~/.codex`, so an edit here is live on this machine immediately, on Ryan's other machines after their next pull, and for plugin users at their next update.

## Layout

- `shared/` — the `skillz` plugin: everything a plugin install copies, and nothing else. Its manifests are `shared/.claude-plugin/plugin.json` and `shared/.codex-plugin/plugin.json`. Neither sets a `version`, so every push reaches plugin users.
- `shared/skills/<name>/SKILL.md` — a skill whose job works for anyone, in any codebase, plus any scripts or references it ships. `install.sh` links only directories that contain a `SKILL.md`. A slash command is a skill too: Claude Code gives every skill a `/name`, so do not add a `commands/` directory.
- `personal/<name>/SKILL.md` — a skill tied to Ryan's own products, services or machines, or vendored from another tool. Same layout; not in the plugin.
- `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` — the Claude Code and Codex marketplaces, each with one entry whose source is `./shared`. Both marketplaces, both entries and both manifests are named `skillz`.
- `codex/skills/<name>` — a Codex skill on Ryan's machines. A skill that works the same under both agents is stored once in `shared/skills/` or `personal/`, with a relative symlink here (`../../shared/skills/<name>` or `../../personal/<name>`), and written for both agents (name both triggers, `/name` and `$name`). It can carry `agents/openai.yaml` for Codex's skill list. Keep a separate copy only when the Codex version has to differ.
- `claude/CLAUDE.md` and `codex/AGENTS.md` — Ryan's global instructions, linked to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`. They load in every project, so guidance about this repo belongs in this file, not there. They carry the same rules in each agent's terms; change one, change the other.

Every skill follows `templates/skill-template.md` for its frontmatter, body, and supporting files. Read it before writing a skill or restructuring one.

`openmarket`, `om-chat`, `graphify` and `desloppify` are vendored from the tools that ship them. Do not edit them by hand. `desloppify` is upstream's `docs/SKILL.md` plus that agent's overlay (`docs/CLAUDE.md` or `docs/CODEX.md`), with upstream's `LICENSE` beside it, which its license requires.

## Shared skills hold nothing personal

The repo is public and every plugin user gets all of `shared/`. A shared skill holds no personal data, no paths of Ryan's, nothing specific to his employer, and no symlink or reference to a file outside `shared/`. `check.py` fails on the markers it lists and on any symlink in `shared/`.

- Anything personal a shared skill needs (a folder, a voice profile, a list of repos) is a Skill setting: a `- <Key>: <value>` line under `## Skill settings` in `~/.claude/CLAUDE.md` (Claude Code) or `~/.codex/AGENTS.md` (Codex). When the line is missing, the skill asks once and offers to add it. It never falls back to a built-in value. A new key goes in the README's Skill settings table, with Ryan's value in both global files.
- A shared skill names its own files as `${CLAUDE_SKILL_DIR}/scripts/x.sh` and says that under Codex the path is relative to the SKILL.md folder. Never `~/.claude/skills/<name>/...`: a plugin install lives in a versioned cache.
- A shared skill calls another by name ("run the commit skill"), not as `/commit`, because plugin users have it as `/skillz:commit`.

## Adding, removing, or renaming a skill

1. Pick the folder: `shared/skills/` when the skill works for anyone with only Skill settings to fill in, `personal/` otherwise.
2. Write it from the template. For a skill only the user should start, such as a one-time setup or one with side effects, set `disable-model-invocation: true` in the frontmatter and add the `agents/openai.yaml` policy the template shows, which is Codex's equivalent.
3. If it works the same under Codex, add its `codex/skills/` link.
4. Add its row to the `README.md` Shared skills or Personal skills table in the same change. Those tables are the only full list; a skill missing from them is invisible. The vendored `openmarket` and `om-chat` are the one exception. `export.py` zips `shared/` for Claude Desktop.

On a rename or removal, also update every mention of the old name in `claude/CLAUDE.md`, `codex/AGENTS.md`, and other skills, and remove the Codex symlink if there is one. `install.sh` drops the dead links it leaves under `~/.claude` and `~/.codex`.

## Editing docs

`README.md`, this file, and skill bodies describe the present state, not the history of how they got there. The README is for developers installing the plugin first; Ryan's own setup comes after. Use the `writing-instructions` skill, when it is installed, for skill bodies and instruction files.

## Sync

A Claude Code `Stop` hook runs `sync.sh` at the end of every turn. It stages everything with `git add -A`, commits, and pushes to `origin/main`.

- Anything left in the working tree when a turn ends is published. Keep scratch files outside the repo.
- Commit a finished change yourself with the `commit` skill, so it gets a real message. Otherwise sync commits it as `skills(<name>): update (…)`.
- While `check.py` reports a problem, sync commits and pushes nothing and writes the report to `.sync-check`. Fix what it lists and the next sync goes out.
- `touch .sync-hold` pauses syncing; `rm .sync-hold` resumes it.
- Never force-push. Other machines push here too. On a rebase conflict, sync leaves a `.sync-conflict` note; resolve it as the note says.

## Verifying a change

- After changing a skill, `README.md`, or a global instruction file, run `python3 -I check.py`. It checks every skill against the template, the Codex symlinks, the README Shared skills and Personal skills tables, the `~/.claude/skills/...` paths that docs and scripts name, the plugin manifests, and `shared/` for personal markers and symlinks. It must print no problems.
- After changing anything in `shared/` or a marketplace file, run `claude plugin validate .` (the marketplace) and `claude plugin validate ./shared` (the plugin). Both must end in "Validation passed". The missing `version` warning and the plugin directory's notes (license, icon) are expected, since the plugin is not submitted to that directory.
- After adding, renaming, or removing a skill, run `./install.sh --links-only`. It must report no `SKIP` lines, and the new links under `~/.claude/skills/` and `~/.codex/skills/` must resolve into this repo. Run plain `./install.sh` after changing `install.sh` or `hook-install.sh`.
- Before and after trimming a skill, run `python3 -I usage.py`. It reads the last 30 days of transcripts and prints how often each skill ran, how many tokens its text loads, and what its description adds to every session.
- A skill that ships tests keeps them in `scripts/tests/`. After changing that skill, run `python3 -m unittest discover -s tests` from its `scripts/` directory.
