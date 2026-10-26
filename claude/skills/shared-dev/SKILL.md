---
name: shared-dev
description: Use when a backend change (tsdb-gateway, metadata-instrument, streamd, stream-deduplicated, live-feed, kiyotaka-go, replayer) has to be tested locally against real data — "let's test this locally", "spin up shared-dev", "probe this end to end", "check it against the clones", "pull more data from prod for this probe" — or a shared-dev run has to be torn down, or public on the dev tsdb brought up to main. Trigger: /shared-dev [repo ...] [--fe] [--keep] | /shared-dev down | /shared-dev rebaseline.
---

# shared-dev — run the change against real data, probe it, tear down

## Overview

Takes the worktrees this session touched, works out the services and data
the change needs, builds the branch's binaries, brings exactly those
services up in the shared-dev Docker stack against Ryan's databases on
Sean's PC, probes, reports, and tears down. DB queries are the main
evidence; FE validation only with `--fe`.

Every command below runs as:

```bash
P=~/.config/shared-dev/.venv/bin/python
S=~/.claude/skills/shared-dev/scripts
$P -I $S/run.py <module> ...        # bash scripts: bash $S/<name>.sh
```

Facts about the bundle, Sean's PC and the repos: `references/environment.md`.
Prod clones and probes: `references/prod-access.md`.

## Hard rules

- **`public` on `data` holds prod clones and a run never changes it**: no
  writes, migrations, indexes, REFRESH or continuous aggregates. A run's
  migrations and writes land in its own `sd_<slug>` schema through the
  `sd_guard` role; `up` and the scripts enforce this. The one exception is
  `rebaseline apply --yes`, and only after Ryan approves that run.
- **Prod reads** go only through `run.py clone` (tsdb2 for tsdb data, pgmeta0
  for metadata), each with Ryan's go for that request; tsdb0–3 only when he
  names them; never in an unattended run.
- **Over 70 GB** of copies, per table or per run: stop and ask.
- **Credentials**: never read or print `connections.env`, `kcat.conf`,
  `~/.pgpass`, `~/.pg_service.conf`, `~/.config/shared-dev/config/*`,
  `<run dir>/config/*` or `state/guard.secret`, and never put a DB URL in a
  command line. Use `run.py query` for SQL.
- **Never** start `zmeta_local`, `pipeline.sh` or any local TimescaleDB; never
  run `configure.py`; never write files into `~/.config/shared-dev` yourself.
- **Never stop, restart or recreate containers this run did not claim.**
- A denied tool call or classifier block: stop and tell Ryan.
- Lint is report-only (`task lint` rewrites files).
- Tear down at the end unless `--keep`.

## Arguments

- `down [--project P]`: step 9 only.
- `rebaseline`: see "Public behind main".
- Repo names: scope only those worktrees. `--fe`: include the FE link.
  `--keep`: leave the stack up after the probes.

## 1. Scope

Run dir: if the work has a plan, `<that plan's -evidence dir>/shared-dev/<YYYY-MM-DD-HHMM>/`
(`grep -rlF '<branch>' ~/.claude/plans`); otherwise
`<scratchpad>/shared-dev/<YYYY-MM-DD-HHMM>/`. Call it `$RUN`.

```bash
$P -I $S/run.py scope <worktree> ... > $RUN/scope.json
```

The worktrees are the ones this session edited or pushed from. None: ask
once. If the branch's MR has squash-merged, keep the worktree builds when
the worktree holds the same code as what landed (`git diff origin/main` on
the changed files is empty); `tsdb-read-main` already runs main. If the
worktree is stale, set that repo's builds to `"source": "main"` in
`plan.json`.

## 2. Plan

```bash
$P -I $S/run.py plan $RUN/scope.json [--fe] > $RUN/plan.json
```

Show Ryan, in a few lines: the services and whether each runs the worktree
or main, the data source (`clones`, `api`, `live`), migrations, the capture
venue, and unmapped files that matter at runtime (chart values, configs),
marked "not exercised locally". Live capture needs symbols: the branch's
own, else two or three liquid ones on the venue. If the branch adds config
keys (a new feature block), write them, without secrets, to a JSON file per
service for `up --patch`. If `need_mib` is over Docker's memory, drop
services the change does not need from `plan.json` and say so.

## 3. Preflight

```bash
bash $S/preflight.sh --need-mib <plan.json need_mib> [--prod]
```

Any `FAIL` stops the run; report the line. A Tailscale move is reported
with the new IP, never fixed by editing configs.

## 4. Up

```bash
$P -I $S/run.py up --scope $RUN/scope.json --plan $RUN/plan.json --run-dir $RUN \
  --session <this session's id, else the run dir's name> \
  [--venue V --symbols A,B --seconds 180] [--patch SERVICE=FILE ...]
```

It claims the project, builds, creates `sd_<slug>` with the copies the
branch's migrations need, applies them as `sd_guard`, migrates `meta_ryan`
when the plan says so, writes `$RUN/compose.json`, starts the services, and
writes `$RUN/up.json` (project, port offset, schema, copies, warnings,
index gaps). When it stops:

| Exit | Means | Do |
|---|---|---|
| 3 | containers running with no claim | show `docker ps --filter label=com.docker.compose.project=<p>`; ask Ryan |
| 4 | a copy over 70 GB | show the size; after his yes, re-run with `--confirm-size` |
| 5 | `public` is behind main | "Public behind main" below; with Ryan's OK re-run with `--allow-behind` |
| 6 | capture needs `--venue`/`--symbols` | pick them, re-run |
| 7 | `plan.json` is inconsistent | fix the plan, re-run |
| 8 | the project's previous run (a dead session's, or this session's own) did not tear down | show the leftovers; ask Ryan |
| other | read the error | `stack down --run-dir $RUN` before retrying |

A second session gets its own project (`kiyotaka-shared-dev-<slug>`, host
ports +20000, Kafka prefix `dev.ryan.<slug>.`); `up.json` says which. A
claim whose containers are gone (a dead session), or this session's own
earlier run, is torn down by `up` before it claims again.

## 5. Data in

- **Clones**: nothing to do; readers see `sd_<slug>` first, then `public`.
- **API and catalog**: metadata-instrument fetched the catalog on start.
  Cjobs: `$P -I $S/run.py stack run-once --compose $RUN/compose.json --project <p> -- cjob ...`
- **Live capture**: `$P -I $S/run.py stack up --compose $RUN/compose.json --project <p> streamd-<venue>`,
  then `docker wait <p>-streamd-<venue>-1` (it stops itself). Check
  `docker compose -p <p> logs tsdb-write` for `permission denied`: a table
  the writer needed was not copied; report it rather than working around it.
  A topic the run needs (a dedup IDs topic, say) is created under the run's
  prefix and deleted by teardown:
  `$P -I $S/run.py topics create --project <p> <prefix><name> --like <prefix>normalized --config retention.ms=…`.
  Restarting a service of this run to pick up a change:
  `docker compose -p <p> -f $RUN/compose.json up -d --no-deps --force-recreate <service>`.

## 6. Probe

```bash
$P -I $S/run.py query --schema <schema> -c "SELECT ..."          # as sd_guard, run's search_path
$P -I $S/run.py scratch coverage --schema <schema> <table> ...
$P -I $S/run.py api --port <4084+offset> "/v1/..."                # tsdb-api with the dev key
```

- **Main against branch**: when `up.json` has `main_reader`, every reader
  probe goes to both `tsdb-read` (branch) and `tsdb-read-main` (host ports
  +100), and the report shows them side by side.
- **Deploy-order check** when the branch changes migrations or views: the
  main reader against the branch's schema.
- **Performance**: `EXPLAIN (ANALYZE, BUFFERS)` main against branch, same
  machine, same data, through
  `$P -I $S/run.py query --as dev --io-timing -c "EXPLAIN (ANALYZE, BUFFERS) …"`
  (`track_io_timing` for that session only). Coverage first: a working set
  smaller than memory means I/O-wait numbers say nothing; say so, and offer
  a prod clone.
- **Correctness**: recompute the value with an independent query; metrics
  endpoints count too.
- **Too thin**: `references/prod-access.md`.

## 7. FE link (`--fe` only)

Ryan's FE stack (kiyo-fe, tharamine, orange, auth, orange-shared) runs in
his terminals; never restart it. Find which one holds the tsdb-gateway
address (their env and config files: names only, never values), tell him
the change and which process to restart to point it at local tsdb-api or
tsdb-read (host ports in `up.json`), then confirm the requests reach the
local gateway in its logs.

## 8. Report

`$RUN/report.md`, and the same in chat:

- What ran: each service with its binary (worktree and commit, main commit,
  or bundled) and host ports.
- Data: `scratch coverage` per table (clone, copy, slice or empty; rows,
  range, chunks); rows landed per table and symbol for a capture.
- Evidence: each probe, its query and output; main against branch.
- Warnings from `up.json`: destructive branch migrations (they ran on
  copies), index gaps against main, files not exercised locally.

## 9. Teardown

```bash
$P -I $S/run.py stack down --run-dir $RUN
```

It stops the project, drops the run's schemas, deletes the topics it
created, rolls `meta_ryan` back to main, deletes the run's configs and
releases the claim. It refuses a run another session claimed; `--force`
only when Ryan says so. Report every `leftover:` line. With `--keep`, skip
this and give Ryan that command.

## Public behind main

`public` is never migrated by a run, so it falls behind main. `up` exits 5
then. Until the catch-up is possible, Ryan may OK a run with
`--allow-behind`: `up.json`'s warnings list what main has that `public`
lacks, and the report says probes touching those objects are not valid. Show Ryan `$P -I $S/run.py rebaseline plan` (forced version,
migrations to apply, which touch `registry`) and get his go for this run,
then `$P -I $S/run.py rebaseline apply --yes --log $RUN/rebaseline.log` in
the background (it can take hours). It refuses while other sessions are
connected to `data`; find out who (`pg_stat_activity` application names,
other Claude sessions) and ask Ryan rather than stopping them. A migration
that fails with `function … does not exist` means the dev DB's
`kiyotaka_toolkit` extension is older than prod's (main's `1791976706` needs
32.x; the dev DB had 30.1.0 on 2026-10-26): that is Ryan's to upgrade.

## Common mistakes

- Running a branch migration, `REFRESH MATERIALIZED VIEW` or an `INSERT`
  against `public` "just to test" — every baseline agent did, and so did a
  real session on 2026-10-26.
- `docker compose -p kiyotaka-shared-dev stop` or `--force-recreate` on a
  stack someone else started.
- Writing `compose.<feature>.yaml`, config copies or binaries into
  `~/.config/shared-dev`.
- Overriding the prod profile's 30 s cap, or reading all four tsdb nodes.
- Leaving the stack, its schema or its topics behind.
- Sourcing `connections.env` and putting `$TIMESCALE_URL` on a command line.
