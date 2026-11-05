# Skill template

The reference for writing a skill in this repo. It is not a skill and is not installed: read it, then write `shared/skills/<name>/SKILL.md` (or `personal/<name>/SKILL.md` for one of Ryan's own) from the skeleton at the end. Where a skill goes, how it is shared with Codex, and the upkeep that comes with adding one are in the root `CLAUDE.md`.

## Frontmatter

- `name` — the skill's directory name, lowercase with hyphens. It is also the trigger: `/name` in Claude Code, `$name` in Codex.
- `description` — the only part the agent reads when deciding whether to load the skill, so it says when to use the skill, not how the skill works. Start with "Use when", name the situations and symptoms a user would describe, and end with `Trigger:` followed by the slash form and any phrases that should fire it. A description that summarises the procedure gets followed instead of the body.
- Optional Claude Code fields, only when the skill needs them:
  - `disable-model-invocation: true` — only the user can start it. Use for side effects you want to trigger by hand, such as a release, a push or a one-time setup. Codex ignores it; give the skill the `agents/openai.yaml` policy below as well.
  - `user-invocable: false` — background knowledge only Claude loads, hidden from the `/` menu.
  - `allowed-tools` — tools the skill may use without a permission prompt while it runs, e.g. `Bash(om *)`.

## Body

- Open with `# <name> — <what it does, in a phrase>`.
- `## Overview`: the problem the skill solves, then the one principle, in bold, that decides the cases the steps don't cover.
- The steps, as a `## Procedure` list or numbered `##` sections, in the order they run. Each step says what to do and how to tell it is done.
- `## Rules` for anything the skill must never do, when there is any.
- `## Common mistakes`: each mistake in bold, then why it is wrong and what to do instead. Add one whenever the skill goes wrong in use.

Write the body as instructions to the agent, in the present tense, with no history and no explanation of tools the agent already knows. Keep `SKILL.md` to what every run needs. Move bulky detail (catalogs, long examples, API notes) into `references/` and link it from the step that needs it. A `SKILL.md` past about 500 lines should be split that way.

## Supporting files

- `references/` — detail the skill reads on demand.
- `scripts/` — code the skill runs. Tests go in `scripts/tests/` and run with `python3 -m unittest discover -s tests` from `scripts/`.
- `agents/openai.yaml` — Codex metadata for a skill shared with Codex: its skill-list entry under `interface:` (`display_name`, `short_description`, `default_prompt`) and, for a skill only the user should start, Codex's equivalent of `disable-model-invocation`:

  ```yaml
  policy:
    allow_implicit_invocation: false
  ```

Refer to these by their path relative to the skill directory. A command that runs one of the skill's own scripts uses `${CLAUDE_SKILL_DIR}/scripts/<file>`, which Claude Code fills in, and says that under Codex the path is relative to the SKILL.md folder.

## Skeleton

````markdown
---
name: <name>
description: Use when <situations and symptoms, in the user's words>. Trigger: /<name> [args], "<phrase>".
---

# <name> — <what it does, in a phrase>

## Overview

<The problem this solves and the outcome it produces.>

**Core principle: <the one rule that decides the cases the steps don't cover>.**

## Procedure

1. <What to do, and how to tell it is done.>
2. <...>

## Rules

- <Something the skill must never do, and why.>

## Common mistakes

- **<Mistake.>** <Why it is wrong, and what to do instead.>
````
