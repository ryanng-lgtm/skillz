---
name: update-knowledge-base
description: >-
  Use when a conversation, investigation or task has produced findings worth
  keeping and the user asks to put them into a knowledge base, docs dir,
  wiki or vault ("update the vault with what we found", "write this up in
  the docs", "add this to the GO Backend dir", "before I clear the context,
  save the findings"), including when the task was dropped or superseded.
  Not for a plan or spec (those live in the plans vault) or for a one-line
  memory note. Trigger: /update-knowledge-base [kb name or path],
  $update-knowledge-base [kb name or path], "update the knowledge base",
  "record the findings".
---

# update-knowledge-base — fold a conversation's findings into a knowledge base

## Overview

A long session leaves durable facts (how a mechanism works, a constraint found by test, a decision and its reason, a command that worked) mixed with residue (hypotheses that died, options that lost, who said what when, next steps that will be stale by morning). The knowledge base wants only the first kind, each in the doc that owns its topic, written for a reader who was not in the conversation.

**Core principle: every fact gets one home it would be looked up in; everything that is only true of this session is discarded.**

**REQUIRED SUB-SKILL:** when the target dir carries `CLAUDE.md` with `scripts/build-index.py`, it is a docs-knowledge-base dir: follow docs-knowledge-base for frontmatter, numbering, links, the index script and the commit. This skill decides what goes in and where; that one decides the shape.

## Procedure

1. **Resolve the target, never guess it.** With a path: use it. With a name ("GO Backend", "the infra docs"): search the places a knowledge base lives (Obsidian vaults under iCloud and `~/Documents`, `docs/` dirs of the repos in the conversation, memory pointers) for a directory whose name matches. Exactly one match: print its absolute path and continue. None or several: list what was found and ask for the exact path. Nothing named at all: ask for the exact path. A knowledge base is a directory of markdown; a single file is a target only when the user names that file.
2. **Learn the target's conventions before writing.** Read its `CLAUDE.md`, `README` or top `INDEX.md`, the index of the area you will write in, and two docs there. Note the link style (wikilinks or markdown), frontmatter fields, numbering, glossary and traps docs, and the voice (plain words, "explain like I'm five" callouts, cite style). The new text must be indistinguishable from the old.
3. **Harvest, then triage.** List every candidate from the conversation and sort it with the table below. Record the discards; the user sees them in the report and can veto. Treat a claim the conversation did not verify as a fact only inside a "not verified" callout.
4. **Place each kept fact in its one home.** An existing doc on that topic: update it in place and bump its date. A topic no doc covers: a new numbered doc in the area that owns the subject. A term the vault defines nowhere: the glossary. A rule that cost time or a way to lose data: the traps or gotchas doc. A pointer to material that lives elsewhere (a plan, evidence, a ticket): one line with the path, not a copy. Cross-link the touched docs; update each touched doc's description when its scope changed. Never a new doc named after the session or the task ("findings", "investigation notes").
5. **Write in the present tense for a stranger.** State what is true, with file and line cites pinned to a commit, measurements with their date and source, and decisions with their one-line reason. A dropped or superseded task gets a short status line saying so and where the plan lives; it gets no "next step" section.
6. **Verify and commit.** Run the target's checker when it has one (`build-index.py`, then `--check`), fix every problem, and regenerate indexes. List the area folder for stray files. When the dir is in git, stage only the files you touched, by name, and commit through the commit skill. A dir under iCloud is written like any other; if a write is refused, say so rather than working around it.
7. **Report in a few lines:** new docs, updated docs and what changed, each discard in one line, the checker result.

## Triage

| Keep | Discard |
| --- | --- |
| How a mechanism works, with the code cite that proves it | The order things were discovered in |
| A constraint found by test, with the environment it was tested on | Hypotheses that the test refuted, beyond one line saying they are ruled out |
| A decision and its reason; a design still standing, in a paragraph | Options that lost, review rounds, who proposed what |
| A measurement or count, dated, with its source | Figures nobody would act on, estimates, timings from unrepresentative data |
| A command that worked, with what it was run against | Commands tried and abandoned |
| A gotcha that cost time or can lose data | Mistakes that were the agent's own and not the system's |
| A pointer to plan, evidence or ticket, as a path | The plan's contents, step lists, open questions |
| Scope and status of a task when the doc exists because of it | Session chronology, messages, approvals |

When a candidate fits neither column, ask: would someone look this up in a month? Yes: keep. No: discard.

## Rules

- Never write credentials, tokens, DB URLs or anything the conversation read from a secrets file, and never stage such files from the target dir.
- Never create or edit `QUESTIONS`, `ISSUES` or backlog files behind an ask-first gate without asking.
- Never overwrite a doc you have not read in full this session.
- Never leave a "next step" or "proposed" section for a task that is not live; a reader a month later cannot tell it is stale.

## Common mistakes

- **Dropping a raw note at the vault root.** The dir has structure; a note outside it is invisible to the index and reads as scratch. Place it per step 4 or do not write it.
- **Writing a ledger.** "First we checked X, then Y failed, then codex found Z" is session history. Write what is true now; git holds the history.
- **Recording the losing options as live.** A design that was ruled out is one line in a "ruled out" list with its reason, not a section.
- **Leaving the plan's open questions in the docs.** They belong to the plan. The doc records what was settled.
- **Guessing the knowledge base from a vague name.** Two vaults with similar names, a nested vault, a docs dir inside a repo: resolve read-only, print the path, ask when more than one fits.
- **Matching the content but not the voice.** A vault written in plain words with callouts gets the same; a terse engineering wiki gets terse. Read two docs first.
