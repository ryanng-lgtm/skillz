# shared-dev environment

Verified 2026-10-26. Re-check what you rely on; things move (Sean's PC changed
Tailscale IP twice in October).

## The bundle: `~/.config/shared-dev`

- Base compose project `kiyotaka-shared-dev` (`compose.yaml`), seven services.
  `up` never edits it; each run renders its own `$RUN/compose.json`.

| Service | Command | Host ports (base) | Depends on |
|---|---|---|---|
| metadata-instrument | `metadata-instrument -c … start` | 8092, 4081, 18092, 18081 | — |
| tsdb-read | `tsdb-gateway … read` | 4080, 4000, 18080, 12080 | metadata-instrument |
| tsdb-api | `tsdb-gateway … api` | 4084, 4004, 18084, 12084 | metadata-instrument |
| tsdb-write | `tsdb-gateway … write` | — | metadata-instrument |
| tsdb-registry | `tsdb-gateway … registry` | — | metadata-instrument |
| stream-deduplicated | `stream-deduplicated -c …` (run from the mounted binary) | — | — |
| live-feed | `live-feed --config …` | 5080, 18090, 19090 | metadata-instrument, tsdb-read |

- Images `kiyotaka-local-*`, `pull_policy: never`; the code that runs is the
  linux/arm64 binary mounted at `/shared-dev/<name>`. The gateway's `-s`
  schema must match its binary (`builds.schema_for`).
- tsdb-registry is OOM-killed at 2g; runs set 4g. Docker Desktop has
  7.7 GiB and has hung before: every docker call has a timeout.
- Rendered configs in `config/` are JSON and hold credentials. `configure.py`
  must not be re-run (its manifest hashes are stale).
- Old feature overlays (`compose.feature.yaml`, `compose.bitget.yaml`,
  `compose.gemini.yaml`, …) and ~40 hand-made configs are history; runs
  don't use them.
- `check_connections.py --backing-only` checks Sean's PC; `status.py`
  diagnoses the base project.
- `state/` holds the skill's claims, `guard.secret` and
  `public-baseline.json`; `bin/linux-arm64-main-<sha>/` caches main builds.

## Sean's PC (`sean-trontal`, Tailscale, not SSH)

- TimescaleDB `:25432`, db `data`, login `dev` (superuser); PG 18,
  TimescaleDB 2.29. Runs inside k3s, so every client shows as `10.42.0.1`.
- `public`: prod clones. `registry` is 26 GB (~46.7M rows, near-full);
  market-data hypertables are thin slices (`trade` 444 MB in 263 chunks,
  1-hour chunks). Other schemas (`lit_relist_archive`, `fix`, `probe_atr`)
  are leftovers from past sessions; leave them.
- Metadata Postgres `:5433`, db `meta_ryan`, Ryan's own database on an
  instance shared with Sean and Alex: no roles, extensions or settings.
- Redis `:26379`. Kafka `:19092`, SASL PLAIN user `ryan`, ACLs PREFIXED on
  `dev.ryan.`. Never delete `dev.ryan.normalized` or `dev.ryan.deduplicated`.

## The guard role

`sd_guard` reads `public` and owns only `sd_*` schemas. TimescaleDB still
lets it build a continuous aggregate over a public hypertable with SELECT
alone, so after applying migrations `up` checks for one and copies the
source instead. `run.py scratch selftest` proves the guard on the live DB.

## Repos and builds

- Anchor clones under `~/Documents/GitLab/meta_repo/<repo>`; feature
  worktrees under `~/Documents/GitLab/worktrees/<branch-slug>/<repo>`.
  Builds never check anything out in an anchor clone.
- cgo is required (confluent-kafka): builds run in `golang:1.27-alpine`
  (static musl). A host build fails with `undefined: kafka.Event` or
  produces a Mach-O binary.
- `vendor/` is gitignored in every backend repo; `go mod vendor` runs on the
  host before each build.
- Live capture config comes from
  `meta_repo/streamd-cex-playbook/configs/streamd.yaml.j2`
  (`<venue>_exchange_config:` blocks).

## FE stack

kiyo-fe, tharamine, orange, auth and orange-shared run in Ryan's own
terminals. `kiyotaka-frontend` and `orange-shared` are under
`~/Documents/GitLab`; find the others from their listening processes.
