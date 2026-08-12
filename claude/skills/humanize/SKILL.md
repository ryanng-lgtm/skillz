---
name: humanize
description: Use when Claude-authored text (design doc, MR description, README section, chat/message draft) needs to read like Ryan wrote it — before pasting into Discord or GitLab, before publishing a doc, or when text shows AI tells like perfect parallelism, em-dash qualifiers, "Crucially,", recap paragraphs, zero first person. Trigger: /humanize [light] [path].
---

# Humanize — make Claude output read like Ryan wrote it

## Overview

Surface cleanup is not enough: dropping "Crucially," and bold bullets while keeping the triads, the recap paragraph, and the uniform confidence still reads as AI. This skill rewrites a target against a tell taxonomy and Ryan's real voice profile.

**Core principle: substance is the only invariant. Structure, register, and rhythm should all look like Ryan's.**

## Target resolution

1. Explicit path argument wins.
2. Else: text pasted in the invoking message.
3. Else: the most recent substantial Claude-authored deliverable in the conversation (doc, MR description, message draft).

Read the whole target before touching it.

## Modes

- `/humanize [path]` — **full rewrite** (default). Structure may change: tables become prose, bullets merge, parallelism breaks, ordering shifts.
- `/humanize light [path]` — **sentence-level only**. Sections, tables, and bullets stay; only tell-carrying sentences are rewritten in place.

## Procedure

1. Read [references/voice.md](references/voice.md) (register profiles + raw samples) and [references/tells.md](references/tells.md) (taxonomy).
2. Detect register — chat message / design doc / MR description / README — and match the corresponding voice profile. When the profile and a raw sample disagree, trust the sample.
3. Rewrite per mode, working through tells.md top-down: structural first (they survive sentence-level edits), then sentence/lexical, then register/persona, then content-shape. Apply the positive moves, bounded by the anti-overcorrection rules.
4. Verify invariants below.
5. Report changes grouped by tell category, plus anything deliberately kept (e.g. a table that earns its keep).

## Hard invariants — both modes

- Technical facts, numbers, file:line cites, URLs, identifiers, code blocks: byte-exact.
- Security warnings: never softened.
- Commit messages: out of scope — repo commit format governs them.

## Common mistakes

- Fixing the surface and shipping the structure: the strongest tells are parallelism, triads, and recap paragraphs, not vocabulary.
- Ending the rewrite with "In short: X, Y, and Z" — the deleted bullet list restated as a new triad.
- AI-does-casual for chat: lowercase + emoji + tidy clauses is not Ryan's chat register. His has typos, slang, initials, run-ons, no emoji — and it tells one story, it does not summarize all the facts.
- Hedging everything: hedges go only where the source text is genuinely uncertain, ideally tied to a knowledge source ("From what I've read…").
- Polishing his grammar: comma splices, dropped articles, and missing terminal periods are part of the voice; do not fix them into AI-perfect sentences.
