# My machines and personal skills

How my own machines are set up, and the skills that are mine alone. Neither is part of the skillz plugin; the [main README](../README.md) covers that.

## My machines

On a new machine, clone the repo and run `./install.sh`, as the [main README](../README.md#the-repo-on-my-machines) shows. It links:

- every skill in `shared/skills/` and `personal/` into `~/.claude/skills/`, and the ones in `codex/skills/` into `~/.codex/skills/`
- `claude/CLAUDE.md` and `codex/AGENTS.md` to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
- `~/.claude/plans` and `~/.codex/plans` to the iCloud Obsidian folder `Claude Plans` (`PLANS_VAULT_DIR` overrides it)
- `om-hosted` and `om-glab` into `~/.local/bin`
- the work skills in `~/repos/llm/skills`, when that checkout is there

It also registers the sync hooks and installs the caveman plugin for Codex ([yibie/caveman-codex](https://github.com/yibie/caveman-codex); only `$caveman` works from it). It doesn't install the skillz plugin, since the links already cover every skill. Re-running it is safe; `./install.sh --help` lists the flags.

Two Claude Code hooks keep the machines in step. At the end of every turn `sync.sh` commits whatever is in the repo, rebases and pushes; at session start it pulls and relinks. So anything left in the working tree when a turn ends goes out. [`CLAUDE.md`](../CLAUDE.md#sync) covers pausing it, failed checks and conflicts.

Not in the repo: `settings.json`, `config.toml` and credentials, the work skills (they have their own remote), and sessions, logs and caches.

## Personal skills

My own skills: tied to my work, services or machines, or vendored from another tool. They live in this folder and aren't in the plugin.

| Skill | Agents | What it does |
| --- | --- | --- |
| [`bump-rc`](bump-rc/SKILL.md) | Claude, Codex | Releases `@openmarket/rooms-client`, choosing the version bump from what changed, and repins both GUI consumers. |
| [`claude-statusline`](claude-statusline/SKILL.md) | Claude | Sets the Claude Code status line (model, folder, branch, context, usage limits, effort), changing only `statusLine` in `settings.json`. |
| [`desloppify`](desloppify/SKILL.md) | Claude, Codex (own copy) | Scores a codebase's health with the `desloppify` CLI and works through the cleanup plan it builds: scan, plan, fix, rescan. Vendored from [desloppify](https://github.com/peteromallet/desloppify). |
| [`graphify`](graphify/SKILL.md) | Claude, Codex (own copy) | Turns code, docs, papers, images or video into a knowledge graph to query instead of grepping. |
| [`loop-me-in`](loop-me-in/SKILL.md) | Claude, Codex (own copy) | Turns an approved plan into a brief a fresh session can run unattended and prove its own changes landed. |
| [`mr-ready`](mr-ready/SKILL.md) | Claude, Codex | Posts a piece of work's MRs to OM Chat in one fixed format, as a draft in `#draft-replies` or in the work's topic: a short TLDR of the problem, the fix and how it was verified, then the MR links and merge order. |
| [`om-build`](om-build/SKILL.md) | Claude, Codex | Builds an OM Chat GUI from source (the daemon's `/rooms` GUI, the hosted `/chat/` fork, or the OpenFloor iOS app) and swaps it onto the live install or the simulator. |
| [`om-glab`](om-glab/SKILL.md) | Claude, Codex | Builds and installs the local daemon with the GitLab chat GUI instead of `om-build`'s GitHub default. |
| [`panos`](panos/SKILL.md) | Claude | Reviews landed MRs the way Panos would, verifies every finding, and fixes and pushes the real ones. |
| [`shared-dev`](shared-dev/SKILL.md) | Claude | Brings up the backend services a change needs in shared-dev, probes main against the branch with real data, and tears down. |
| [`syncup`](syncup/SKILL.md) | Claude, Codex | Rebases the working branch and every behind MR or PR onto its target, resolving conflicts and keeping uncommitted work. |
| [`testing-harness`](testing-harness/SKILL.md) | Claude, Codex | Proves a change in the running OM Chat GUI with cloud-versus-local visual diffs and browser probes. |
| [`war-diary`](war-diary/SKILL.md) | Claude, Codex | Turns a day's GitLab activity and Claude Code sessions into War Diaries notes and Kanban cards. |
| [`world-todo`](world-todo/SKILL.md) | Claude, Codex | Plans every OM World service change before implementation, however small. |

`openmarket` and `om-chat` ship with the `om` CLI and are vendored here so both agents get the same copy; they are not listed.
