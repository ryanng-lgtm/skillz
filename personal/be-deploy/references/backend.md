# Backend deploy specifics

Read with the "From a draft MR to a verified deploy" stages in `SKILL.md`.
Database reads below are read-only and go through the tsdb-verify skill's
wrapper; anything that writes to a production database (dropping or
building an index by hand) needs the service owner's go first.

## tsdb-gateway

### Apps per environment

Read them from `argocd app list -o name | grep tsdb-gateway`; counts differ
per environment.

- **Write shards**, `<env>-cache-tsdb-gateway-<N>-main`, one per database
  (ore has 0 to 3). Each uses `charts/tsdb-gateway-<N>`, whose files are
  symlinks into `charts/tsdb-gateway` (`values.yaml`, `values.<env>.yaml`,
  `schema/`, `templates/`) plus a real `values.<env>.z.override.yaml` that
  points the shard at its own database. Every shard runs its own writers,
  cjob Deployments (refresh, compress, drop, reorder) and migrate hook
  against that database, so a values or schema change reaches all databases
  only when every shard has synced.
- **Read set**, `<env>-cache-tsdb-gateway-read-main` (chart
  `tsdb-gateway-read`). Never synced in the same step as the write shards.
- An app that reports health `Missing` and has never synced is not part of
  the rollout. Leave it and ask its owner.

### Before the sync

- **Migrations.** `schema_migrations` records only the latest version, so a
  migration whose timestamp is below the latest one applied in that
  environment is skipped without an error. Compare before merging.
- **Schema yaml.** A change to `schema.<env>.yaml` (an aggregate policy, a
  retention policy, an index) changes what the cjobs select and what the
  migrate hook builds. Read which refresh, compress and drop jobs will pick
  up the changed tier from their include and exclude patterns and skip
  lists in `values.<env>.yaml`, and say so in the plan.
  - Per-plane values are anchors in `schema.<plane>.yaml`, aliased from
    `schema.boneless.yaml`. One anchor can serve many tiers (the 1h
    deep-history retention serves several buckets), so a change meant for
    one tier needs an anchor of its own.
  - A non-null aggregate policy opens the tier to the refresh jobs whose
    patterns match it, the compress job, the invalidation refresher where it
    has replicas, and the migrate hook's index build. A non-null retention
    makes the drop job call `drop_chunks` on it, which recomputes a cagg's
    watermark from its stored rows on every call. For a cagg that holds
    loaded history, the backfill-setup skill has the order these go in.
  - The drop job logs nothing for a tier it skips. Check it from the next
    run's `drop_chunks(` lines in Loki per database, or from
    `cjob --dry-run drop --mode oneshot` in the drop pod.
  - The cjobs run from the write shards, so a schema change takes effect on
    a database when its shard syncs, not when the read app does.
- **Index size.** When the deploy adds an index to an existing table or
  continuous aggregate, read the table's size first
  (`hypertable_size('<storage table>')`). A large build decides the order
  below.

### The migrate hook

`charts/tsdb-gateway/templates/job-migrate.yaml`: a Helm
`post-install,post-upgrade` hook (PostSync in ArgoCD) with
`activeDeadlineSeconds: 3600`, running
`migrate up --migrations /migrations/ --with-index`. Indexes are created by
`cmd/tsdb-gateway/handle_migrate.go` as

```sql
CREATE INDEX IF NOT EXISTS <name> ON <relation> (<columns>) WITH (timescaledb.transaction_per_chunk)
```

`transaction_per_chunk` builds each chunk's copy in its own transaction. If
the job is killed at the deadline, the parent index already exists while
some chunks have no copy or an invalid one, and `IF NOT EXISTS` makes every
later deploy skip it. A redeploy does not repair it. Repair is a hand
`DROP INDEX` followed by a redeploy (or a per-chunk build), on the owner's
go.

So, for a deploy that builds an index on a large table: sync one shard
first, time its hook, check the index on every chunk, and only then sync
the other shards. Shards hold different amounts of data; the first
shard's time is an estimate, not a bound.

When a build may not fit the hour, build it by hand before the deploy, on
the owner's go per database: the same statement with the exact name the
schema yaml produces (`<relation>_<index name>_ts`) and the same columns.
The deploy then skips it. `IF NOT EXISTS` matches on the name only, so a
hand-built index with other columns stays wrong without any error. A hand
build has no deadline and can wait for a quiet window; it is not faster,
since the time goes into reading and sorting the table.

### Checking an index on every chunk

TimescaleDB 2.30 has no `_timescaledb_catalog.chunk_index`, and a chunk's
index name is the chunk name plus the parent index name cut at 63
characters, so match chunk indexes to the parent by their key columns.
`<view>` is the continuous aggregate's user view name; for a plain
hypertable, select the table itself as `ht`.

```sql
WITH v AS (
  SELECT ca.user_view_name AS view, format('%I.%I', h.schema_name, h.table_name)::regclass AS ht
    FROM _timescaledb_catalog.continuous_agg ca
    JOIN _timescaledb_catalog.hypertable h ON h.id = ca.mat_hypertable_id
   WHERE ca.user_view_name IN ('<view>', '<view>')
), chunks AS (
  SELECT v.view, i.inhrelid AS chunk FROM v JOIN pg_inherits i ON i.inhparent = v.ht
)
SELECT v.view,
       pi.relname || ' (' || (SELECT string_agg(a.attname, ',' ORDER BY k.ord) FROM unnest(px.indkey) WITH ORDINALITY k(attnum, ord) JOIN pg_attribute a ON a.attrelid = px.indrelid AND a.attnum = k.attnum) || ')',
       px.indisvalid,
       (SELECT count(*) FROM chunks c JOIN pg_index cx ON cx.indrelid = c.chunk
         WHERE c.view = v.view
           AND (SELECT string_agg(a.attname, ',' ORDER BY k.ord) FROM unnest(cx.indkey) WITH ORDINALITY k(attnum, ord) JOIN pg_attribute a ON a.attrelid = cx.indrelid AND a.attnum = k.attnum) = (SELECT string_agg(a.attname, ',' ORDER BY k.ord) FROM unnest(px.indkey) WITH ORDINALITY k(attnum, ord) JOIN pg_attribute a ON a.attrelid = px.indrelid AND a.attnum = k.attnum)),
       (SELECT count(*) FROM chunks c JOIN pg_index cx ON cx.indrelid = c.chunk
         WHERE c.view = v.view
           AND (SELECT string_agg(a.attname, ',' ORDER BY k.ord) FROM unnest(cx.indkey) WITH ORDINALITY k(attnum, ord) JOIN pg_attribute a ON a.attrelid = cx.indrelid AND a.attnum = k.attnum) = (SELECT string_agg(a.attname, ',' ORDER BY k.ord) FROM unnest(px.indkey) WITH ORDINALITY k(attnum, ord) JOIN pg_attribute a ON a.attrelid = px.indrelid AND a.attnum = k.attnum)
           AND NOT cx.indisvalid),
       (SELECT count(*) FROM chunks c WHERE c.view = v.view)
  FROM v JOIN pg_index px ON px.indrelid = v.ht JOIN pg_class pi ON pi.oid = px.indexrelid
 ORDER BY 1, 2;
```

Columns: view, parent index (key columns), parent valid, chunks carrying
it, invalid copies on chunks, chunks. Pass: every parent valid, the fourth
column equal to the sixth, the fifth zero. While a hook is still building,
`pg_stat_progress_create_index` (joined to `pg_stat_activity` on `pid`)
shows the relation, phase and blocks done.

## tsdb-move

The chart's `values.<env>.yaml` lists one Kubernetes Job per move. Sync
only the Job you mean to run:

```bash
argocd app sync <app> --grpc-web --resource batch:Job:<job name>
```

A whole-app sync creates every Job the file lists. A Job that has finished
keeps its object until its TTL, and syncing it again does not rerun it
while that object exists. Remove finished Jobs from the values file in a
follow-up MR so a later sync cannot start them again.

Writing a load job:

- Put it in `values.<env>.yaml`, not `values.yaml`: every tsdb-move MR gets
  a staging preview app that renders `values.yaml` and
  `values.staging.yaml` from the MR branch.
- `replace: true` deletes the target range and inserts the source range one
  batch per transaction, so a rerun does not duplicate rows. Without it a
  rerun inserts again.
- One connection serves source and target, so both tables are on the same
  database. Storage table names (`_materialized_hypertable_<n>`) differ per
  database: read them on each before writing the job.
- An `interval` that is a multiple of `30d` runs calendar months.
- Run a `dry_run: true` job first, or the binary locally with the job's
  arguments (`--dry-run` opens no connection), and render the chart with
  `helm template` for the target env and for staging.
