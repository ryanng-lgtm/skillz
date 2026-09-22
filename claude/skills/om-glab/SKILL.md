---
name: om-glab
description: Build and install the local OM daemon with its /rooms GUI from the GitLab openmarket-chat checkout, linked to openmarket-internal. Alias of om-build hosted mode. Trigger: /om-glab or $om-glab.
---

# om-glab

Use the [om-build hosted workflow](../om-build/SKILL.md) with the GitLab GUI
checkout. Read that skill before running this alias; its provenance, main
worktree, build, install and verification rules apply.

```bash
om-glab          # build, install and verify
om-glab --gate   # inspect without installing
```

`skillz/install.sh` links the shell command into `~/.local/bin`; its target is
`~/.claude/skills/om-glab/scripts/hosted.sh`. The same skill is available as
`$om-glab` in Codex and `/om-glab` in Claude.

Defaults: `~/Documents/GitLab/openmarket-chat-gitlab` for the GUI and
`~/Documents/GitLab/openmarket-internal` for the daemon. `OM_GUI` and `OM_MONO`
override those paths. Resolve and report both source branches, commits and
dirty state before building; the alias builds their checked-out content and
does not switch branches or update them to main.

This builds the root daemon `/rooms` artifact and links rooms-client to core.
It does not run `build:cloud` or deploy `/chat/`. Forward hosted options such as
`--force` and `--no-gui` unchanged to the shared script.

`om-hosted` / `om-build` keep their GitHub GUI default. Both commands target the same local
daemon installation, so the most recent successful install selects its GUI.

For a browser probe, set `OM_CHAT_REPO` to the selected GitLab checkout and
`OM_CHAT_LOCAL_PORT` to the installed daemon's port so the report records the
artifact actually being tested.
