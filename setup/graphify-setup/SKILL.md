---
name: graphify-setup
description: >-
  Use when a repo, or a workspace of sibling repos, needs a local graphify
  knowledge graph that is never committed and that git hooks keep current: a
  project with no graphify-out/graph.json, a graph that predates its ignore
  rules, or several repos to merge into one graph. Trigger: /graphify-setup,
  $graphify-setup.
disable-model-invocation: true
---

# graphify-setup — run the graphify install runbook

## Overview

[`INSTALL.md`](INSTALL.md) in this skill's directory is a self-contained agent runbook. It installs graphify, builds a local graph for one repo or for several merged into one, keeps everything it creates out of git and out of the graph, and installs the hooks that keep the graph current.

**Core principle: run `INSTALL.md` exactly as if the user had dropped that file into a fresh session. It is the whole procedure; this file adds nothing to it.**

## Procedure

1. Read `INSTALL.md` in full before running anything.
2. Treat any arguments given with the command as the user's message sent alongside the file, such as the mode or the repos.
3. Follow it from Step 0, with its own gates, questions, and report.

## Rules

- Never edit `INSTALL.md` to fit a repo. Its survey steps and ADAPT sections handle the differences.
