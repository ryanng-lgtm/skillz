# skillz

Agent skills and instructions, shared across machines. One source of truth for
Claude Code (`~/.claude`) and Codex (`~/.codex`); each machine symlinks into it
rather than keeping its own copy.

## Setup on a new machine

```bash
git clone git@github.com:ryanng-lgtm/skillz.git ~/Documents/github/skillz
cd ~/Documents/github/skillz
./install.sh
```

That links every skill, command, and instruction file into `~/.claude` and
`~/.codex`, and registers the auto-sync hook. Re-run it any time — it refreshes
links and never touches skills this repo doesn't own.

If a skill directory already exists as real files on that machine, `install.sh`
adopts it when the contents match and reports it otherwise. `--force` replaces
it, keeping a `.local-<timestamp>` backup alongside.

## Layout

```
claude/
  CLAUDE.md      global instructions        → ~/.claude/CLAUDE.md
  commands/      slash commands             → ~/.claude/commands/
  skills/        skills                     → ~/.claude/skills/<name>
codex/
  AGENTS.md      global instructions        → ~/.codex/AGENTS.md
  skills/        skills                     → ~/.codex/skills/<name>
```

`codex/skills/om-chat` and `codex/skills/openmarket` are relative symlinks into
`claude/skills/`. Those two are identical across both agents, so they're stored
once; `graphify` genuinely differs between them and is stored twice.

## Sync

`hook.sh` runs as a Claude Code `PostToolUse` hook. Any edit that resolves to a
path inside this repo — including edits made through the `~/.claude/skills`
symlinks — fires `sync.sh`, which commits and pushes in the background.

`sync.sh` never force-pushes. It rebases onto the remote first; on a conflict it
stops, keeps your commit local, and writes `.sync-conflict` with instructions.
Run it by hand any time:

```bash
./sync.sh
```

Changes made outside Claude Code (a text editor, another CLI) don't trip the
hook. Run `./sync.sh` after those.

To pause automatic pushing on a machine — working offline, or mid-way through a
change you don't want published yet:

```bash
touch .sync-hold     # sync.sh becomes a no-op
rm .sync-hold        # resume
```

## Deliberately not in this repo

- **`settings.json` / `config.toml`** — they accumulate machine-local permission
  entries and project paths, and Claude Code rewrites `settings.json` constantly.
  Auto-pushing that would republish local paths on every permission approval.
  `install.sh` injects the sync hook into the local file instead.
- **Credentials** — `~/.codex/auth.json` and anything like it. `.gitignore`
  blocks the obvious filenames as a backstop.
- **Work skills** — the ~25 skills in `~/repos/llm/skills` have their own remote
  and stay there. `install.sh` relinks them when that checkout is present and
  skips them silently when it isn't.
- **State** — sessions, transcripts, caches, logs, plugin caches. Plugins are
  declared in `settings.json` (`enabledPlugins`, `extraKnownMarketplaces`), so
  they reinstall themselves on a new machine.
