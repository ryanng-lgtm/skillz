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
| Target | The real table or cagg, and what reads it (reader, API, jobs) and how far back. A reader's bar cap limits read depth, not storage, so retention does not have to match it. |
| Source | A venue or vendor API, or a finer cagg tier. Its coverage: from when it holds data, its retention, gaps known. |
| Staging | A separate table or cagg per target, never the target itself. Name it so `\d` shows it is staging (`backfill_<source>_<target>`). |
| Units | The smallest piece that can be run, checked and rerun alone: one tier per time window (a calendar month for a cagg refresh, a day for an API fetch). Their order: oldest first. |
| Cut | Where loaded rows end and normally refreshed rows begin, a UTC time. Written once and never changed. |
| Databases | Every database the job runs on, and the order. |
| Steps after the fill | check, load, verify, floor, indexes, expose, handoff, retention back, each with its gate (step 7). |

A cagg target that keeps folding its usual source tier cannot rebuild a
loaded range once that tier has dropped it. A later repair below the cut is
a rebuild of that unit in staging and a reload, never a refresh of the real
view.

### 2. Preflight, read-only

With Ryan's go for prod reads in this request (they are short, one
statement per psql, never a held transaction):

- Free disk per host against the peak: staging, the loaded rows and the
  target's indexes together, plus the host's daily growth until staging is
  dropped. Agree a stop threshold with Ryan before the fill.
- The target tier's retention and every job that can refresh, compress or
  drop it (refresh cjobs' include and exclude patterns, the compress skip
  list, the drop job, the invalidation refresher). `drop_chunks` recomputes
  a cagg's watermark from its stored rows on every call, even when it drops
  nothing, so a drop run during the load serves the partial history. Null
  the tier's retention through an anchor of its own (nulling a shared anchor
  such as the 1h deep-history policy nulls every tier that uses it), in an
  MR merged and synced before step 5. The drop job logs nothing for a
  skipped tier: prove it from the job's dry run or from the next run's
  `drop_chunks(` lines in Loki, per database.
- How the tier is declared. A tier with a null aggregate policy is skipped
  by every refresh job, the invalidation refresher, `control cagg-refresh`
  and the index build. Setting the policy opens all of them and the compress
  job at once, so their excludes and skip entries go in the same MR. Jobs
  build their view lists from the schema's buckets, not the catalog; the
  invalidation refresher ignores every job's patterns; a skip list may match
  family names only, so read how it matches before relying on a tier name.
- The target's watermark, its chunks and its `cagg_history_floor` rows. A
  view whose watermark is unset can still hold leftover rows from an
  accidental refresh, and the next recomputed watermark serves them.
  Truncate the cagg (on Ryan's go) before loading.
- The source's coverage over the whole range: a finer tier whose retention
  is shorter than the range cannot build the oldest units.
- The source's correctness over the whole range, not only where a finer
  tier overlaps it: compare per exchange and day against a stored coarser
  tier. Old minute data can miss or double whole days. Record wrong ranges
  in a catalog in the plan's evidence folder; Ryan decides whether they load.
- Other writers to the source: tsdb-move loads by other developers, dedupes,
  backfiller repairs. A write after a unit was built leaves that unit stale.
  List them before the load and rebuild those units or accept them.
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

Units that refresh a cagg:

- Run oldest first. Below its watermark a cagg serves stored rows only, so a
  newest-first fill hides every older bar until it ends. `control
  cagg-refresh` walks newest first (and listed each view twice in a
  rehearsal): never use it for a fill.
- Put every window edge on a bucket boundary, 00:00 UTC for day windows. A
  refresh stores only the buckets wholly inside its window.
- A refresh commits in batches. A dropped unit keeps what it committed, and
  its rerun does the rest.
- The runner's guard waits for the identical statement only. A command that
  can rerun with a different window (expose) has to wait for any refresh of
  the same view, as the worked example's `expose` does.

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
- Fills, checks and loads run outside US market hours (21:00 to 14:00 UTC);
  a statement running at 14:00 UTC finishes, no new one starts. The first
  database runs alone. After it, at most one reader database and one API
  database at a time (on ore the readers use tsdb0 and tsdb1, the API tsdb2
  and tsdb3), so each keeps a database free of load.
- A run from the laptop lives as long as the session, the Mac and the VPN.
  Dropped sessions (`SSL error: unexpected eof while reading`) and resolver
  stalls under Cloudflare WARP happen several times a day; the runner
  retries reads only, and a stopped write unit waits for a rerun.
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
| check | the fill finished on that database | staging equals the source over the range the source still holds; no duplicate full key (a session whose client dropped keeps running and commits, and before TimescaleDB 2.26.3 overlapping refreshes of one view could double rows); rows in every unit; a reference series has a row in every bucket. Differences pass only inside an exceptions manifest Ryan agreed to (view, exchange, window, reason), the same file the final checks use. Databases can hold different rows for the same day, so check each one. |
| load into the target | check passed on that database; retention null deployed and checked; no source writes since its units were built; Ryan's go | the target's watermark is still unset; a direct read of a day 300 days back returns no bars while the storage table holds the rows. tsdb-move mechanics: be-deploy's `references/backend.md`. |
| verify | the load finished | row count and a hash of every column equal staging, one unit per statement; write a receipt that expose requires. |
| floor | verify passed on every database; no cagg folds the target (catalog), since a view's effective floor is the later of its own and its source's | one `cagg_history_floor` row per target at exactly the cut, read back. Earlier leaves loaded rows open to a refresh; later blocks refreshing the stretch above it. The table holds one date per family and tier, for every exchange. |
| indexes | the floor is written | every index of the target valid on every chunk. Built after the load, through the aggregate-policy MR's migrate hook or by hand first (be-deploy's `references/backend.md`); no view is exposed before its indexes are valid. |
| expose | all of the above on every database; the reference series has a bar in every bucket from the cut to now (an exchange outage stops expose's continuity check, so add manifest entries first); Ryan present | per view the first statement refreshes exactly one bucket at the cut and commits in seconds; run it on every database back to back, ordered so each consumer's pair of databases switches together (eight statements are still eight commits); the watermark at the cut plus one bucket; no gap or duplicate across the seam. Then later windows oldest first, each starting on a day the source tier still holds. A rerun trusts the database's watermark only when it equals an endpoint the script writes and the reference series is continuous up to it. |
| cache | every data change of expose is finished | the reader caches each 250-bar chunk on its own, shared by every user: 24 hours with rows, 1 hour empty. Delete the type's keys and the indicator keys built from them, again after in-flight fills have ended, or let them expire as Ryan decides. Verify with a direct, cache-bypassing read on each database, then through the reader and the API: a cache hit reaches no database. |
| handoff to the jobs | every database topped up to the last bucket the source tier holds | refresh jobs walk newest first, so at the first run the stored end must reach the start of the newest bucket it refreshes, or a gap reads as empty until a later run. After the first runs: every bucket of the last closed day, no gap at the handoff. |
| retention back | the handoff checked; on every view and database the highest stored bucket plus one bucket equals the watermark; the chunks the drop job will remove listed (it drops whole chunks) | after the first drop run: the watermark unchanged, only the listed chunks gone. With the newest stored bucket empty, `drop_chunks` pulls the watermark back. |
| cleanup | retention back checked | staging dropped only on Ryan's word; the load jobs removed from tsdb-move; temporary skip and exclude entries removed. |

Way back. Until expose, `TRUNCATE` on the real cagg (its storage table
refuses it) returns the watermark to unset and users to what they saw
before; after the floor and the aggregate-policy MR, also delete the floor
rows and revert the MRs in reverse order; after expose, also delete the
cache keys and reset the state files.

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
  view created `WITH NO DATA` keeps everything below its first refreshed
  window marked as changed, so a refresh there, forced or not, recomputes
  from the source tier and deletes loaded rows wherever the source no longer
  holds them. Only the expose step refreshes a real view, from the cut
  upward. The history floor does not stop a direct SQL refresh, `--force`,
  tsdb-move, retention or the OPRA drop.
- **A real cagg's watermark may only be set when every row below it is
  stored.** The view serves stored rows below the watermark and folds the
  source tier above it, so a watermark over partial storage is a chart gap,
  and the reader's cache can keep it for 24 hours. Its movers: a refresh, a
  `drop_chunks` call (any retention run on the tier), and leftover rows that
  either of those exposes.
- **No `TRUNCATE` or `DROP` without Ryan**, staging included.
- **One rehearsal on shared-dev before the first prod run**, and none of its
  writes in `public`.

## Common mistakes

- **Leaving retention on during the load.** A drop run moves the watermark
  up to the rows already stored and serves the partial history. Retention
  null is deployed and checked before the first load.
- **Restoring retention or handing over to the jobs early.** Both move the
  watermark. Retention comes back last, after the handoff, behind its gate.
- **Checking staging only against the finer tier.** That covers the finer
  tier's retention window and says nothing about older ranges.
- **Trusting a shared-dev rehearsal for catalog or watermark behaviour.**
  shared-dev's TimescaleDB is older than prod's (see the shared-dev skill's
  report section).
- **Retrying a write after a dropped connection.** The old backend can still
  be running and commit. Wait for it in `pg_stat_activity` first, as the
  runner does.
- **Reading an exit code through a pipe.** `cmd | tail` returns `tail`'s
  status, and `$PIPESTATUS` read after `|| break` is empty. Capture the
  command's own status.
- **Trusting TimescaleDB catalog tables across versions.** 2.30 has no
  `_timescaledb_catalog.chunk_index`, and chunk index names are cut at 63
  characters. Match chunk indexes by their key columns (the be-deploy skill's
  `references/backend.md` has the query).
- **Editing the wrong status message.** Keep the progress message's link in
  the plan, and edit only messages the badge posted.
- **Exposing one database at a time over hours.** Readers move between
  databases, so a user sees the history on one request and not the next.
  Run the first expose statement on every database back to back.
