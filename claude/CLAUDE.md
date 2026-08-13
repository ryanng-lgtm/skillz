# Personal instructions (Ryan)

## Caveman mode — internal only

The `caveman` plugin is enabled. Apply caveman compression to **internal work only** to save tokens:

- Thinking / reasoning
- Skill execution (audits, plans, debugging steps, checklists)
- Subagent prompts and inter-agent messages
- TodoWrite items, scratch notes, tool-call descriptions

Use **normal, full English** for anything **surfaced to me, the user**:

- Final answers and explanations
- Summaries of findings, recommendations, conclusions
- Anything I read to make a decision

Always normal (never caveman), per the plugin's own rules: code, commit messages, PR/MR descriptions, and security warnings.

Rule of thumb: compress the scaffolding, not the delivery.

## The 2-bug rule — all projects

If you (or a subagent) produce **2 bugs of the same class** or take **more than 3 iterations** on one problem, **STOP. Do not apply a 4th patch.** The mental model or architecture is wrong — step back, re-derive the model from the actual code/behavior, and say so, instead of patching again.

## Workflow agent cap — all projects

If the Workflow tool is used (including under ultracode): **5 agents maximum per workflow run, STRICTLY.** Count every `agent()` call the script can make (loops and per-item pipelines included) and design under the cap — prefer fewer, broader agents (one critic with multiple lenses, not one per lens). If a task seems to need more than 5, shrink the design or ask me first.

## Graphify-first codebase search — all projects

Before reaching for Grep/Glob (or Explore-style subagents) to answer a question about a codebase, use graphify:

- If `graphify-out/graph.json` exists in the project root and is current, answer via `graphify query` instead of raw greps/globs.
- If the project has no graph, do not build one unprompted — ask me to provide the install.md, then proceed from that.
- If the graph exists but is out of date (source files changed since it was built), run `/graphify <path> --update` first, then query.

Raw Grep/Glob is still fine for trivial single-file lookups where a graph query adds nothing.

## Plan files — dated dirs in the Obsidian vault

`~/.claude/plans` is symlinked to the Obsidian vault (`~/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/Claude Plans`, iCloud-synced), so every plan file lands in the vault. There is also a nested `Obsidian/Obsidian/` vault registered in Obsidian's own config — it is NOT where plans go; trust the symlink, not `obsidian.json`. Placement rule:

- A plan file always goes under a subdirectory named for today's date, `YYYY-MM-DD` (e.g. `~/.claude/plans/2026-08-05/my-plan.md`). Create the dir if it doesn't exist; if it exists, just place the file in it. Never write plan files at the plans root.
- Plan mode pins its plan file at the plans root (harness-assigned path, not editable during planning): keep working with the pinned path while plan mode is active, then move the file into today's dated dir as the first action after plan mode ends.
- **Never commit plan/spec documents.** Session-authored plans, specs, and design docs live in the plans vault only — never `git add` or commit them into a project repo, and exclude them from any staging sweep (`git add -A` included). If one is needed in a repo temporarily, it stays untracked.

## Subagent commits — all projects

Whenever a subagent makes a git commit, it must ALWAYS: first stage its changes (`git add`), then invoke the `/commit` skill to commit what's staged — no raw `git commit` from subagents. When dispatching any subagent that may commit, include this requirement explicitly in its prompt.

## Personal skills

When I type one of these slash triggers, invoke the Skill tool with that skill before doing anything else.

- **graphify** (`~/.claude/skills/graphify/SKILL.md`) — any input to knowledge graph. Trigger: `/graphify`
- **demuddy** (`~/.claude/skills/demuddy/SKILL.md`) — editorial pass turning a much-edited plan/spec into a handover-ready one (strip decision archaeology, dedupe rules, build order; keep every gotcha and cite). Trigger: `/demuddy [path]`
- **ivtg** (`~/.claude/skills/ivtg/SKILL.md`) — investigator: issues fed one at a time, each investigated across the named repos by an Opus agent, reviewed by codex, written into one dated plan file. Never implements. Trigger: `/ivtg`
- **syncup** (`~/.claude/skills/syncup/SKILL.md`) — pick repos, refresh main from origin, rebase the working branch onto it, resolve conflicts, hand uncommitted work back intact. Never pushes. Trigger: `/syncup [repo ...]`
- **humanize** (`~/.claude/skills/humanize/SKILL.md`) — rewrite Claude-authored text (doc, MR description, message draft) so it reads like Ryan wrote it: strip AI tells, match his voice per register. Trigger: `/humanize [light] [path]` (`light` = sentence-level only, keeps structure)
- **loop-me-in** (`~/.claude/skills/loop-me-in/SKILL.md`) — turn an approved plan into a brief a fresh session can execute unattended: resolved worktrees, traps, phases, gates, stop conditions. One worktree per repo and a chat completion post are defaults. Trigger: `/loop-me-in [path]`
- **om-build** (`~/.claude/skills/om-build/SKILL.md`) — build an OM Chat GUI from source and put it in front of Ryan: the daemon-embedded `/rooms` GUI, or the hosted `/chat/` cloud fork. Covers the swap onto the live install. Trigger: `/om-build [--hosted|--cloud] [--no-gui]`
- **om-chat-web** (`~/.claude/skills/om-chat-web/SKILL.md`) — drive the OM Chat GUI in a real browser with a logged-in session, and prove a UI change landed by diffing cloud against the local daemon into a before/after report. Trigger: `/om-chat-web`
- **bump-rc** (`~/.claude/skills/bump-rc/SKILL.md`) — release a new `@openmarket/rooms-client`: pick the bump from what actually changed, run the release script, update both GUI consumers' pins. Trigger: `/bump-rc [version]`
