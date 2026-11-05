---
name: ivtg
description: >-
  Use when the user wants to queue up bugs, regressions, or issues one at a time
  and get each one investigated across one or more repos and written up as a fix
  plan to approve before any code is touched. Trigger: /ivtg, $ivtg, "investigator
  mode", "investigate these issues", "plan fixes, don't implement".
---

# ivtg — issues in, reviewed fix plans out

## Overview

The user feeds issues one at a time. Each issue gets investigated by a background subagent, reviewed by a second model, and written into one shared plan file, which the demuddy skill cleans up once the session ends. Implementation happens only when the user says so, in a later turn, outside this skill.

Repo-agnostic: every repo path comes from the user at session start, never from the current working directory alone.

**Core principle: the terminal state of this skill is a written plan. No code is ever changed here.**

## Phase 0 — session open (once)

1. Run `date +%F` for today's date. Never guess it.
2. Read the `Plans folder` setting: a `- Plans folder: <path>` line under `## Skill settings` in the user's global instructions (`~/.claude/CLAUDE.md` in Claude Code, `~/.codex/AGENTS.md` in Codex).
3. Ask the user, in one message: session title, which repos to scan (names or paths), and, when the setting is missing, which folder plans go in, offering to add the `Plans folder` line.
4. Resolve each repo to an absolute path (`ls -d`). If one doesn't resolve, ask for the path. Echo the resolved list back once — that set is reused for every issue this session.
5. Create `<Plans folder>/<YYYY-MM-DD>/ivtg-<title-slug>.md` from the template below, making the dated folder first. Expand a leading `~` to `$HOME` and quote the path in commands, since it may contain spaces. Never write at the plans folder's root.
6. Report the plan file path, then say you're ready for issue 1.

## Phase 1 — per issue

The user pastes an issue. Immediately:

1. Append a stub section to the plan file: `## Issue N — <one-line title>`, `**Status:** investigating`, the issue text verbatim.
2. Launch **one background subagent** on the strongest model available (in Claude Code: `Agent`, `model: "opus"`, `run_in_background: true`) with the investigator contract below. When the agent can't start subagents, investigate the issue yourself to the same contract before taking the next one.
3. Tell the user the issue is queued and take the next one. Issue N+1's pipeline runs while issue N is still investigating.

## Phase 2 — second review

When the investigator returns:

1. Write its findings into that issue's section (Investigation + Fix plan). Set `**Status:** in review`.
2. Once per session, create a working directory with `mktemp -d "<parent>/ivtg.XXXXXX"`, where `<parent>` is this session's scratchpad directory, else `${TMPDIR:-/tmp}`. `<scratch>` below is the path it prints. Write the review prompt to `<scratch>/ivtg-issue-<N>-prompt.md`:

```text
Review this fix plan against the actual code in the repos you can read.
Do not write code. Do not edit files.

First line of your reply must be exactly: VERDICT: clean  — or —  VERDICT: <N> blockers
Then, numbered, each blocker: what is wrong, the file:line evidence, what the plan should say instead.
Then non-blocking notes, if any.

<issue text and the fix plan verbatim>
```

3. Send it, read-only, to the first reviewer on this list the session has. Run a CLI or subagent reviewer in the background. The review never waits on the user and is never skipped.
   1. **The other agent's CLI.** In Claude Code, `codex` when it is on `PATH`, with its configured model: the `model =` line of `~/.codex/config.toml`, which goes in the review heading. In Codex, `claude` when it is on `PATH`.
   2. **A subagent on a different model** from the investigator's.
   3. **A fresh subagent on the same model** that never saw the plan being written, so never the investigator.
   4. **When the agent can't start subagents, a separate self-review pass**: answer the prompt yourself against the code, as if someone else wrote the plan.

   Reviewers 3 and 4 are weaker: mark them so in the review heading and in the report to the user.

```bash
# codex, from Claude Code
awk -F'"' '/^\[/{exit} /^model *=/{print $2; exit}' ~/.codex/config.toml
codex exec -C <repo1> --add-dir <repo2> -c model_reasoning_effort="high" \
  --sandbox read-only -o <scratch>/ivtg-issue-<N>-review.md - < <scratch>/ivtg-issue-<N>-prompt.md

# claude, from Codex
cd <repo1> && claude -p --permission-mode plan --add-dir <repo2> \
  < <scratch>/ivtg-issue-<N>-prompt.md > <scratch>/ivtg-issue-<N>-review.md
```

4. Append the reviewer's reply verbatim under `### Review (<reviewer>, <model>)`, e.g. `codex, <model from config>` or `fresh subagent, same model — weaker`.

## Phase 3 — one revision, then stop

- **Clean verdict:** set `**Status:** ready — awaiting go`. Done.
- **Blockers:** send the blockers back to the same investigator, whose context is intact (in Claude Code, `SendMessage`; spawn a fresh agent only if that fails), or revise the plan yourself if you investigated the issue yourself. The revision is a fix plan only. Replace the fix plan with the revision, keep the original under `### Superseded plan`, set `**Status:** ready (revised) — awaiting go`.

Then stop. Report to the user: issue number, one-line root cause, verdict (clean / N blockers, revised), plan file path. Do not start implementing, do not offer to start.

## Phase 4 — demuddy on completion

When the plan file is complete — the user says they're out of issues, or every issue has reached a `ready` status and they've signalled they're done — run the demuddy skill on it. Always. A file built one issue at a time, each with a superseded plan and a review verdict stacked under it, is exactly the decision archaeology demuddy exists to strip.

Run it once, on the whole file, not per issue: an issue's section is not final until its revision pass has landed.

Preserve through the pass: each issue's **Reported** text verbatim, every `<repo>/<file>:<line>` cite, every gotcha and open unknown, each issue's `**Status:**` line, and the repo list. The Reported text is what the closing summary of a later run recaps the issues from. Review verdicts and superseded plans are archaeology and may go.

Report the demuddied path and the index: per issue, its number, title, one-line root cause and status. This is still a plan — no code.

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
### Review (<reviewer>, <model>)
```

## Rules

| Rule | Why |
|---|---|
| Only the main thread writes the plan file | Parallel issues would clobber each other's edits |
| Agents are read-only | An investigation that edits code has pre-empted the user's go/no-go |
| Plan file is never `git add`ed or committed | It lives in the plans folder; repos stay clean |
| Repo set is asked once, at session start | Ask again per issue and the session turns into an interview |
| One revision pass maximum | Second round means the investigation was wrong, not the plan — say so instead of looping |
| demuddy runs once, on the finished file | Per-issue passes would rewrite sections that a later revision still changes |

### Stop signs

- "This fix is one line, I'll just apply it" — no. The deliverable is a plan.
- "The review found blockers, let me fix the code" — revise the plan, not the code.
- "Obvious which repo this is, no need to ask" — the resolved repo set is the only source.
- "I'll write today's date from context" — run `date +%F`.
- Third revision round — stop and tell the user the investigation needs redoing.
- "Last issue is ready, session's done" — not until demuddy has run on the file.
