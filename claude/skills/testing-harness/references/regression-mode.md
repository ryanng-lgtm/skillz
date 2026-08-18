# `--regression` — design of record

Status: **designed, not built.** This file is the contract to build against. It
is the carry artifact — the skill directory does not sync between machines, this
design does (a copy lives in `~/.claude/plans/2026-08-18/`).

## The question the mode answers

`--parity-check` asks *did my intended visual change land, and only where I meant
it to*, by diffing cloud against the local daemon. It says nothing about what
else moved.

`--regression` asks *did anything else quietly break*. It is behavioral, targeted
at the latest changes, and run against one target — the local daemon serving the
branch — rather than across two.

## Settled decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Baseline source | recorded on disk, `--record` on `main`, replay on the branch | one daemon alive at a time |
| Two live daemons | rejected | two `om` daemons sharing an `OM_HOME` share one database and one credential store; isolating a second home plus a second build costs more than a stored baseline |
| Assertions-only, no baseline | rejected | cannot catch silent drift nobody wrote an assertion for, which is most of what a regression run is for |
| CLI shape | `check --parity-check \| --regression`, exactly one mode required | `compare` stays as a silent alias for `check --parity-check` |
| Doctor gate | applies to both modes | a clean verdict against the wrong daemon is worse than no verdict |

## The four legs

All four write into one run artifact. Each is independently runnable so a fast
run can skip the expensive ones.

### 1. Runtime health sweep

Walk a route list against one target and fail on any of:

- a `console.error`, or any console message matching the configured error patterns
- an uncaught `pageerror`
- a network request that failed, 4xx'd, or 5xx'd
- a websocket that closed without a reconnect inside the grace window
- a stub or blank render — `STUB_MARKER` present, or `#root` with no children

Needs no baseline, so it is the cheapest leg and the right one to build first.
Its output shape forces the artifact layout into existence.

### 2. Critical journeys

A fixed, hand-written suite against the real daemon. Starting set:

- app hydrates and the rooms list populates
- open a DM, history renders
- send a message and confirm it rendered (the existing `send` verb's assertion)
- reload — the view survives and the message is still there
- `context.setOffline(true)` then back — the websocket reconnects and backfills

Governed by the journey rules in `SKILL.md`: assert the observable not the
action, cross a real boundary, and use cloud as the control before calling
anything a regression.

### 3. Self-baseline diff

`--record` on `main` writes a baseline; a later run on the branch replays the
identical steps and diffs against it. Diffed dimensions: screenshots per route,
DOM fingerprints, the network log, the console log.

Staleness is the known weakness. Rules:

- a baseline is stamped with branch, sha, and time
- a run warns loudly when its baseline is behind `main`, and names how far
- a baseline recorded against a dirty tree is marked dirty and never silently
  reused

### 4. Change-driven targeting

Read the branch's diff against `main`, map touched components and routes onto
which routes to sweep and which journeys to run, and skip the rest. Keeps a run
fast and pointed at the latest changes. Falls back to the full set when the
mapping is uncertain — under-running is the dangerous direction.

## Network and console are scraped on every leg

Not just the sweep. The request log and the console log are part of the run
artifact for journeys and baseline replays too, so a journey that passes while
quietly firing a 500 is still a finding.

Injecting temporary debug logging into the page to capture data no selector
exposes is a supported technique, not a hack — via `page.addInitScript` or an
`evaluate` shim. Rules: it is added by the harness, never committed into the GUI
source, and the run artifact records that it was injected so a log line is never
mistaken for something the product emitted.

## Artifact layout

Baselines and runs share one shape, so replay is a directory comparison.

```
~/.claude/state/testing-harness/
  baselines/<branch>@<sha>/
    meta.json        branch, sha, dirty flag, recorded-at, route list, harness version
    shots/<route>.png
    dom.json         per-route DOM fingerprints
    network.jsonl    one request per line: method, url, status, timing
    console.jsonl    one message per line: type, text, location
  runs/<timestamp>/
    ...the same four, plus:
    verdict.json     per-leg pass/fail, findings, the baseline compared against
```

`verdict.json` is the machine-readable result; the human surface is a report in
the same spirit as the parity-check HTML.

## Open questions for the next session

- Which routes make the default sweep list, and does it come from a config file
  or from the route table in the GUI source?
- Journey suite location: hand-written inside `om-chat.mjs`, or discovered from a
  directory of journey files the way the visual suite discovers `*.visual.ts`?
- DOM fingerprint granularity — full serialized tree is too noisy to diff, tag +
  `data-*` + text-length per node is probably the right resolution, but this is
  untested.
- Exit code contract: does a failing regression run exit non-zero (CI-shaped) or
  always exit 0 and report (report-shaped)?
- Does `--regression` ever run against cloud, or is cloud strictly the control
  for a suspected regression?

## Do not

- Report a regression verdict from this skill before the mode exists. Use an
  ad-hoc probe and say it was a probe.
- Duplicate the GUI repo's fixture-based visual suite. Anything that would pass
  against a static fixture belongs in `openmarket-chat`, not here.
- Let a leg post, react, or delete against the production backend without the
  same approval the `send` verb requires.
