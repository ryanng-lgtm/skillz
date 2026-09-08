# Personal instructions (Ryan)

Same rules as my Claude Code setup (`claude/CLAUDE.md` in the skillz repo), phrased for Codex. Keep the two in step when one changes.

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

## Subagent cap — all projects

When a task fans out to subagents or parallel agents: **5 agents maximum per task, STRICTLY.** Count every agent the plan can spawn (loops and per-item fan-outs included) and design under the cap — prefer fewer, broader agents (one critic with multiple lenses, not one per lens). If a task seems to need more than 5, shrink the design or ask me first. If subagents are not available in this session, run the roles sequentially in the main thread instead of skipping them.

## Graphify-first codebase search — all projects

Before reaching for `rg`/`find` (or explore-style subagents) to answer a question about a codebase, use graphify:

- If `graphify-out/graph.json` exists in the project root and is current, answer via `graphify query` instead of raw greps/globs.
- If the project has no graph, do not build one unprompted — ask me to provide the install.md, then proceed from that.
- If the graph exists but is out of date (source files changed since it was built), run `$graphify <path> --update` first, then query.

Raw `rg`/`find` is still fine for trivial single-file lookups where a graph query adds nothing.

## Plan files — dated dirs in the Obsidian vault

`~/.codex/plans` is symlinked to the Obsidian vault (`~/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/Claude Plans`, iCloud-synced) — the same folder `~/.claude/plans` points at, so Claude and Codex plans land side by side. There is also a nested `Obsidian/Obsidian/` vault registered in Obsidian's own config — it is NOT where plans go; trust the symlink, not `obsidian.json`. Placement rule:

- A plan file always goes under a subdirectory named for today's date, `YYYY-MM-DD` (e.g. `~/.codex/plans/2026-08-05/my-plan.md`). Create the dir if it doesn't exist; if it exists, just place the file in it. Never write plan files at the plans root.
- Any plan, spec, or design doc you author — including one drafted in Codex plan mode — is written to today's dated dir as a markdown file before execution starts, so it survives the session and shows up in the vault.
- **Never commit plan/spec documents.** Session-authored plans, specs, and design docs live in the plans vault only — never `git add` or commit them into a project repo, and exclude them from any staging sweep (`git add -A` included). If one is needed in a repo temporarily, it stays untracked.

## Commits — all projects

Every commit goes through the `$commit` skill (`~/.codex/skills/commit/SKILL.md`), main thread included: stage with `git add`, then run the skill to commit what's staged — no raw `git commit`. One summary line plus at most three bullets, no AI/co-authored-by watermark.

Whenever a subagent makes a git commit, it must ALWAYS do the same: first stage its changes (`git add`), then follow the `commit` skill. When dispatching any subagent that may commit, include this requirement explicitly in its prompt.

## Personal skills

Skills live in `~/.codex/skills/<name>/SKILL.md`. When I mention one as `$name`, or type its slash trigger (`/name`) out of Claude habit, read and follow that SKILL.md before doing anything else.

- **graphify** (`~/.codex/skills/graphify/SKILL.md`) — any input to knowledge graph. Trigger: `$graphify`
- **demuddy** (`~/.codex/skills/demuddy/SKILL.md`) — editorial pass turning a much-edited plan/spec into a handover-ready one (strip decision archaeology, dedupe rules, build order; keep every gotcha and cite). Trigger: `$demuddy [path]`
- **ivtg** (`~/.codex/skills/ivtg/SKILL.md`) — investigator: issues fed one at a time, each investigated across the named repos, reviewed by a second agent, written into one dated plan file. Never implements. Trigger: `$ivtg`
- **syncup** (`~/.codex/skills/syncup/SKILL.md`) — pick repos, refresh main from origin, rebase the working branch onto it, resolve conflicts, hand uncommitted work back intact. Never pushes. Trigger: `$syncup [repo ...]`
- **humanize** (`~/.codex/skills/humanize/SKILL.md`) — rewrite AI-authored text (doc, MR description, message draft) so it reads like Ryan wrote it: strip AI tells, match his voice per register. Trigger: `$humanize [light] [path]` (`light` = sentence-level only, keeps structure)
- **loop-me-in** (`~/.codex/skills/loop-me-in/SKILL.md`) — turn an approved plan into a brief a fresh session can execute unattended: resolved worktrees, traps, phases, gates, stop conditions. One worktree per repo and a chat completion post are defaults. Trigger: `$loop-me-in [path]`
- **om-build** (`~/.codex/skills/om-build/SKILL.md`) — build an OM Chat GUI from source and put it in front of Ryan: the daemon-embedded `/rooms` GUI, or the hosted `/chat/` cloud fork. Covers the swap onto the live install. Trigger: `$om-build [--hosted|--cloud] [--no-gui]`
- **testing-harness** (`~/.codex/skills/testing-harness/SKILL.md`) — prove a change in the real running app: drive the OM Chat GUI in a logged-in browser and diff cloud against the local daemon into a before/after report. Trigger: `$testing-harness`
- **bump-rc** (`~/.codex/skills/bump-rc/SKILL.md`) — release a new `@openmarket/rooms-client`: pick the bump from what actually changed, run the release script, update both GUI consumers' pins. Trigger: `$bump-rc [version]`
- **llm-council** (`~/.codex/skills/llm-council/SKILL.md`) — run a real decision through 5 advisors who analyse independently, peer-review anonymously, then synthesise a verdict. Trigger: "council this", "pressure-test this", `$llm-council`
- **prompt-ready** (`~/.codex/skills/prompt-ready/SKILL.md`) — persistent mode turning raw requests into clean, self-contained, copy-paste-ready prompts for another session. Trigger: `$prompt-ready`
- **war-diary** (`~/.codex/skills/war-diary/SKILL.md`) — turn a day's GitLab `.atom` export plus the day's sessions into Frontend War Diaries daily-log notes and Kanban cards. Trigger: `$war-diary`
- **mr-markdown** (`~/.codex/skills/mr-markdown/SKILL.md`) — condensed MR description for the current branch, in one copyable code block. Trigger: `$mr-markdown`
- **commit** (`~/.codex/skills/commit/SKILL.md`) — commit the currently staged changes only. Trigger: `$commit`

Skills written for Claude Code may name Claude tools (`AskUserQuestion`, `Agent`, `SendMessage`, `Skill`). Map them to the Codex equivalent — ask in chat, spawn a subagent or run the role inline, message the agent or re-spawn it, read the SKILL.md — and keep going; never stop because a tool name doesn't match.
