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

## Skills

Everything below is authored here. The `openmarket` and `om-chat` skills ship
with the `om` CLI and are only vendored into this repo so both agents get the
same copy — they're synced by `skills: sync om-bundled docs from om <version>`
commits, not edited by hand, and aren't listed.

### Claude (`claude/skills/` → `~/.claude/skills/`)

| Skill | Trigger | What it does |
| --- | --- | --- |
| `bump-rc` | `/bump-rc [version]` | Releases `@openmarket/rooms-client`: picks the bump from what actually changed, runs the release script, repins both GUI consumers. |
| `demuddy` | `/demuddy [path]` | Editorial pass that turns a much-edited plan into a handover-ready one — strips decision archaeology, dedupes rules, reorders into build order, keeps every gotcha and cite. |
| `graphify` | `/graphify` | Turns any input (code, docs, papers, images, video) into a persistent knowledge graph with god nodes and community detection; query/path/explain instead of grepping. |
| `humanize` | `/humanize [light] [path]` | Rewrites Claude-authored text so it reads like Ryan wrote it — strips AI tells, matches voice per register. `light` keeps the structure and edits sentences only. |
| `ivtg` | `/ivtg` | Investigator mode: issues fed one at a time, each investigated across the named repos and written into one dated plan file. Never implements. |
| `llm-council` | "council this", "pressure-test this" | Runs a question through 5 AI advisors who analyse it independently, peer-review each other anonymously, then synthesise a verdict. |
| `loop-me-in` | `/loop-me-in [path]` | Turns an approved plan into a brief a fresh session can execute unattended — elicits the expected result of every change first, writes it as a spec before the code, and gates the run on those specs. |
| `om-build` | `/om-build [--hosted\|--cloud]` | Builds an OM Chat GUI from source — the daemon-embedded `/rooms` GUI or the hosted `/chat/` cloud fork — including the swap onto the live install. |
| `prompt-ready` | `/prompt-ready` | Persistent mode that turns raw, natural-language requests into clean, self-contained, copy-paste-ready prompts for a different session. |
| `syncup` | `/syncup [repo ...]` | Refreshes main from origin, rebases the working branch onto it, resolves every conflict, and hands uncommitted work back intact. Never pushes. |
| `testing-harness` | `/testing-harness` | Proves a change in the real running app rather than in tests. `--parity-check` diffs the cloud deployment against the local daemon visually; `--regression` (designed, not yet built) checks the running app against invariants and a baseline. |
| `war-diary` | — | Turns a day of GitLab `.atom` activity plus the day's Claude Code sessions into Frontend War Diaries daily-log notes and matching Kanban cards. |

### Codex (`codex/skills/` → `~/.codex/skills/`)

| Skill | Trigger | What it does |
| --- | --- | --- |
| `commit` | `/commit` | Commits the currently staged changes only — concise message from the existing index, never stages anything extra. |
| `graphify` | `/graphify` | The Codex build of graphify. Genuinely differs from the Claude one, so it's stored separately rather than symlinked. |

### Commands (`claude/commands/` → `~/.claude/commands/`)

| Command | What it does |
| --- | --- |
| `/commit` | Commits the currently staged changes. |
| `/mr-markdown` | Generates a condensed MR markdown for the changes on the current branch. |

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
