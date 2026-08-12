---
name: demuddy
description: Use when a plan, spec, or design doc has accumulated edits from multiple discussion rounds and is about to be handed to an implementing agent (or human) — symptoms include date-stamped decisions, "considered and rejected" passages, the same rule stated in several sections, bold "Verified:"/"Decision:" framing, or sections ordered by when they were added rather than build order. Trigger: /demuddy [path], "de-muddy", "editorial pass", "clean this plan for handover".
---

# Demuddy — editorial pass for handover-ready plans

## Overview

A plan that went through many editing rounds accretes conversation archaeology. The implementer needs instructions and facts; the negotiation that produced them is noise that muddies execution.

**Core principle: every sentence must either instruct the implementer or state a verified fact. Anything else is archaeology.**

## Target

If no path is given, the target is the plan file most recently edited or discussed in the conversation. Read the WHOLE file before touching it.

## The contract — what the output IS

1. **Decisions read as present-tense spec.** "Guests never fetch." — not "(decided 2026-07-20)", not "Consequence, accepted:", not "Decision, verified:". Dates and decision framing carry zero instruction.
2. **One blanket verification line** near the top ("All file:line cites verified against code on \<date\>"), then every cite below reads as plain fact. No per-fact "**Verified:**" alarms.
3. **Each rule stated exactly once as spec**, optionally once more as an invariant. Every other mention becomes a short pointer or is deleted.
4. **Rejected alternatives get one line** in Out-of-scope: the rejection + an upgrade path only if forward-useful. The debate that led there is deleted.
5. **Sections in build/read order** (what you make first comes first), not accretion order. Cross-references, section letters, and the title updated to match.
6. **All load-bearing content survives**: gotchas, file:line cites, invariants, verification matrices, conventions, do-not-"fix"-this warnings. Deletion test per sentence: *does the implementer lose an instruction or a fact?* If yes, it stays — compressed if verbose, never dropped.
7. **Completed work is marked closed.** An audit already performed reads "Audit result (complete — do not re-audit): …" so the implementer doesn't redo it.

## Procedure

1. Read the entire file.
2. Rewrite it in place (full-file Write) to the contract above — same substance, same plan structure (keep the owner's section format, e.g. Root cause/Fix/Invariants/Risks/Verification).
3. Re-check every cross-reference the reorder touched.
4. Report three lists: **Removed** (artifact classes, not line-by-line), **Restructured** (reorders, retitles), **Kept in full** (the load-bearing items an anxious reader would fear losing).

## Common mistakes

- Over-trimming: deleting a gotcha or a "do not correct this deliberate deviation" warning as noise. These are the highest-value sentences in the plan.
- Leaving "decided/accepted" ghosts inside invariants and risks after cleaning the fix sections.
- Reordering sections but not the cross-references (or the title).
- Compressing a verification matrix into vagueness — matrices are instructions; keep every cell.
