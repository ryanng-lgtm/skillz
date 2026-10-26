# Prod access: clones and probes

The rule over everything here: prod connections are short and light, so live
queries never notice them. Every prod read needs Ryan's go for that request.

## Profiles

From the GO Backend vault (`psql-investigation/`), installed as
`~/.pg_service.conf` with passwords in `~/.pgpass`; never read or print either.

- `service=tsdb2`: `timescaledb-2.int.ore.kiyotaka.ai`, db `data`, user `tsdb`, ore plane.
- `service=pgmeta0`: `postgres-0.int.ore.kiyotaka.ai`, db `metadata`.
- Their `options` set read-only, `lock_timeout=3s`, `statement_timeout=30s`,
  `idle_in_transaction_session_timeout=60s`. `run.py clone` strips
  `PGOPTIONS` so nothing lifts them. Never use the `-long` profiles.
- tsdb0–3 are four independent primaries serving live traffic. Use tsdb2;
  others only when Ryan names them (`--explicit-nodes`).
- Needs the org VPN (`*.int.ore.kiyotaka.ai`); `preflight.sh --prod` checks.
- Scale: prod `trade` was 224 GB in 5231 chunks, raw `trade` kept about two
  days (Aug). Every query on a hypertable is bounded on its time column.

## Clone

When coverage shows the clone is too thin for the probe:

1. `$P -I $S/run.py clone propose --source tsdb2 --table T --since … --until … --batch 60 --target T_tsdb2_<from>_<to>`
2. Show Ryan the proposal (source, slice, batch minutes, 30 s cap, target).
3. On his go: `$P -I $S/run.py clone run <same args> --go [--expose-in <schema>]`.
   It sizes the slice from the catalog (over 70 GB needs `--confirm-size`
   after his yes), runs a plain `EXPLAIN` of the first batch, creates
   `public.<target>` (a new table; it never writes into an existing one),
   then copies chunk-aligned batches, one short psql per batch, pausing
   between. A batch that hits the 30 s cap is halved down to one minute,
   then the clone stops. `--expose-in` adds a view in the run's schema so
   the services read the clone under the table's own name.
4. The clone stays in `public` after teardown, as part of the prod-clone set.

## Probe

```bash
$P -I $S/run.py clone probe [--source tsdb2] -c "SELECT …"
```

One read-only statement, run as plain `EXPLAIN` unless it already starts
with `EXPLAIN`. `EXPLAIN ANALYZE` executes the query on prod and needs its
own go (`--analyze-approved`). Show Ryan each statement before it runs.
