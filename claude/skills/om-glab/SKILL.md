---
name: om-glab
description: >-
  Use when the local OM daemon and its /rooms GUI have to be built from source and installed from the GitLab GUI checkout (om-chat-cloud), linked to openmarket-internal, instead of the GitHub openmarket-chat default that om-build uses. Do not use it for the hosted /chat/ cloud deploy or for om-build's cloud or mobile targets. Trigger: /om-glab [--gate|--force|--no-gui], $om-glab.
---

# om-glab — build and install the OM daemon with its /rooms GUI from the GitLab checkout

## Overview

Use the [om-build hosted workflow](../om-build/SKILL.md) with the GitLab GUI
checkout. Read that skill before running this alias; its provenance, main
worktree, build, install and verification rules apply.

**Core principle: Resolve and report both source branches, commits and dirty state before building; the alias builds their checked-out content and does not switch branches or update them to main.**

## Sources

Defaults: `~/Documents/GitLab/om-chat-cloud` for the GitLab GUI and
`~/Documents/GitLab/openmarket-internal` for the daemon. `OM_GUI` and `OM_MONO`
override those paths.

## Procedure

```bash
om-glab          # build, install and verify
om-glab --gate   # inspect without installing
```

`skillz/install.sh` links the shell command into `~/.local/bin`; its target is
`~/.claude/skills/om-glab/scripts/hosted.sh`. The same skill is available as
`$om-glab` in Codex and `/om-glab` in Claude.

This builds the root daemon `/rooms` artifact and links rooms-client to core.
It does not run `build:cloud` or deploy `/chat/`. Forward hosted options such as
`--force` and `--no-gui` unchanged to the shared script.

`om-hosted` / `om-build` keep their GitHub GUI default. Both commands target the same local
daemon installation, so the most recent successful install selects its GUI.

For a browser probe, set `OM_CHAT_REPO` to the selected GitLab checkout and
`OM_CHAT_LOCAL_PORT` to the installed daemon's port so the report records the
artifact actually being tested.
