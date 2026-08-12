---
name: ivtg
description: Use when the user wants to queue up bugs, regressions, or issues one at a time and get each one investigated across one or more repos and written up as a fix plan to approve before any code is touched. Trigger: /ivtg, "investigator mode", "investigate these issues", "plan fixes, don't implement".
---

# ivtg — issues in, reviewed fix plans out

## Overview

The user feeds issues one at a time. Each issue gets investigated by an Opus agent, reviewed by a codex agent, and written into one shared plan file, which is demuddied once the session ends. **The terminal state of this skill is a written plan. No code is ever changed here** — implementation happens only when the user says so, in a later turn, outside this skill.

Repo-agnostic: every repo path comes from the user at session start, never from the current working directory alone.

## Phase 0 — session open (once)

1. Run `date +%F` for today's date. Never guess it.
2. Ask the user, in one message: session title, and which repos to scan (names or paths).
3. Resolve each repo to an absolute path (`ls -d`). If one doesn't resolve, ask for the path. Echo the resolved list back once — that set is reused for every issue this session.
4. `mkdir -p ~/.claude/plans/<YYYY-MM-DD>` and create `~/.claude/plans/<YYYY-MM-DD>/ivtg-<title-slug>.md` using the template below. Never write at the plans root.
5. Report the plan file path, then say you're ready for issue 1.

## Phase 1 — per issue

The user pastes an issue. Immediately:

1. Append a stub section to the plan file: `## Issue N — <one-line title>`, `**Status:** investigating`, the issue text verbatim.
2. Launch **one background Opus agent** (`Agent`, `model: "opus"`, `run_in_background: true`) with the investigator contract below.
3. Tell the user the issue is queued and take the next one. Issue N+1's pipeline runs while issue N is still investigating.

## Phase 2 — codex review

When the investigator returns:

1. Write its findings into that issue's section (Investigation + Fix plan). Set `**Status:** in review`.
2. Run codex in the background:

```bash
codex exec -C <repo1> --add-dir <repo2> -m gpt-5.6-sol \
  -c model_reasoning_effort="high" --sandbox read-only \
  -o <scratch>/ivtg-issue-<N>-review.md - <<'PROMPT'
Review this fix plan against the actual code in the repos you can read.
Do not write code. Do not edit files.

First line of your reply must be exactly: VERDICT: clean  — or —  VERDICT: <N> blockers
Then, numbered, each blocker: what is wrong, the file:line evidence, what the plan should say instead.
Then non-blocking notes, if any.

<issue text and the fix plan verbatim>
PROMPT
```

3. Append the verdict file's contents verbatim under `### Codex review`.

## Phase 3 — one revision, then stop

- **Clean verdict:** set `**Status:** ready — awaiting go`. Done.
- **Blockers:** send the blockers back to the same investigator via `SendMessage` (its context is intact; only spawn a fresh agent if that fails). It returns a revised fix plan only. Replace the fix plan with the revision, keep the original under `### Superseded plan`, set `**Status:** ready (revised) — awaiting go`.

Then stop. Report to the user: issue number, one-line root cause, verdict (clean / N blockers, revised), plan file path. Do not start implementing, do not offer to start.

## Phase 4 — demuddy on completion

When the plan file is complete — the user says they're out of issues, or every issue has reached a `ready` status and they've signalled they're done — invoke `/demuddy` on it. Always. A file built one issue at a time, each with a superseded plan and a review verdict stacked under it, is exactly the decision archaeology demuddy exists to strip.

Run it once, on the whole file, not per issue: an issue's section is not final until its revision pass has landed.

Preserve through the pass: every `<repo>/<file>:<line>` cite, every gotcha and open unknown, each issue's `**Status:**` line, and the repo list. Codex verdicts and superseded plans are archaeology and may go.

Report the demuddied path. This is still a plan — no code.

## Investigator agent contract

Give the agent: absolute repo paths, the issue text verbatim, and this output shape. Its reply must be these sections, in this order:

1. **Symptom** — one line.
2. **Root cause** — every claim carries a `<repo>/<file>:<line>` cite.
3. **Evidence** — what was read or traced to prove it.
4. **Fix plan** — numbered steps; each names the file, the change, and why.
5. **Blast radius** — other call sites, forks, or shared files the change reaches.
6. **Risks & unknowns** — anything not verified. Say "unknown", never guess.
7. **Verification** — commands to run and what output proves it fixed.

Mandate in the prompt: read-only, no edits, no commits, no running of destructive commands.

## Plan file template

```markdown
# ivtg — <session title>

Date: <YYYY-MM-DD>
Repos:
- <name> — <abs path>

## Index
1. <issue title> — <status>

---

## Issue 1 — <title>

**Status:** investigating
**Reported:**
> <user's text, verbatim>

### Investigation
### Fix plan
### Codex review (gpt-5.6-sol, high)
```

## Rules

| Rule | Why |
|---|---|
| Only the main thread writes the plan file | Parallel issues would clobber each other's edits |
| Agents are read-only | An investigation that edits code has pre-empted the user's go/no-go |
| Plan file is never `git add`ed or committed | It lives in the vault; repos stay clean |
| Repo set is asked once, at session start | Ask again per issue and the session turns into an interview |
| One revision pass maximum | Second round means the investigation was wrong, not the plan — say so instead of looping |
| `/demuddy` runs once, on the finished file | Per-issue passes would rewrite sections that a later revision still changes |

## Red flags — stop

- "This fix is one line, I'll just apply it" — no. The deliverable is a plan.
- "Codex found blockers, let me fix the code" — revise the plan, not the code.
- "Obvious which repo this is, no need to ask" — the resolved repo set is the only source.
- "I'll write today's date from context" — run `date +%F`.
- Third revision round — stop and tell the user the investigation needs redoing.
- "Last issue is ready, session's done" — not until `/demuddy` has run on the file.
