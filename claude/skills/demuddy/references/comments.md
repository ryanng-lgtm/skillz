# Demuddy for code comments

Same core principle as for plans: remove or rewrite only what you can
positively identify as residue, and when you cannot classify a comment, it
stays. Then make what stays readable to someone new to this code who does not
have much technical background.

## Target

- `/demuddy comments`: the comments the current branch added or changed since
  it left the default branch (`git merge-base HEAD origin/HEAD`; if
  `origin/HEAD` is unset, use `origin/<default branch>`). Comments the change
  did not touch are out of scope.
- `/demuddy comments <path|rev>`: the comments in those files, or in that
  revision range's changes.
- Edit comments only, never code.
- Start from a committed change. The pass is its own commit, made with the
  commit skill, so one revert undoes it. Never squash it into the feature
  commits, and never push.
- Skip generated files (`Code generated ... DO NOT EDIT`).

## Residue: the only things removed

- **Change narration:** "now uses", "previously", "changed to", "fixed",
  "added", "new", "updated", "instead of the old". Git holds the history; a
  comment describes the code as it is.
- **Review and transcript residue:** "per review", "as requested", "good
  catch", "addressing feedback".
- **Restated code:** a comment that says what the next line says, a summary
  echoed above every block, `Step 1:` counting.
- **Reassurance:** "now we can safely proceed", "this should work", "at this
  point the connection is ready".
- **Decision and verification stamps:** "Decision:", "Verified:", a date on a
  rule with no expiry.
- **Ceremonial doc comments** on small unexported helpers whose name already
  says what they do.
- **Section banners and dividers.**
- **AI filler:** "robust", "leverage", "seamlessly", "comprehensive", "it's
  worth noting", "in order to", "ensure that".
- **The same explanation at several sites:** keep it once, where the thing is
  defined. Only when it is truly the same rule: same actor, scope, condition
  and exception.

## Rewrite rules

1. History becomes present tense, and the reason stays. "Previously we cached
   this, but the tenant ID changes after replay, so caching was removed" →
   "Not cached: the tenant ID changes after a replay."
2. Negative results stay; they are why the obvious alternative is not used.
   "Streaming runs out of memory at 250k rows, so this batches."

## Readability

Write for a reader who is new to this code and not deeply technical: a
reviewer from another team, a new hire, someone following a bug report. A
rewritten comment is never longer than the one it replaces; plainer comes
from swapping and cutting words, never from adding them.

- Short sentences, everyday words, one idea each. Cut a long comment to what
  the reader needs at that line.
- Swap jargon for a plain word of about the same length: "safe to repeat" for
  idempotent, "drops duplicates" for dedupes, "transaction" for tx. When no
  short plain word exists, keep the term. Never add a gloss or a spelled-out
  acronym beside it.
- Never add an explanation the original did not have.
- Names stay exactly as written: identifiers, file names, flags, config keys,
  error strings. They are how a reader searches.
- Plain never beats precise. Numbers, units, conditions and exceptions stay
  exact; when the plain word would drop one, keep the technical term.

Before: `Retry is idempotent: the PK on (venue, symbol) dedupes, so callers
must never wrap it in a tx — the lock escalates under SSI. Fixed: previously
this retried forever.`

After: `Retry is safe to repeat: the primary key on (venue, symbol) drops
duplicates. Callers must never wrap it in a transaction; under SSI the lock
escalates.`

## Protected

The Protected list in SKILL.md applies in full. In code, also:

- **Comments that tools read** are never edited: build tags and `//go:`
  directives, `//nolint:<linter> // <reason>` (nolintlint fails without the
  reason), `eslint-disable*`, `@ts-expect-error` and `@ts-ignore` with their
  reasons, `# shellcheck disable=`, `# noqa`, `# type: ignore`, pragmas,
  license headers. JSDoc types in `.js` files are type-checked.
- **Doc comments on exported or public API:** plainer wording is fine, but the
  contract stays: inputs, outputs, errors, side effects. In Go, the first
  sentence still starts with the identifier's name.
- **A TODO or FIXME without a ticket** is an open question: list it in the
  report, never delete or answer it.
- **Commented-out code the change added:** list it in the report, never delete
  it silently.

## Procedure

1. List the target hunks. Read the whole function around each comment before
   touching it.
2. Edit the comments.
3. Run Checks A, B and C. If one fails, fix the edit, never the check.
4. Run the repo's build and lint; directives and doc linters read comments.
5. Read the diff as a reviewer, not as the author.
6. Commit with the commit skill.
7. Report five lists: **Removed** (each residue class, with a count),
   **Rewritten for readability**, **Kept** (what an anxious reader would fear
   losing), **Reported, not touched** (ticketless TODOs, commented-out code),
   and **Checks** (the output of A, B and C).

### Check A: code untouched

```bash
git diff -U0 HEAD | grep -E '^[-+]' | grep -vE '^(---|\+\+\+) (a/|b/|/dev/null)' \
  | cut -c2- | grep -vE '^[[:space:]]*($|//|#|/\*|\*|--)'
```

Empty output passes. A printed line is code, a code line with a trailing
comment, or the inside of a docstring: confirm by eye that only comment text
changed on it.

### Check B: nothing load-bearing dropped

```bash
side() { # changed lines on one side of the diff: - or +
  git diff -U0 HEAD | grep -E "^[$1]" | grep -vE '^(---|\+\+\+) (a/|b/|/dev/null)' | cut -c2-
}
facts() { # load-bearing tokens in stdin, duplicates kept
  local t
  t="$(cat)"
  {
    grep -oE '[A-Za-z0-9_./-]+\.[a-z]+:[0-9]+' <<<"$t"                    # file:line cites
    grep -oE 'https?://[^ )>]+' <<<"$t"                                    # links
    grep -oE '\b[A-Z][A-Z0-9]+-[0-9]+\b|[#!][0-9]+\b' <<<"$t"             # tickets, issues, MRs
    grep -oE '\b[0-9][0-9,._]*\s*(ms|s|m|h|KB|MB|GB|%|x|k|rows)\b' <<<"$t" # numbers with units
    grep -oiE '\b(must|never|always|do not|don.t|unless|except|only if|cannot)\b' <<<"$t" | tr '[:upper:]' '[:lower:]'
    grep -oE '\b(TODO|FIXME|HACK|XXX)\b' <<<"$t"
    grep -oE 'nolint[:a-z,]*|eslint-[a-z-]+|@ts-[a-z-]+|shellcheck disable=[A-Z0-9,]+|noqa|type: ignore|go:[a-z]+' <<<"$t"
    grep -o '?' <<<"$t"                                                     # open questions
  } | sort
}
comm -23 <(side - | facts) <(side + | facts)
```

Every printed token was in a removed comment and is in no added one. Put it
back, or give the reason it may go in the report. A lost `?` is the cheap
detector for a question that was deleted or silently answered.

### Check C: no comment got longer

```bash
git diff -U0 HEAD | awk '
  function check() { if (a > r) printf "%s %s grew: %d -> %d chars\n", file, hunk, r, a }
  /^\+\+\+ (b\/|\/dev\/null)/ { file = $2; next }
  /^--- (a\/|\/dev\/null)/ { next }
  /^@@/ { check(); hunk = $2; r = a = 0; next }
  /^-/ { r += length($0) - 1; next }
  /^\+/ { a += length($0) - 1 }
  END { check() }'
```

Empty output passes. Each printed hunk has more comment text than before;
shorten it.

## Idempotency

A second pass over a cleaned change produces no diff: no new explanations, no
further compression.

## Common mistakes

- Deleting the "why" because it reads like narration. "Not cached: the tenant
  ID changes after a replay" is the reason the cache must not come back.
- Dropping the reason after a `nolint`, or editing any other directive.
- Editing a generated file.
- Touching comments the change did not add, or "improving" code while there.
- Simplifying a sentence until it loses its condition: "Do not retry during
  backfill" is not "Do not retry".
- Renaming a term in a comment so it no longer matches the identifier a reader
  will search for.
- Dropping a ticket link while shortening.
