# skillz

Ryan's agent skills and global instructions, shared across machines. One source of truth for Claude Code (`~/.claude`) and Codex (`~/.codex`): each machine symlinks into this repo instead of keeping its own copy.

## Skill index

Agnostic is `yes` when a skill's job works in any codebase, so it can be [exported](#export) to Claude Desktop or anywhere else. Personal defaults such as a vault path don't count against it; a skill about one product, service or person is `no`.

| Skill | Agents | Agnostic | What it does |
| --- | --- | --- | --- |
| [`bump-rc`](claude/skills/bump-rc/SKILL.md) | Claude, Codex | no | Releases `@openmarket/rooms-client`, choosing the version bump from what changed, and repins both GUI consumers. |
| [`commit`](claude/skills/commit/SKILL.md) | Claude, Codex | yes | Commits only what is already staged, with a short message in the repo's style. |
| [`demuddy`](claude/skills/demuddy/SKILL.md) | Claude, Codex | yes | Makes a much-edited plan handover-ready, or cleans up the comments a code change left behind, keeping every gotcha and cite. |
| [`docs-knowledge-base`](claude/skills/docs-knowledge-base/SKILL.md) | Claude, Codex | yes | Looks up and records durable facts in a nested markdown docs dir, with `INDEX.md` tables generated and checked by `build-index.py`. |
| [`graphify`](claude/skills/graphify/SKILL.md) | Claude, Codex (own copy) | yes | Turns code, docs, papers, images or video into a knowledge graph to query instead of grepping. |
| [`humanize`](claude/skills/humanize/SKILL.md) | Claude, Codex | yes | Rewrites Claude-authored text so it reads like Ryan wrote it. |
| [`ivtg`](claude/skills/ivtg/SKILL.md) | Claude, Codex | yes | Investigates issues one at a time across the named repos and writes each up as a fix plan. Never implements. |
| [`llm-council`](claude/skills/llm-council/SKILL.md) | Claude, Codex | yes | Runs a decision past five advisors who analyse it independently, review each other anonymously, and synthesise a verdict. |
| [`loop-me-in`](claude/skills/loop-me-in/SKILL.md) | Claude, Codex (own copy) | yes | Turns an approved plan into a brief a fresh session can run unattended and prove its own changes landed. |
| [`mr-markdown`](claude/skills/mr-markdown/SKILL.md) | Claude, Codex | yes | Writes the MR description for the current branch: a full draft, cut to 200 words, then stripped of jargon. |
| [`om-build`](claude/skills/om-build/SKILL.md) | Claude, Codex | no | Builds an OM Chat GUI from source (the daemon's `/rooms` GUI, the hosted `/chat/` fork, or the OpenFloor iOS app) and swaps it onto the live install or the simulator. |
| [`om-glab`](claude/skills/om-glab/SKILL.md) | Claude, Codex | no | Builds and installs the local daemon with the GitLab chat GUI instead of `om-build`'s GitHub default. |
| [`panos`](claude/skills/panos/SKILL.md) | Claude | no | Reviews landed MRs the way Panos would, verifies every finding, and fixes and pushes the real ones. |
| [`prompt-ready`](claude/skills/prompt-ready/SKILL.md) | Claude, Codex | yes | Turns raw requests into self-contained, copy-paste-ready prompts for another session. |
| [`regroup`](claude/skills/regroup/SKILL.md) | Claude | yes | Trims a branch's tests to the necessary ones and rewrites its commits for review, leaving the code byte-identical. |
| [`shared-dev`](claude/skills/shared-dev/SKILL.md) | Claude | no | Brings up the backend services a change needs in shared-dev, probes main against the branch with real data, and tears down. |
| [`socratic-teacher`](claude/skills/socratic-teacher/SKILL.md) | Claude, Codex | yes | Teaching mode: one guiding question per turn, never the full solution. |
| [`syncup`](claude/skills/syncup/SKILL.md) | Claude, Codex | yes | Rebases the working branch and every behind MR or PR onto its target, resolving conflicts and keeping uncommitted work. |
| [`test-audit`](claude/skills/test-audit/SKILL.md) | Claude | yes | Gates new or changed tests on the behaviour they protect, and sweeps out low-value ones. |
| [`testing-harness`](claude/skills/testing-harness/SKILL.md) | Claude, Codex | no | Proves a change in the running OM Chat GUI with cloud-versus-local visual diffs and browser probes. |
| [`war-diary`](claude/skills/war-diary/SKILL.md) | Claude, Codex | no | Turns a day's GitLab activity and Claude Code sessions into War Diaries notes and Kanban cards. |
| [`world-todo`](claude/skills/world-todo/SKILL.md) | Claude, Codex | no | Plans every OM World service change before implementation, however small. |

`openmarket` and `om-chat` ship with the `om` CLI and are vendored here so both agents get the same copy; they are not listed. `socratic-teacher`, `docs-knowledge-base` and the skill template are adapted from [wooneusean/skills](https://github.com/wooneusean/skills).

## One-time setup

Skills that set something up once per machine or repo. They live in `setup/` and install like any other skill, but only run when you invoke them.

| Skill | Agents | Agnostic | What it does |
| --- | --- | --- | --- |
| [`graphify-setup`](setup/graphify-setup/SKILL.md) | Claude, Codex | yes | Installs graphify and builds a never-committed graph for one repo or several merged ones, with git hooks that keep it current. |
| [`status-line`](setup/status-line/SKILL.md) | Claude | yes | Sets the Claude Code status line (model, folder, branch, context, usage limits, effort), changing only `statusLine` in `settings.json`. |

## Structure

```
skillz/
├── claude/
│   ├── CLAUDE.md      # global instructions → ~/.claude/CLAUDE.md
│   └── skills/        # every skill → ~/.claude/skills/<name>
├── codex/
│   ├── AGENTS.md      # the same instructions for Codex → ~/.codex/AGENTS.md
│   └── skills/        # links into claude/skills and setup, plus Codex-only copies → ~/.codex/skills/<name>
├── setup/             # one-time setup skills → ~/.claude/skills/<name>
├── templates/         # skill-template.md, the layout every skill follows
├── CLAUDE.md          # how agents work in this repo
├── install.sh         # links everything into place
├── hook-install.sh    # registers the sync hooks; install.sh runs it
├── hook.sh            # runs sync.sh for an edit inside the repo, for a tool hook
├── sync.sh            # commits and pushes each turn, pulls at session start
├── check.py           # checks skills, Codex links, the index and skill paths agree
└── export.py          # packs the agnostic skills into one plugin zip
```

## Installation

```bash
git clone git@github.com:ryanng-lgtm/skillz.git ~/Documents/github/skillz
cd ~/Documents/github/skillz
./install.sh
```

`install.sh` links every skill and both instruction files into `~/.claude` and `~/.codex`, registers the sync hooks, and installs the Codex plugins below. It also:

- points `~/.claude/plans` and `~/.codex/plans` at the iCloud Obsidian folder `Obsidian/Claude Plans` (override with `PLANS_VAULT_DIR`);
- links the daemon build commands `om-hosted` (GitHub chat GUI) and `om-glab` (GitLab chat GUI) into `~/.local/bin`;
- links the work skills in `~/repos/llm/skills` when that checkout is present.

Re-running is safe. It refreshes links, removes links to skills the repo dropped, and never touches skills it doesn't own. A real directory where a link should go is adopted when its contents match and reported otherwise; `--force` replaces it and keeps a `.local-<timestamp>` backup.

### Codex plugins

`install.sh` registers each plugin's marketplace and installs the plugin; Codex records both in its per-machine `config.toml`.

| Plugin | Source | What it does |
| --- | --- | --- |
| `caveman@caveman-repo` | [yibie/caveman-codex](https://github.com/yibie/caveman-codex) | Terse internal reasoning, `$caveman [lite\|full\|ultra]`. Only `$caveman` works: the plugin copy drops the symlinks its `compress` skill needs. Upgrade with `codex plugin marketplace upgrade`. |

## Using skills

Invoke a skill as `/name` in Claude Code or `$name` in Codex, or describe the task. Each skill's `description` says when it applies and lists its arguments and trigger phrases.

## Export

```bash
python3 -I export.py                             # writes ~/Downloads/skillz.zip
python3 -I export.py --out ~/Desktop/skillz.zip  # any path outside this repo
```

`export.py` packs every skill marked Agnostic `yes` in the tables above into one plugin zip: `skillz/.claude-plugin/plugin.json` plus `skillz/skills/<name>/` for each skill. It runs `check.py` first and stops if the repo is out of step, and refuses a path inside the repo, since sync would publish the zip.

- In Claude Desktop or claude.ai, upload it at Customize > Plugins > Add > Upload plugin. Every skill comes in at once.
- Anywhere else, unzip it and copy the folders under `skillz/skills/` into that tool's skills directory.

## Adding a skill

1. Write `claude/skills/<name>/SKILL.md` from [`templates/skill-template.md`](templates/skill-template.md), or `setup/<name>/SKILL.md` for a one-time setup.
2. If it works the same under Codex, link it: `ln -s ../../claude/skills/<name> codex/skills/<name>` (or `../../setup/<name>`).
3. Add its row to the [skill index](#skill-index) or the [one-time setup](#one-time-setup) table, with Agnostic set to `yes` or `no`.
4. Run `python3 -I check.py` and `./install.sh --links-only`.

[`CLAUDE.md`](CLAUDE.md) has the full rules agents follow here.

## Sync

Two Claude Code hooks keep every machine on the same version:

- **Stop** runs `sync.sh` when a turn ends. It commits everything in the repo, rebases onto `origin/main`, and pushes.
- **SessionStart** runs `sync.sh --pull`, then links any skill the pull added and drops links to any it removed.

`sync.sh` never force-pushes. It pushes nothing and leaves a note when:

| Note | Cause |
| --- | --- |
| `.sync-conflict` | The rebase conflicted. The commit stays local; the note says how to resolve it. |
| `.sync-check` | `check.py` failed. Nothing is committed until its report is fixed. |

A pull or push that can't reach the remote is logged in `.sync.log` and retried on the next sync. `touch .sync-hold` pauses syncing on a machine and `rm .sync-hold` resumes it. Edits made outside Claude Code go out with the next session's first sync, or run `./sync.sh` by hand.

## Not in this repo

- `settings.json` and `config.toml`. They fill up with machine-local permissions and paths, so `install.sh` adds the sync hooks to the local `settings.json` instead.
- Credentials such as `~/.codex/auth.json`. `.gitignore` blocks the usual filenames as a backstop.
- Work skills in `~/repos/llm/skills`, which have their own remote.
- Sessions, transcripts, caches, logs and plugin caches.
