---
name: humanize
description: Use when Claude-authored text (design doc, MR description, README section, chat/message draft) needs to read like a specific person wrote it — before pasting into Discord or GitLab, before publishing a doc, or when text shows AI tells like perfect parallelism, em-dash qualifiers, "Crucially,", recap paragraphs, zero first person. Takes a voice reference file; asks for one if none is given. Trigger: /humanize [light] [--voice <path>] [path].
---

# Humanize — make Claude output read like a real person wrote it

## Overview

Surface cleanup is not enough: dropping "Crucially," and bold bullets while keeping the triads, the recap paragraph, and the uniform confidence still reads as AI. This skill rewrites a target against a tell taxonomy and a voice reference describing the person whose voice it should carry.

**Core principle: substance is the only invariant. Structure, register, and rhythm should all look like the voice reference's.**

## Voice reference resolution

The voice reference is any file that describes how one person writes: register profiles, voice rules, lexicon, boundaries, and verbatim samples. Accepted shapes include the bundled profile at [references/voice.md](references/voice.md) and selfmd persona cards (markdown with a `Card data` JSON block).

1. `--voice <path>` argument wins.
2. Else ask the user for a path before reading the target. Offer the bundled `references/voice.md` as one option and free text for any other file. Do not guess or silently default.

Read the whole reference. Use its prose sections; when a JSON card block only repeats the prose, skip it. Verbatim samples and measured stats are the ground truth: when a rule and a sample disagree, trust the sample.

## Target resolution

1. Explicit path argument wins.
2. Else: text pasted in the invoking message.
3. Else: the most recent substantial Claude-authored deliverable in the conversation (doc, MR description, message draft).

Read the whole target before touching it.

## Modes

- `/humanize [path]` — **full rewrite** (default). Structure may change: tables become prose, bullets merge, parallelism breaks, ordering shifts.
- `/humanize light [path]` — **sentence-level only**. Sections, tables, and bullets stay; only tell-carrying sentences are rewritten in place.

## Procedure

1. Resolve the voice reference (above) and read [references/tells.md](references/tells.md) (taxonomy).
2. Detect the target's register — chat message / design doc / MR description / README / channel escalation — and match the closest register in the voice reference. If the reference covers no register close to the target (a chat-only card asked to voice a design doc), say so and use the bundled `references/voice.md` for that register.
3. Rewrite per mode, working through tells.md top-down: structural first (they survive sentence-level edits), then sentence/lexical, then register/persona, then content-shape. Apply the reference's voice rules and lexicon, bounded by its boundaries and "never" list and by the anti-overcorrection rules in tells.md.
4. Verify invariants below.
5. Report changes grouped by tell category, plus anything deliberately kept (e.g. a table that earns its keep), and name the voice reference used.

## Hard invariants — both modes

- Technical facts, numbers, file:line cites, URLs, identifiers, code blocks: byte-exact.
- Security warnings: never softened.
- Commit messages: out of scope — repo commit format governs them.

## Common mistakes

- Fixing the surface and shipping the structure: the strongest tells are parallelism, triads, and recap paragraphs, not vocabulary.
- Ending the rewrite with "In short: X, Y, and Z" — the deleted bullet list restated as a new triad.
- AI-does-casual for chat: lowercase + emoji + tidy clauses is not a real casual register. Take casing, punctuation, typo level, emoji rate, and message length from the reference's samples and stats — and tell one story, do not summarize all the facts.
- Hedging everything: hedges go only where the source text is genuinely uncertain, and in the hedge words the reference uses.
- Polishing the grammar: comma splices, dropped articles, dropped apostrophes, and missing terminal periods are part of a voice when the reference shows them; do not fix them into AI-perfect sentences.
- Copying sample sentences wholesale when the target overlaps a sample's subject: imitate the shapes, write fresh sentences.
