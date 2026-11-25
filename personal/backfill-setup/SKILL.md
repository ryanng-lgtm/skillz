---
name: backfill-setup
description: >-
  Use when a backend table or continuous aggregate needs history it does not
  hold yet: rows to fetch from a venue or vendor API, a coarser cagg tier to
  build from a finer one (30m from 1m), a gap to fill on one or more ore or
  cme databases, or a long load that has to report its progress in OM Chat
  and keep an eye on the hosts while it runs. Trigger: /backfill-setup
  [plan path], "set up the backfill", "backfill X from Y", "build the 30m
  history", "load the history into staging".
---

# backfill-setup — staged, resumable backfills with progress in OM Chat

## Overview

A backfill is long, touches production databases, and fails halfway at
least once. This skill sets one up so that every unit of work is small,
recorded and safe to rerun, the rows land in staging before anything
users read, the progress is one OM Chat message edited in place, and the
hosts are checked every hour.

The worked example is `ore-trade-30m/backfill.sh` in the `tsdb-scripts`
repo (with its `README.md`): staging caggs that fold 1m to 30m, a monthly
fill, a check against 15m, a load by tsdb-move, a verify, a history floor,
and an expose step. Read it before writing a new job.

**Core principle: users never see a partial history. Rows go to staging
first, are checked there, and reach the real table and its watermark only
in later steps, each behind its own gate.**

## Procedure

### 1. Write down the job

Put these in the plan (`~/.claude/plans/<date>/<job>.md`) before any code:

| Field | What to record |
| --- | --- |
| Target | The real table or cagg, and what reads it (reader, API, jobs). |
| Source | A venue or vendor API, or a finer cagg tier. Its coverage: from when it holds data, its retention, gaps known. |
| Staging | A separate table or cagg per target, never the target itself. Name it so `\d` shows it is staging (`backfill_<source>_<target>`). |
| Units | The smallest piece that can be run, checked and rerun alone: one tier per time window (a calendar month for a cagg refresh, a day for an API fetch). Their order: oldest first. |
| Cut | Where loaded rows end and normally refreshed rows begin, a UTC time. Written once and never changed. |
| Databases | Every database the job runs on, and the order. |
| Steps after the fill | check, load, verify, floor, expose, cleanup, each with its gate (step 7). |

### 2. Preflight, read-only

With Ryan's go for prod reads in this request (they are short, one
statement per psql, never a held transaction):

- Free disk per host against the expected size (staging plus the load, with
  room left). Stop and ask when it is close.
- The target tier's retention and every job that can refresh, compress or
  drop it (refresh cjobs' include and exclude patterns, the compress skip
  list, the drop job). A drop or refresh during the load moves the
  watermark over a partial history. Retention goes to null for the load in
  an MR merged and synced before step 5.
- The target's watermark and its `cagg_history_floor` rows.
- The source's coverage over the whole range: a finer tier whose retention
  is shorter than the range cannot build the oldest units.
- The cagg definitions of staging and target match column for column.

### 3. Build the runner

Write the units file (tab separated: `group`, `unit`, `mode`, `statement`)
with a small generator, one line per unit; `mode` is `read`, `write` or
`cmd`. Then run it with the bundled runner, or copy the runner into the job's
repo folder when the job needs more commands (create, check, verify, expose)
the way the worked example does:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/runner.sh run    --host <host> --job <job> --units units.tsv --dry-run
bash ${CLAUDE_SKILL_DIR}/scripts/runner.sh run    --host <host> --job <job> --units units.tsv
bash ${CLAUDE_SKILL_DIR}/scripts/runner.sh status --host <host> --job <job> --units units.tsv
```

The runner opens one psql connection per unit with `application_name`
`runner-<job>`, sets `lock_timeout` and `statement_timeout` through
`PGOPTIONS`, waits before a write until no earlier backend of the job runs
the same statement, never retries a write, retries a read whose connection
dropped, logs every unit, and records finished units in
`state/<host>.<job>.json` so a rerun continues. `--help` lists its
environment variables. Under Codex the script path is relative to this
SKILL.md's folder.

Every write unit must be idempotent: a refresh of a window, an
`INSERT … ON CONFLICT`, a `DELETE` then `INSERT` in one statement. A unit
that is not cannot be rerun after a dropped connection.

### 4. Rehearse

REQUIRED SUB-SKILL: shared-dev, against a scratch copy. Run two units, kill
the client in the middle of a write, rerun, and confirm the runner waits for
the old backend and the state file is right. Run the check (step 7) on the
rehearsal data.

### 5. Start the fill

- Per database, only with Ryan's go for that database: start the runner
  with `run_in_background`, one database at a time unless Ryan says to run
  them together. The background task's completion and its `UNIT DONE`,
  `GROUP DONE` and `UNIT FAILED` lines are the reports.
- An unattended run (overnight) needs a runbook in the plan's evidence
  folder: start condition, order, what to do on each failure, and what
  stops it.

### 6. Report while it runs

- **Progress message.** Post one message in the work's OM Chat topic with
  the agent badge and edit it in place after each finished group (at most
  every 10 minutes). Build its text from the state files:

  ```bash
  bash ${CLAUDE_SKILL_DIR}/scripts/runner.sh status --host <host> --job <job> --units units.tsv |
    awk -F'\t' -v OFS='\t' '{print "tsdb3 " $1, $2, $3, $4}' |
    bash ${CLAUDE_SKILL_DIR}/scripts/progress.sh "<job>, load progress"
  ```

  It prints a title and a fenced `progress` block, one line per row:
  `name: done/total | note`. When a database is finished, its note says
  what was verified and when, e.g. `loaded and verified 22:51 UTC Nov 24`.
  Edit only messages the badge posted; a checklist that belongs to Ryan
  gets a line in the session saying which step to tick.
- **Hourly host check**, reported in the session as one line per host:

  ```bash
  bash ${CLAUDE_SKILL_DIR}/scripts/grafana-health.sh --instance timescaledb-3 --instance timescaledb-1 --every 3600
  ```

  It reads Grafana with `~/.grafana_token` (query path only) and prints
  memory available, deadlocks in the last hour, free space on the largest
  filesystem and disk IO, then `OK` or the flags that tripped. On a flag:
  start no new unit, finish the one running, and tell Ryan. cme databases
  take `--datasource P936145AD0657F27E`.

### 7. After the fill, one gated step at a time

| Step | Gate before it | Check after it |
| --- | --- | --- |
| check | the fill finished on that database | staging equals the source over the range the source still holds; no duplicate keys; rows in every unit; a reference series has a row in every bucket. Differences are accepted only through an exceptions file Ryan agreed to. |
| load into the target | check passed on that database; retention null deployed and checked; Ryan's go | the target's watermark is still unset; a read 300 days back through the reader returns nothing yet. |
| verify | the load finished | row count and a hash of every column equal staging, one unit per statement; write a receipt. |
| floor | verify passed on every database | one `cagg_history_floor` row per target at the cut, read back. |
| indexes | the floor is written | every index of the target valid on every chunk. |
| expose | all of the above on every database; Ryan present | the first statement (one bucket at the cut) on every database back to back; the watermark past the cut; the seam around the cut has no gap; cache keys of the affected types cleared or left to expire, as Ryan decides. |
| cleanup | expose checked | retention back on with the watermark unchanged; staging dropped only on Ryan's word; the job's load entries removed from tsdb-move. |

Write each step's result into the plan with its UTC time.

## Rules

- **Prod writes need Ryan's explicit go per database**, in the current
  request. A go for one database or one step does not cover the next.
- **Prod reads are short**: one statement per psql, a `statement_timeout`,
  no cursors or open transactions, no unbounded scans.
- **Never print or read credentials**: no `~/.pgpass`, `~/.pg_service.conf`,
  `connections.env` or token contents; never a database URL on a command
  line. psql reads `~/.pgpass` by itself.
- **Never run `refresh_continuous_aggregate` by hand on a real view.** A
  refresh below the cut recomputes from the source tier and deletes loaded
  rows wherever the source no longer holds them. Only the expose step
  refreshes a real view, from the cut upward.
- **A real cagg's watermark may only be set when every row below it is
  stored.** The reader serves stored rows below the watermark, and a cache
  can keep a partial answer for 24 hours.
- **No `TRUNCATE` or `DROP` without Ryan**, staging included.
- **One rehearsal on shared-dev before the first prod run**, and none of its
  writes in `public`.

## Common mistakes

- **Leaving retention on during the load.** A drop run moves the watermark
  up to the rows already stored and serves the partial history. Retention
  null is deployed and checked before the first load.
- **Retrying a write after a dropped connection.** The old backend can still
  be running and commit. Wait for it in `pg_stat_activity` first, as the
  runner does.
- **Reading an exit code through a pipe.** `cmd | tail` returns `tail`'s
  status, and `$PIPESTATUS` read after `|| break` is empty. Capture the
  command's own status.
- **Trusting TimescaleDB catalog tables across versions.** 2.30 has no
  `_timescaledb_catalog.chunk_index`, and chunk index names are cut at 63
  characters. Match chunk indexes by their key columns (the argocd skill's
  `references/backend.md` has the query).
- **Editing the wrong status message.** Keep the progress message's link in
  the plan, and edit only messages the badge posted.
- **Exposing one database at a time over hours.** Readers move between
  databases, so a user sees the history on one request and not the next.
  Run the first expose statement on every database back to back.
