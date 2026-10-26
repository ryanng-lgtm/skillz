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

## Model, effort, and sessions — all projects

- Use medium effort for well-scoped daily work.
- Give the model a way to check its work, and start changes that span files in plan mode.
- When medium stalls, raise effort to high. With an API key or a subscription the change keeps the cache. On a cloud provider or gateway, change it at a break.
- If xhigh hits the same problem twice, switch to Fable 5.1. Switch back to Opus 5.5 once it's solved.
- Put search and log-reading subagents on Sonnet or Haiku. Keep code edits on Opus 5.5.
- Keep a long session moving so its cache stays warm.
- Use `/clear` between unrelated tasks, and `/compact` at a break with a note on what to keep.
- The one that matters most: run one real task on each model and compare what `/usage` reports. My own numbers are the ones to trust.

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

- Create a plan file only when the work needs a durable implementation plan,
  spec, design, or execution handoff, or when Ryan explicitly asks for one.
  Routine fixes, installs, publishes, and short task checklists do not need a
  plan file just because execution has steps. Keep those steps in the session.
- Reuse the existing plan for an ongoing task, including across sessions and
  dates. Update it in place rather than creating a new plan for every follow-up
  or phase. Create a separate document only for a distinct scope or deliverable.
- Keep dated directories focused on plans and artifact directories. Save
  non-JSON supporting material (validation reports, review findings, receipts,
  logs, scripts, and bundles) under a task's `<task>-evidence/` directory, and
  link it from the plan when one exists. Reuse existing evidence directories;
  evidence does not require creating a plan. Keep disposable scratch work in a
  temporary directory outside the vault.
- A plan with retained JSON gets its own directory: the plan lives at
  `<date>/<plan>/<plan>.md` and its JSON at `<date>/<plan>/JSON/`. Use the plan's
  filename stem as the directory name and capitalized `JSON/`. When adding
  JSON to a previously standalone plan, move the plan into that directory and
  update affected links. JSON unrelated to a plan goes under `<date>/JSON/`.
  Reuse the plan's original date and directory across sessions, and link JSON
  artifacts from the plan when relevant. This JSON-specific rule takes
  precedence over the general evidence location; preserve existing evidence
  directories and their contents.
- A new plan file always goes under a subdirectory named for today's date, `YYYY-MM-DD` (e.g. `~/.claude/plans/2026-08-05/my-plan.md`). Create the dir if it doesn't exist; if it exists, just place the file in it. Never write plan files at the plans root.
- Plan mode pins its plan file at the plans root (harness-assigned path, not editable during planning): keep working with the pinned path while plan mode is active, then move the file into today's dated dir as the first action after plan mode ends.
- **Never commit plan/spec documents.** Session-authored plans, specs, and design docs live in the plans vault only — never `git add` or commit them into a project repo, and exclude them from any staging sweep (`git add -A` included). If one is needed in a repo temporarily, it stays untracked.

## Commits — all projects

Commit as you go: after each coherent unit of work, stage only task-owned changes and use the commit skill to create a local checkpoint without waiting for a separate request. Run the relevant checks first, state any incomplete validation honestly, and keep commits on the task branch. Do not push without explicit authorization.

Whenever a subagent makes a git commit, it must ALWAYS: first stage its changes (`git add`), then invoke the `/commit` skill to commit what's staged — no raw `git commit` from subagents. When dispatching any subagent that may commit, include this requirement explicitly in its prompt.

## Personal skills

When I type one of these slash triggers, invoke the Skill tool with that skill before doing anything else.

- **graphify** (`~/.claude/skills/graphify/SKILL.md`) — any input to knowledge graph. Trigger: `/graphify`
- **demuddy** (`~/.claude/skills/demuddy/SKILL.md`) — editorial pass turning a much-edited plan/spec into a handover-ready one (strip decision archaeology, dedupe rules, build order; keep every gotcha and cite). Trigger: `/demuddy [path]`
- **ivtg** (`~/.claude/skills/ivtg/SKILL.md`) — investigator: issues fed one at a time, each investigated across the named repos by an Opus agent, reviewed by codex, written into one dated plan file. Never implements. Trigger: `/ivtg`
- **syncup** (`~/.claude/skills/syncup/SKILL.md`) — pick repos (from the session, behind-target MRs, or a named stack), refresh main from origin, rebase the working branch onto it and every behind MR onto its target branch, resolve conflicts, hand uncommitted work back intact. Pushes rebased MR branches only. Trigger: `/syncup [repo|stack ...]`
- **humanize** (`~/.claude/skills/humanize/SKILL.md`) — rewrite Claude-authored text (doc, MR description, message draft) so it reads like Ryan wrote it: strip AI tells, match his voice per register. Trigger: `/humanize [light] [path]` (`light` = sentence-level only, keeps structure)
- **loop-me-in** (`~/.claude/skills/loop-me-in/SKILL.md`) — turn an approved plan into a brief a fresh session can execute unattended: resolved worktrees, traps, phases, gates, stop conditions. One worktree per repo and a chat completion post are defaults. Trigger: `/loop-me-in [path]`
- **om-build** (`~/.claude/skills/om-build/SKILL.md`) — build an OM Chat GUI from source and put it in front of Ryan: the daemon-embedded `/rooms` GUI, or the hosted `/chat/` cloud fork. Covers the swap onto the live install. Trigger: `/om-build [--hosted|--cloud] [--no-gui]`
- **testing-harness** (`~/.claude/skills/testing-harness/SKILL.md`) — browser rig for proving a change in the running OM Chat GUI. Two modes: `--parity-check` (cloud vs local daemon, visual before/after report) and `--regression` (behavioral sweep of the latest changes — designed, not built). Plus DMs/reads through the real UI and one-off Playwright probes. Trigger: `/testing-harness`
- **panos** (`~/.claude/skills/panos/SKILL.md`) — once MRs have landed, review each one the way Panos (`pan26`) would, on codex `gpt-6.1-sol`; verify every finding, fix and push the real ones. Never comments on the MR. Trigger: `/panos [MR ...] [--model MODEL]`
- **shared-dev** (`~/.claude/skills/shared-dev/SKILL.md`) — bring up the backend services a session's change needs in shared-dev against the databases on Sean's PC, probe with real data, tear down. Never modifies the prod clones in `public`; prod reads only from tsdb2/pgmeta0 with my go. Trigger: `/shared-dev [repo ...] [--fe] [--keep]`, `/shared-dev down`, `/shared-dev rebaseline`
- **bump-rc** (`~/.claude/skills/bump-rc/SKILL.md`) — release a new `@openmarket/rooms-client`: pick the bump from what actually changed, run the release script, update both GUI consumers' pins. Trigger: `/bump-rc [version]`
