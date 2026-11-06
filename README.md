# skillz

Skills for Claude Code and Codex that work in any codebase: commit messages and MR descriptions, plan cleanup, issue investigation, unattended dev loops, branch syncing, test audits and a few more. They install as one plugin, `skillz`. A few more are my own, tied to my work or my machines; they stay out of the plugin and are listed in [personal/README.md](personal/README.md).

## Install

### The plugin

Claude Code:

```bash
claude plugin marketplace add ryanng-lgtm/skillz
claude plugin install skillz@skillz
```

Codex:

```bash
codex plugin marketplace add ryanng-lgtm/skillz
codex plugin add skillz@skillz
```

Claude Desktop and claude.ai: Customize > Plugins > Add > Add marketplace, with `https://github.com/ryanng-lgtm/skillz`.

Then add whichever [skill settings](#skill-settings) you need. The plugin doesn't pick up my changes by itself; [Updates](#updates) has how to get them. Or paste [the install prompt](#let-your-agent-install-it) into Claude Code or Codex and let it do all of this.

### The repo, on my machines

```bash
git clone git@github.com:ryanng-lgtm/skillz.git ~/Documents/github/skillz
cd ~/Documents/github/skillz
./install.sh
```

This links every skill, shared and personal, and my global instructions, and turns on the sync hooks. It's for my machines only: with the plugin you don't need it. [personal/README.md](personal/README.md) has what it sets up.

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

## More on installing

### Updates

Auto-update is off by default for a marketplace you add yourself. To turn it on in Claude Code, run `/plugin` in a session, open the Marketplaces tab, select skillz and select Enable auto-update. Claude Code then updates the plugin after each session starts, and the next session loads the new version. `claude plugin update skillz@skillz` updates it once, by hand.

Codex doesn't update plugins for you. Run `codex plugin marketplace upgrade skillz` and then the `codex plugin add` line again whenever you want the latest.

In Claude Desktop and claude.ai, select Check for updates on the marketplace, or turn on Sync automatically.

### Let your agent install it

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

### Upload a zip instead

On Team and Enterprise plans an Owner decides whether members can add their own marketplaces in Claude Desktop and claude.ai. If you can't, build the plugin as a zip and upload it at Customize > Plugins > Add > Upload plugin:

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

## Changing this repo

Read [`CLAUDE.md`](CLAUDE.md) first. It has the layout, how to add a skill, the checks to run and how sync works.
