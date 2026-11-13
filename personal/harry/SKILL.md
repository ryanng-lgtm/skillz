---
name: harry
description: >-
  Use when MRs Ryan opened or pushed have landed on GitLab and need the review
  Harry (harry208) would give, before Harry sees them. Trigger: /harry [MR ...]
  [--model MODEL], "review this like Harry", "assume you are Harry", "what
  would Harry say about this MR".
---

# harry — review landed MRs as Harry, fix what is real

## Overview

Harry (`harry208` on GitLab, `@harrychiew` in OM Chat) reviews the go-backend
repos and kiyotaka-toolkit. Before he asks whether the code is right, he asks
whether it is the right change: whether it reaches the problem it names,
whether it should have extended something that already exists, and what each
moving part buys. This skill gives each MR that review first, through the
panos skill's pipeline with Harry's brief.

**Core principle: a reviewer finding is a hypothesis; never fix one Phase 3 has not reproduced.**

## Procedure

**REQUIRED:** read `~/.claude/skills/panos/SKILL.md` and run its Phases 0–6,
Rules and Common mistakes, with these changes.

1. **Past reviews**, started in the background during Phase 0:

   ```bash
   python3 -I ~/.claude/skills/harry/scripts/reviews.py ~/.cache/harry/reviews.md
   ```

   It reuses a file younger than 7 days. A rebuild reads Harry's GitLab
   threads and his #go-tasks posts and takes a few minutes. When it fails,
   leave the "Your past reviews" line out of the prompt and say so in the
   report. The file holds teammates' words and internal links: never copy it
   into the skillz repo, which is public.
2. **The prompt** is `references/harry.md`, then the panos "This MR" block
   with two more lines right after "Deliberately temporary", then the panos
   skill's `references/contract.md`:

   ```
   Your past reviews: <$HOME>/.cache/harry/reviews.md
   Walk file: <run dir>/walk-<name>.md
   ```

3. **Names.** `harry` replaces `panos` in the run dir
   (`<evidence dir or scratchpad>/harry/<YYYY-MM-DD-HHMM>/`) and in probe file
   names (`zz_harry_probe_*`), including the Claude reviewer's prompt.
4. **Phase 3, design findings.** A finding about a duplicated rule, a moving
   part that buys nothing, a misleading comment or a test that would pass on
   the old code is verified by reading the code it cites: real when the code
   shows it, with no failing test needed. A finding that the MR should keep
   only part, be reworked on another path, or be closed is a design change.
   It goes to Ryan with the alternative the reviewer named, and Phase 4 fixes
   nothing else in that MR until Ryan decides.
5. **The report** names Harry as the review lens and links each MR's walk
   file.

## Refreshing the brief

`references/harry.md` holds Harry's review questions as patterns, never his
words or the details of the MRs they came from. After Harry has reviewed new
MRs, rebuild the past reviews with `--max-age-days 0` and fold any new lens
into the brief the same way: no names, numbers, links or identifiers from the
source.

## Common mistakes

- **Leaving out the walk file.** Without a written answer to each question,
  the reviewer drifts back to a bug hunt and stops at the one or two findings
  it can prove with a probe, missing the comments, hygiene, ownership and
  rollout points Harry raises.
- **Fixing toward a rework.** When the reviewer says the MR should be built
  on an existing path, patching the current approach is wasted work. Ryan
  decides first.
