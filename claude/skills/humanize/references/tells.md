# AI tells — taxonomy

Work top-down: structural tells first (they survive sentence-level edits), then sentence/lexical, then register. Each entry: the tell, the fix.

## 1. Structural — visible before reading a word

- **Perfect parallelism.** Every bullet/cell/clause the same shape ("verb: detail, detail, detail"). Humans are uneven: one cell is three words, another rambles. Fix: vary shape and length deliberately; let one item get most of the words.
- **Rule-of-three.** Triads of adjectives, examples, clauses, everywhere. Fix: two items, or four, or one item explained properly.
- **Recap relocation.** Killing a bullet list but restating it as "In short: X, Y, and Z" — same tell, new position. A closing summary that re-enumerates the section is AI. Fix: end on the last real point, or on the one consequence that matters.
- **Header-itis.** Sections and bold headers on a three-paragraph answer. Fix: prose with plain connectors.
- **Double summary.** Same claim at top and bottom. Fix: keep one.
- **Symmetric coverage.** 3 pros / 3 cons; equal words on unequally important things. Fix: uneven emphasis — loud on the surprising part, one clause for the rest.
- **Table-where-prose-belongs.** Tables for things with two rows or non-enumerable content. Fix: a sentence.
- **Equal paragraph lengths.** Fix: let one paragraph be two lines and another be ten.

## 2. Sentence-level

- **Colon-chained noun stacks.** "create incident: catalog copy, impact_override, component set to severity, identity stamped in metadata" — four payload facts in one breath. Humans say what the call does and let the payload live in code. Fix: one fact per sentence, or point at the code/payload.
- **Em-dash qualifiers.** "— truncated to 12 characters for readability —". The signature move. Fix: parentheses, a separate sentence, or cut the qualifier. No em-dashes inside the parentheses either — the human parenthetical is plain: "(sha256, first 12 chars)".
- **Contrast frames.** "not just X, but Y", "it's not about X; it's about Y". Fix: state Y.
- **Participial tails.** "…, ensuring consistency across environments", "…, preventing incident spam", "…, completing the lifecycle". Fix: new sentence with a real subject, or delete — the tail usually restates the sentence.
- **Front-loaded adverbs.** "Crucially,", "Notably,", "Importantly,". Fix: delete; if it's actually crucial, say why in a plain sentence ("This is also what makes resolve work at all.").
- **No fragments, ever.** Every sentence lands perfectly. Fix: fragments where a human would fragment. Comma splices are allowed.

## 3. Lexical

- **LLM vocabulary.** leverage, robust, seamless, comprehensive, streamline, facilitate, utilize, "serves as", "acts as", "key" as adjective, "a variety of", ensure/ensures. Fix: the short verb ("use", "make sure").
- **Compressed jargon asides.** "best-effort", "identity stamped", "not in the serving path". Precise, but nobody types "stamped" about a JSON field on a first draft. Fix: the phrase a person would type first ("written into the metadata").
- **Nominalizations.** "performs deduplication of" → "dedupes".

## 4. Register / persona — the richest vein

- **Zero first person.** Humans own decisions: "I deliberately left the default policy alone", "we've opted to use". Fix: put a person behind every decision.
- **Zero hedging.** Humans flag real uncertainty and its source: "From what I've read it's basically…", "shouldn't normally fire", "haven't tested the retry path". Fix: hedge what is actually uncertain — and only that.
- **Uniform confidence.** Everything asserted at the same strength. Humans are loud about the surprising part, casual about the rest.
- **No process references.** Humans say "turned out", "after digging", "for now", "assuming it lives in the occ cluster".
- **No opinions or asides.** Humans editorialize: "full hash is overkill and ugly in the UI", "this API is weird", "annoyingly".

## 5. Content-shape

- **Exhaustive coverage.** Mentioning every branch/edge case when a human mentions only the surprising one. In chat this is fatal: a human summarizes the one thing that matters, not all the facts.
- **Preamble/postamble.** "Let's break this down", "In summary". Delete both ends.
- **Payload enumeration in prose.** Say what the call does; the fields live in the code block.

## Positive moves — add, don't just remove

- Uneven emphasis: ramble on the interesting part, wave at the rest.
- First person and ownership: "I went with X because…".
- Hedges tied to a knowledge source: "From what I've read…", "Assuming…".
- Colloquial connectors: "so", "anyway", "also", "fwiw".
- Reference the process, not just the result.
- Concrete numeric examples over abstractions ("10 rules firing at once still produce one webhook call").
- Let code carry the detail.

## Anti-overcorrection — faking humanity is its own tell

- No injected typos or forced slang outside registers where the voice profile shows them.
- No emoji unless the voice profile uses them (Ryan's chat register: none).
- Never hedge something that is certain; never blur technical precision.
- Code blocks, identifiers, numbers, URLs: byte-exact.
- "AI-does-casual" — lowercase + emoji + tidy parallel clauses — is not chat register. Check the voice profile's actual chat sample.
