# skillz

Skills for Claude Code and Codex that work in any codebase: commit messages and MR descriptions, plan cleanup, issue investigation, unattended dev loops, branch syncing, test audits and a few more. They install as one plugin, `skillz`. It doesn't pick up my changes by itself: Claude Code gets them once you turn on auto-update for the marketplace, which is off by default, and Codex when you upgrade it by hand. [Install](#install) has the steps.

A few skills here are my own, tied to my work or my machines. They stay out of the plugin and are listed under [Ryan's machines](#ryans-machines).

## Install

Paste this into Claude Code or Codex and let it do the work:

```text
Install the skillz plugin from https://github.com/ryanng-lgtm/skillz for me.

1. Check which of these I have: Claude Code (`claude`) and Codex (`codex`).
   Do the steps below for each one I have.
2. Claude Code: run `claude plugin marketplace add ryanng-lgtm/skillz`, then
   `claude plugin install skillz@skillz`. There's no command that turns on
   updates, so tell me how: in a Claude Code session, run /plugin, open the
   Marketplaces tab, select skillz, then select "Enable auto-update".
3. Codex: run `codex plugin marketplace add ryanng-lgtm/skillz`, then
   `codex plugin add skillz@skillz`. Tell me Codex won't update it on its own:
   `codex plugin marketplace upgrade skillz`, then the add command again,
   gets the latest.
4. Read the "Skill settings" section of the repo's README. Ask me for each
   setting, one question at a time, and skip any I say I don't need. Write my
   answers as `- <Key>: <value>` lines under a "## Skill settings" heading in
   ~/.claude/CLAUDE.md (and in ~/.codex/AGENTS.md if I use Codex). Create the
   file or the section if it's missing, and change nothing else in them.
5. Don't run the repo's install.sh. It sets up the owner's machines, not mine.
6. When you're done, tell me to start a new session, then list the skills and
   how to run each one. In Claude Code, plugin skills run as /skillz:<name>.
```

Or by hand. Claude Code:

```bash
claude plugin marketplace add ryanng-lgtm/skillz
claude plugin install skillz@skillz
```

Auto-update is off by default for a marketplace you add yourself. To turn it on, run `/plugin` in a session, open the Marketplaces tab, select skillz and select Enable auto-update. Claude Code then updates the plugin after each session starts, and the next session loads the new version. `claude plugin update skillz@skillz` updates it once, by hand.

Codex:

```bash
codex plugin marketplace add ryanng-lgtm/skillz
codex plugin add skillz@skillz
```

Codex doesn't update plugins for you. Run `codex plugin marketplace upgrade skillz` and then the `codex plugin add` line again whenever you want the latest.

Then add whichever [skill settings](#skill-settings) you need.

### Claude Desktop and claude.ai

Add the repo as a marketplace at Customize > Plugins > Add > Add marketplace, with `https://github.com/ryanng-lgtm/skillz`. To get my changes, select Check for updates on it, or turn on Sync automatically. On Team and Enterprise plans an Owner decides whether members can add their own marketplaces. If you can't, build the plugin as a zip and upload it at Customize > Plugins > Add > Upload plugin:

```bash
git clone https://github.com/ryanng-lgtm/skillz.git
cd skillz
python3 -I export.py   # writes ~/Downloads/skillz.zip; --out picks another path
```

An uploaded zip never updates. Pull, export and upload again to get newer skills. The folders under `skillz/skills/` in the zip also work as plain skills in any tool that reads a skills directory.

## Shared skills

Everything the plugin installs. Claude Code shows them as `/skillz:<name>`. Codex lists them with the same `skillz:` prefix; type `$` to pick one. Or describe the task, and the agent picks the skill from its description.

| Skill | Agents | What it does |
| --- | --- | --- |
| [`commit`](shared/skills/commit/SKILL.md) | Claude, Codex | Commits only what is already staged, with a short message in the repo's style. |
| [`demuddy`](shared/skills/demuddy/SKILL.md) | Claude, Codex | Makes a much-edited plan handover-ready, or cleans up the comments a code change left behind, keeping every gotcha and cite. |
| [`dev-loop`](shared/skills/dev-loop/SKILL.md) | Claude, Codex | Turns an approved plan into a brief a fresh session can run unattended and prove its own changes landed. |
| [`docs-knowledge-base`](shared/skills/docs-knowledge-base/SKILL.md) | Claude, Codex | Looks up and records durable facts in a nested markdown docs dir, with `INDEX.md` tables generated and checked by `build-index.py`. |
| [`graphify-setup`](shared/skills/graphify-setup/SKILL.md) | Claude, Codex | One-time setup. Installs graphify and graphify's own skill for each agent you use, then builds a never-committed graph for one repo or several merged ones, with git hooks that keep it current. |
| [`humanize`](shared/skills/humanize/SKILL.md) | Claude, Codex | Rewrites AI-written text so it reads like a person wrote it: in your voice when you give it a voice file, plain when you don't. |
| [`ivtg`](shared/skills/ivtg/SKILL.md) | Claude, Codex | Investigates issues one at a time across the named repos and writes each up as a fix plan. Never implements. |
| [`llm-council`](shared/skills/llm-council/SKILL.md) | Claude, Codex | Runs a decision past five advisors who analyse it independently, review each other anonymously, and synthesise a verdict. |
| [`mr-markdown`](shared/skills/mr-markdown/SKILL.md) | Claude, Codex | Writes the MR description for the current branch: a full draft, cut to 200 words, then stripped of jargon. |
| [`prompt-ready`](shared/skills/prompt-ready/SKILL.md) | Claude, Codex | Turns raw requests into self-contained, copy-paste-ready prompts for another session. |
| [`regroup`](shared/skills/regroup/SKILL.md) | Claude | Trims a branch's tests to the necessary ones and rewrites its commits into three for review (refactor, change, tests and docs), leaving the code byte-identical. |
| [`repo-sync`](shared/skills/repo-sync/SKILL.md) | Claude, Codex | Rebases the working branch and every behind MR or PR onto its target, resolving conflicts and handing uncommitted work back exactly as it was staged. |
| [`setup-statusline`](shared/skills/setup-statusline/SKILL.md) | Claude | One-time setup. Gives Claude Code a status line with the parts you pick (model, folder, branch, context, usage limits, effort), changing only `statusLine` in `settings.json`. |
| [`socratic-teacher`](shared/skills/socratic-teacher/SKILL.md) | Claude, Codex | Teaching mode: one guiding question per turn, never the full solution. |
| [`summary`](shared/skills/summary/SKILL.md) | Claude, Codex | Ends a run or long session with the issues it worked and what became of each, the repos touched, their merge order and what is left for the user, every state read live. |
| [`test-audit`](shared/skills/test-audit/SKILL.md) | Claude | Gates new or changed tests on the behaviour they protect, and sweeps out low-value ones; `enforce` deletes every test that can't name the bug only it catches. |
| [`update-knowledge-base`](shared/skills/update-knowledge-base/SKILL.md) | Claude, Codex | Folds a conversation's durable findings into the docs dir or vault the user names, each fact in the doc that owns it, and discards the session residue. |

Codex gets all of them, but the ones marked Claude are written for Claude Code.

`socratic-teacher`, `docs-knowledge-base` and the skill template are adapted from [wooneusean/skills](https://github.com/wooneusean/skills).

The shared plugin is MIT-licensed ([`shared/LICENSE`](shared/LICENSE)). The personal and vendored skills are not licensed for reuse.

## Skill settings

Some skills need something only you know, like where your plans go. They read it from a `## Skill settings` section in your global instructions: `~/.claude/CLAUDE.md` for Claude Code, `~/.codex/AGENTS.md` for Codex. Each setting is one `- <Key>: <value>` line, and values can have spaces. When a skill needs a setting you haven't added, it asks once and offers to add the line. It never falls back to a default of mine.

| Setting | What it is | Used by | Without it |
| --- | --- | --- | --- |
| `Voice file` | A markdown profile of how you write. humanize's [voice template](shared/skills/humanize/references/voice-template.md) builds one from your own writing | humanize, mr-markdown | humanize asks for one when you run it yourself; otherwise it strips the AI tells and writes plainly |
| `Plans folder` | Where plans, briefs and their evidence go, in a dated subfolder per day | ivtg, dev-loop | asks where |
| `Prompts folder` | Where each finished prompt is saved, in a dated subfolder per day | prompt-ready | prints the prompt and saves nothing |
| `Repo folders` | Comma-separated folders whose direct children are your clones | repo-sync | works on the current repo and the ones this session touched, and asks before scanning wider |
| `Repo stacks` | Named groups of repos that ship together: `<stack>: <repo>, <repo>; <stack>: …` | repo-sync | no stacks |
| `Dev-loop reports` | Where an unattended run posts its final report: a chat channel the session can post to, an issue or MR thread, or a file | dev-loop | asks; with no answer, the findings log beside the brief is the report |

For example:

```markdown
## Skill settings

- Voice file: ~/notes/voice.md
- Plans folder: ~/notes/plans
- Prompts folder: ~/notes/prompts
- Repo folders: ~/code, ~/work repos
- Repo stacks: web: frontend, api, shared-ui; data: ingest, warehouse
- Dev-loop reports: the #dev-runs Slack channel
```

## Ryan's machines

The rest is my own setup. On a new machine:

```bash
git clone git@github.com:ryanng-lgtm/skillz.git ~/Documents/github/skillz
cd ~/Documents/github/skillz
./install.sh
```

`install.sh` links:

- every skill in `shared/skills/` and `personal/` into `~/.claude/skills/`, and the ones in `codex/skills/` into `~/.codex/skills/`
- `claude/CLAUDE.md` and `codex/AGENTS.md` to `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
- `~/.claude/plans` and `~/.codex/plans` to the iCloud Obsidian folder `Claude Plans` (`PLANS_VAULT_DIR` overrides it)
- `om-hosted` and `om-glab` into `~/.local/bin`
- the work skills in `~/repos/llm/skills`, when that checkout is there

It also registers the sync hooks and installs the caveman plugin for Codex ([yibie/caveman-codex](https://github.com/yibie/caveman-codex); only `$caveman` works from it). It doesn't install the skillz plugin, since the links already cover every skill. Re-running it is safe; `./install.sh --help` lists the flags.

Two Claude Code hooks keep the machines in step. At the end of every turn `sync.sh` commits whatever is in the repo, rebases and pushes; at session start it pulls and relinks. So anything left in the working tree when a turn ends goes out. [`CLAUDE.md`](CLAUDE.md#sync) covers pausing it, failed checks and conflicts.

Not in the repo: `settings.json`, `config.toml` and credentials, the work skills (they have their own remote), and sessions, logs and caches.

## Personal skills

My own skills: tied to my work, services or machines, or vendored from another tool. They live in `personal/` and aren't in the plugin.

| Skill | Agents | What it does |
| --- | --- | --- |
| [`bump-rc`](personal/bump-rc/SKILL.md) | Claude, Codex | Releases `@openmarket/rooms-client`, choosing the version bump from what changed, and repins both GUI consumers. |
| [`claude-statusline`](personal/claude-statusline/SKILL.md) | Claude | Sets the Claude Code status line (model, folder, branch, context, usage limits, effort), changing only `statusLine` in `settings.json`. |
| [`desloppify`](personal/desloppify/SKILL.md) | Claude, Codex (own copy) | Scores a codebase's health with the `desloppify` CLI and works through the cleanup plan it builds: scan, plan, fix, rescan. Vendored from [desloppify](https://github.com/peteromallet/desloppify). |
| [`graphify`](personal/graphify/SKILL.md) | Claude, Codex (own copy) | Turns code, docs, papers, images or video into a knowledge graph to query instead of grepping. |
| [`loop-me-in`](personal/loop-me-in/SKILL.md) | Claude, Codex (own copy) | Turns an approved plan into a brief a fresh session can run unattended and prove its own changes landed. |
| [`mr-ready`](personal/mr-ready/SKILL.md) | Claude, Codex | Posts a piece of work's MRs to OM Chat in one fixed format, as a draft in `#draft-replies` or in the work's topic: a short TLDR of the problem, the fix and how it was verified, then the MR links and merge order. |
| [`om-build`](personal/om-build/SKILL.md) | Claude, Codex | Builds an OM Chat GUI from source (the daemon's `/rooms` GUI, the hosted `/chat/` fork, or the OpenFloor iOS app) and swaps it onto the live install or the simulator. |
| [`om-glab`](personal/om-glab/SKILL.md) | Claude, Codex | Builds and installs the local daemon with the GitLab chat GUI instead of `om-build`'s GitHub default. |
| [`panos`](personal/panos/SKILL.md) | Claude | Reviews landed MRs the way Panos would, verifies every finding, and fixes and pushes the real ones. |
| [`shared-dev`](personal/shared-dev/SKILL.md) | Claude | Brings up the backend services a change needs in shared-dev, probes main against the branch with real data, and tears down. |
| [`syncup`](personal/syncup/SKILL.md) | Claude, Codex | Rebases the working branch and every behind MR or PR onto its target, resolving conflicts and keeping uncommitted work. |
| [`testing-harness`](personal/testing-harness/SKILL.md) | Claude, Codex | Proves a change in the running OM Chat GUI with cloud-versus-local visual diffs and browser probes. |
| [`war-diary`](personal/war-diary/SKILL.md) | Claude, Codex | Turns a day's GitLab activity and Claude Code sessions into War Diaries notes and Kanban cards. |
| [`world-todo`](personal/world-todo/SKILL.md) | Claude, Codex | Plans every OM World service change before implementation, however small. |

`openmarket` and `om-chat` ship with the `om` CLI and are vendored here so both agents get the same copy; they are not listed.

## Changing this repo

Read [`CLAUDE.md`](CLAUDE.md) first. It has the layout, how to add a skill, the checks to run and how sync works.
