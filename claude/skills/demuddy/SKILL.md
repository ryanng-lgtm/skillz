---
name: demuddy
description: Use when a plan, spec, or design doc has accumulated edits from multiple discussion rounds and is about to be handed to an implementing agent (or human) — symptoms include date-stamped decisions, "considered and rejected" passages, the same rule stated in several sections, bold "Verified:"/"Decision:" framing, or sections ordered by when they were added rather than build order. Trigger: /demuddy [path], "de-muddy", "editorial pass", "clean this plan for handover".
---

# Demuddy — editorial pass for handover-ready plans

## Overview

A plan that went through many editing rounds accretes conversation archaeology. The implementer needs instructions and facts; the negotiation that produced them is noise that muddies execution.

**Core principle: remove only what you can positively identify as editorial residue. Everything else stays.**

This is deliberately the inverse of "keep only instructions and facts". Plenty of load-bearing content is neither: the reason a deliberate deviation exists, an unresolved question, a negative result, a constraint that only ever got written down inside a rejected-alternative discussion. A delete-unless-instruction rule eats all of it. **When you cannot classify a sentence, it stays.**

**Editorial residue** is the short list of things you may remove: decision framing and dates that carry no applicability (`**Decision, verified:**`, "(decided 2026-07-20)" on a rule with no expiry), politeness and hedging, restatements of a rule already stated in full elsewhere, transcript back-and-forth ("good catch — updated"), and section ordering that reflects when text was added.

## Target

**In-place rewrite is destructive and this vault is not version-controlled** — `~/.claude/plans` resolves into iCloud with no git, so a bad pass has no local undo.

- With a path: use it.
- Without a path: resolve candidates **read-only**, then print the absolute path and a content hash and ask which. "Most recently edited" and "most recently discussed" are different orderings, and the conversation may have mentioned a scratch copy, a generated plan, or a stale duplicate. Never break the ambiguity by guessing.

Read the WHOLE file before touching it.

## Protected — never removed, never silently resolved

Rule 6's old enumeration was too short. These categories survive in substance, not just as headings:

- Gotchas, traps, and do-not-"fix"-this warnings
- `file:line` cites, URLs, identifiers, numbers, limits, thresholds
- Invariants, conventions, verification matrices (**every cell**)
- **Risks, unknowns, open questions, assumptions** — an editorial pass may never answer, resolve, or drop one. Downstream skills mine exactly this section; `loop-me-in` reads it hardest, because "does this fix even address the report?" lives there.
- **Rationale** for any deliberate deviation — the sentence that stops the next implementer "correcting" it
- **Negative results and evidence** — "the streaming version OOMed at 250k records" is why an option is closed
- Dependencies, rollback constraints, compatibility limits, security and performance concerns
- Conditions to revisit, and anything that determines whether a decision still applies

Keeping the `Risks` heading while emptying it is a failure, not a pass.

## The contract — what the output IS

1. **Decisions read as present-tense spec** — but preserve what governs their *applicability*: status (`provisional`, `approved`, `superseded`), the version or period they hold for, the owner where that is what makes them authoritative, and the rationale where losing it invites reversal. Strip the decorative framing, not the scope. "Accepted experimentally until the API migration" must not become a permanent rule.
2. **Verification status is never broadened.** A blanket "All file:line cites verified against code on \<date\>" is permitted *only* after enumerating every cite and confirming all of them against one revision. Otherwise group by status — verified (date, revision), proposed, stale. Turning five verified and two proposed cites into a universal claim is a fabrication, not an edit.
3. **Each rule stated exactly once as spec** — where the rules are genuinely the same rule. Deduplicate only when actor, scope, condition, exception, and normative force all match. "Clients retry reads" and "workers retry idempotent writes" are not duplicates. The consolidated wording must entail every statement it replaces; if it doesn't, keep the variants.
4. **Rejected alternatives keep four fields where present**: the alternative, the rejection reason, the supporting evidence or negative result, and the conditions under which it becomes viable again. Compress repetition, not information. There is no one-line limit — a one-line rejection that drops "it violates tenant isolation" invites the next implementer to repeat the experiment.
5. **Sections in build/read order**, with ordering dependencies modelled first. Order can itself be load-bearing: prerequisites, rollout phases, hazards that must precede the irreversible step they warn about, evidence in chronological sequence. Then re-check cross-references, section letters, generated anchors, footnotes, relative phrases ("the exception below"), the title, and any *other document* that links into this one.
6. **Compression must preserve meaning, not just the topic.** "Survives" means the actor, action, scope, condition, exception, consequence, rationale, and recovery path all survive. "Do not cache this lookup during backfill because tenant identity changes after replay; clear the cache before retry" → "Do not cache lookups" keeps a sentence and destroys the instruction.
7. **Completed work is marked closed only when completion is explicit**, and it keeps its scope, date/revision, method, exclusions, and any open findings. Past-tense discussion is not proof an audit covered the final design. Write "do not repeat unless inputs or scope change", never an unconditional "do not re-audit" — later edits can invalidate it.

## Procedure

1. Read the entire file.
2. **Write the candidate to a new path** (`<name>.demuddy-candidate.md`) beside the original. Do not touch the original yet.
3. **Run the coverage check** below. If it fails, fix the candidate — never the check.
4. Produce a unified diff of original → candidate and read it yourself as a reviewer, not as the author.
5. Only then replace the original, and keep the candidate until the report is delivered.
6. Report four lists: **Removed** (artifact classes), **Restructured** (reorders, retitles), **Kept in full** (the load-bearing items an anxious reader would fear losing), and **Coverage check** (the numbers below, so the claim is evidence and not self-attestation).

### The coverage check

Self-reported "kept in full" is the same agent attesting to what it may have overlooked. Extract mechanically from both files and diff the sets:

```sh
orig="path/to/plan.md"; cand="path/to/plan.demuddy-candidate.md"
extract() {   # cites, URLs, numbers+units, modal/conditional sentences, negations, table rows
  grep -oE '[A-Za-z0-9_./-]+\.[a-z]+:[0-9]+' "$1" | sort -u          # file:line cites
  grep -oE 'https?://[^ )>]+'               "$1" | sort -u           # links
  grep -oE '\b[0-9][0-9,._]*\s*(ms|s|m|h|MB|GB|KB|%|x|k)\b' "$1" | sort -u
  grep -inE '\b(must|never|always|do not|don.t|unless|except|only if|cannot)\b' "$1" \
    | sed 's/^[0-9]*://' | sort -u                                    # normative sentences
  grep -cE '^\|' "$1"                                                 # table row count
  grep -c '?'    "$1"                                                 # unresolved questions
}
diff <(extract "$orig") <(extract "$cand")
```

Anything present in the original and absent from the candidate must have an explicit, stated reason. A dropped table row, a vanished `must`, a lost threshold, or a missing cite fails the check by default.

**The question count is the cheap detector for the worst failure mode.** It drops when an open question is deleted *or silently answered* — a rewrite that turns "Does this cover reports created before migration?" into "Yes, it covers pre-migration reports" passes every other check in this file. A lower count than the original fails the pass.

**Also check, by reading:** every `Risks`/`Unknowns`/`Open questions`/`Assumptions` heading still has contents.

### Idempotency

A compliant output is a **fixed point**: running demuddy again produces no substantive diff. A second pass over an already-demuddied file is an *audit against this contract*, not another compression round — otherwise pointers and compressed rejections stop looking instruction-shaped and get deleted as archaeology, and the document erodes one pass at a time.

## Common mistakes

- **Deleting rationale because it isn't an instruction.** The sentence explaining why a deviation is deliberate is what stops the next implementer reverting it. Highest-value content in the file, and the easiest to classify as noise.
- **Emptying a Risks or Open questions section while keeping its heading.** Passes every structural check and destroys what the downstream run depends on.
- **Answering an open question in passing.** An editorial pass has no authority to resolve one.
- Over-trimming a "do not correct this deliberate deviation" warning.
- Leaving "decided/accepted" ghosts inside invariants and risks after cleaning the fix sections.
- Broadening a verification claim to cover cites that were never checked.
- Merging two rules that differ by actor, scope, or exception.
- Reordering sections but not the cross-references, anchors, or the title — or moving a hazard after the irreversible step it guards.
- Compressing a verification matrix into vagueness — matrices are instructions; keep every cell.
- Rewriting in place before the coverage check, in a vault with no version control.
