"""Scratch schemas on `data`, behind a guard role that cannot change `public`.

Tables in `public` are prod clones and are never modified. A run's
migrations and writes land in `sd_<slug>`, owned by `sd_guard`, which can
only read `public`. Services see `search_path = sd_<slug>, public`.

Usage:
  python -I run.py scratch selftest
  python -I run.py scratch down --schema S
  python -I run.py scratch coverage --schema S TABLE...
"""

import argparse
import json
import re
import secrets
import sys
import time
from pathlib import Path

from sd.common import SHARED_DEV, STATE, load_env, patch_pg_url, run

GUARD_ROLE = "sd_guard"
LIMIT = 70 * 2**30
IMAGE = "kiyotaka-local-tsdb-gateway"
SCHEMA_RE = re.compile(r"^sd_[a-z0-9_]+$")
_DENIED = re.compile(
    r'(?:permission denied for|must be owner of)\s+(?:table|relation|hypertable|view|materialized view)\s+"?([\w.]+)"?',
    re.I,
)
_URL = re.compile(r"postgres(?:ql)?://\S+")


class TooBig(Exception):
    def __init__(self, table, size, total=None):
        what = f"{table} is {size / 2**30:.1f} GB" + (f", run total would be {total / 2**30:.1f} GB" if total else "")
        super().__init__(f"{what}; over 70 GB needs Ryan's confirmation")
        self.table, self.size = table, size


class NeedsCopy(Exception):
    def __init__(self, table):
        super().__init__(f"migration needs a scratch copy of {table}")
        self.table = table


class TooManyCopies(Exception):
    pass


class MigrateFailed(Exception):
    pass


class Budget:
    """70 GB per table and per run, unless Ryan confirmed."""

    def __init__(self, limit=LIMIT):
        self.limit, self.total = limit, 0

    def charge(self, table, size, confirmed=False):
        if not confirmed:
            if size > self.limit:
                raise TooBig(table, size)
            if self.total + size > self.limit:
                raise TooBig(table, size, self.total + size)
        self.total += size


def _check(schema):
    if not SCHEMA_RE.match(schema or "") or len(schema.encode()) > 63:
        raise ValueError(f"not a scratch schema name: {schema!r}")


def _ident(name):
    return '"' + name.replace('"', '""') + '"'


def main_schema(sha):
    return "sd_main_" + sha[:12]


def connect(url=None):
    import psycopg

    return psycopg.connect(url or load_env()["TIMESCALE_URL"], autocommit=True, connect_timeout=10)


def guard_url(password, schemas):
    url = patch_pg_url(load_env()["TIMESCALE_URL"], user=GUARD_ROLE, password=password,
                       settings={"search_path": ",".join([*schemas, "public"])})
    return url


def _secret_path():
    return STATE / "guard.secret"


def ensure_guard(conn):
    """Create sd_guard if missing and return its password.

    The password is kept in STATE/guard.secret (0600) and reused, so a second
    run never breaks the connections of a first one.
    """
    path = _secret_path()
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (GUARD_ROLE,)).fetchone()
    if exists and path.exists():
        password = path.read_text().strip()
    else:
        password = secrets.token_urlsafe(24)
        if not exists:
            conn.execute(f"CREATE ROLE {GUARD_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
        from psycopg import sql

        conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(GUARD_ROLE), sql.Literal(password)))
        STATE.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600)
        path.write_text(password + "\n")
    db = conn.execute("SELECT current_database()").fetchone()[0]
    conn.execute(f"GRANT CONNECT ON DATABASE {_ident(db)} TO {GUARD_ROLE}")
    for schema in ("public", "_timescaledb_internal"):
        conn.execute(f"GRANT USAGE ON SCHEMA {schema} TO {GUARD_ROLE}")
        conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {GUARD_ROLE}")
    owner = conn.execute("SELECT current_user").fetchone()[0]
    conn.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {_ident(owner)} IN SCHEMA public GRANT SELECT ON TABLES TO {GUARD_ROLE}")
    if conn.execute("SELECT has_schema_privilege(%s, 'public', 'CREATE')", (GUARD_ROLE,)).fetchone()[0]:
        raise SystemExit("sd_guard can CREATE in public (granted to PUBLIC?); the guard would not hold. Ask Ryan.")
    return password


def create_schema(conn, schema):
    _check(schema)
    if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,)).fetchone():
        raise ValueError(f"schema {schema} already exists")
    conn.execute(f"CREATE SCHEMA {_ident(schema)} AUTHORIZATION {GUARD_ROLE}")


def drop_schema(conn, schema):
    _check(schema)
    conn.execute(f"DROP SCHEMA IF EXISTS {_ident(schema)} CASCADE")


def table_size(conn, table):
    row = conn.execute(
        """SELECT CASE WHEN EXISTS (SELECT 1 FROM timescaledb_information.hypertables
                                    WHERE hypertable_schema = 'public' AND hypertable_name = %s)
                       THEN hypertable_size(format('public.%%I', %s::text)::regclass)
                       ELSE pg_total_relation_size(format('public.%%I', %s::text)::regclass) END""",
        (table, table, table),
    ).fetchone()
    return int(row[0] or 0)


def copy_data_sql(table, schema, *, time_col, since):
    """INSERT copying public.table into schema.table; per-chunk bounds when time_col is set."""
    sql = f"INSERT INTO {_ident(schema)}.{_ident(table)} SELECT * FROM {_ident('public')}.{_ident(table)}"
    if time_col:
        sql += f" WHERE {_ident(time_col)} >= %s AND {_ident(time_col)} < %s"
    return sql


def sequence_fixes(schema, table, defaults):
    """SQL giving a copy its own sequences: LIKE … INCLUDING ALL keeps nextval('public.…'),
    which sd_guard may not use, so a service's inserts into the copy would fail."""
    out = []
    for column, expr in defaults:
        m = re.match(r"nextval\('(?:public\.)?\"?([\w]+)\"?'(?:::regclass)?\)", expr or "")
        if not m:
            continue
        seq = f"{_ident(schema)}.{_ident(m.group(1))}"
        out.append(f"CREATE SEQUENCE {seq} OWNED BY {_ident(schema)}.{_ident(table)}.{_ident(column)}")
        out.append(f"ALTER TABLE {_ident(schema)}.{_ident(table)} ALTER COLUMN {_ident(column)} "
                   f"SET DEFAULT nextval('{seq}')")
    return out


def rewrite_ddl(ddl, schema):
    """Point index DDL that `migrate index` writes for public at the scratch schema."""
    return re.sub(r"\bON\s+(?:ONLY\s+)?public\.", f"ON {_ident(schema)}.", ddl, count=1)


def _hypertable(conn, table):
    dims = conn.execute(
        """SELECT column_name, time_interval, integer_interval FROM timescaledb_information.dimensions
           WHERE hypertable_schema = 'public' AND hypertable_name = %s ORDER BY dimension_number""",
        (table,),
    ).fetchall()
    if not dims:
        return None
    comp = conn.execute(
        """SELECT h.compression_enabled, s.segmentby, s.orderby
           FROM timescaledb_information.hypertables h
           LEFT JOIN timescaledb_information.hypertable_compression_settings s
             ON s.hypertable = format('public.%%I', h.hypertable_name)::regclass
           WHERE h.hypertable_schema = 'public' AND h.hypertable_name = %s""",
        (table,),
    ).fetchone()
    return {"time_col": dims[0][0], "interval": dims[0][1] or dims[0][2], "extra_dims": len(dims) - 1,
            "compressed": bool(comp and comp[0]), "segmentby": comp and comp[1], "orderby": comp and comp[2]}


def copy_table(conn, table, schema, *, mode, since=None, confirmed=False, budget=None):
    """Copy public.table into schema.table, owned by sd_guard, with the source's layout."""
    _check(schema)
    if mode not in ("full", "slice", "empty"):
        raise ValueError(f"mode must be full, slice or empty, not {mode!r}")
    size = table_size(conn, table)
    (budget or Budget()).charge(table, 0 if mode == "empty" else size, confirmed)
    ht = _hypertable(conn, table)
    if mode == "slice" and not (ht and since):
        raise ValueError(f"slice needs a hypertable and since; {table} is {'a hypertable' if ht else 'a plain table'}")
    dst = f"{_ident(schema)}.{_ident(table)}"
    conn.execute(f"CREATE TABLE {dst} (LIKE public.{_ident(table)} INCLUDING ALL)")
    defaults = conn.execute(
        """SELECT a.attname, pg_get_expr(d.adbin, d.adrelid) FROM pg_attrdef d
           JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
           WHERE d.adrelid = %s::regclass""", (f"{schema}.{table}",)).fetchall()
    fixes = sequence_fixes(schema, table, defaults)
    for sql in fixes:
        conn.execute(sql)
    compressed = 0
    if ht:
        conn.execute("SELECT create_hypertable(%s, by_range(%s, %s), create_default_indexes => false)",
                     (f"{schema}.{table}", ht["time_col"], ht["interval"]))
        if ht["compressed"]:
            opts = ["timescaledb.compress"]
            if ht["segmentby"]:
                opts.append(f"timescaledb.compress_segmentby = '{ht['segmentby']}'")
            if ht["orderby"]:
                opts.append(f"timescaledb.compress_orderby = '{ht['orderby']}'")
            conn.execute(f"ALTER TABLE {dst} SET ({', '.join(opts)})")
    if mode != "empty":
        if ht:
            chunks = conn.execute(
                """SELECT range_start, range_end, is_compressed FROM timescaledb_information.chunks
                   WHERE hypertable_schema = 'public' AND hypertable_name = %s
                     AND (%s::timestamptz IS NULL OR range_end > %s::timestamptz) ORDER BY range_start""",
                (table, since, since),
            ).fetchall()
            insert = copy_data_sql(table, schema, time_col=ht["time_col"], since=since)
            for start, end, is_compressed in chunks:
                lo = max(start, since) if since else start
                conn.execute(insert, (lo, end))
                if is_compressed:
                    conn.execute(
                        """SELECT compress_chunk(format('%%I.%%I', chunk_schema, chunk_name)::regclass, if_not_compressed => true)
                           FROM timescaledb_information.chunks
                           WHERE hypertable_schema = %s AND hypertable_name = %s AND range_start = %s""",
                        (schema, table, start),
                    )
                    compressed += 1
        else:
            conn.execute(copy_data_sql(table, schema, time_col=None, since=None))
        conn.execute(f"VACUUM (FREEZE, ANALYZE) {dst}")
    for sql in fixes[::2]:  # each CREATE SEQUENCE: move it past the copied rows
        seq, column = re.match(r"CREATE SEQUENCE (\S+) OWNED BY \S+\.(\S+)$", sql).groups()
        conn.execute(f"SELECT setval('{seq}', coalesce((SELECT max({column}) FROM {dst}), 0) + 1, false)")
    conn.execute(f"ALTER TABLE {dst} OWNER TO {GUARD_ROLE}")
    return {"table": table, "mode": mode, "bytes": size, "hypertable": bool(ht), "compressed_chunks": compressed,
            "extra_dims_not_copied": ht["extra_dims"] if ht else 0}


def copy_view(conn, name, schema):
    """Recreate a public view or (non-continuous) materialized view in schema."""
    _check(schema)
    row = conn.execute(
        """SELECT c.relkind, pg_get_viewdef(c.oid, true),
                  EXISTS (SELECT 1 FROM timescaledb_information.continuous_aggregates
                          WHERE view_schema = 'public' AND view_name = c.relname)
           FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace AND c.relname = %s""",
        (name,),
    ).fetchone()
    if not row:
        raise MigrateFailed(f"public.{name} does not exist")
    kind, definition, is_cagg = row
    if is_cagg:
        raise MigrateFailed(f"public.{name} is a continuous aggregate; copy its source hypertable instead (ask Ryan)")
    dst = f"{_ident(schema)}.{_ident(name)}"
    if kind == "v":
        conn.execute(f"CREATE VIEW {dst} AS {definition}")
        conn.execute(f"ALTER VIEW {dst} OWNER TO {GUARD_ROLE}")
    elif kind == "m":
        conn.execute(f"CREATE MATERIALIZED VIEW {dst} AS {definition.rstrip(';')} WITH DATA")
        conn.execute(f"ALTER MATERIALIZED VIEW {dst} OWNER TO {GUARD_ROLE}")
    else:
        raise MigrateFailed(f"public.{name} has relkind {kind}, not a view")
    return {"table": name, "mode": "view", "bytes": 0}


def copy_object(conn, name, schema, *, mode="full", budget=None):
    kind = conn.execute("SELECT relkind FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relname = %s",
                        (name,)).fetchone()
    if kind and kind[0] in ("v", "m"):
        return copy_view(conn, name, schema)
    return copy_table(conn, name, schema, mode=mode, budget=budget)


def expose(conn, schema, name, target):
    """A view schema.name over public.target, so a new clone reads under the services' name."""
    _check(schema)
    dst = f"{_ident(schema)}.{_ident(name)}"
    conn.execute(f"CREATE VIEW {dst} AS SELECT * FROM public.{_ident(target)}")
    conn.execute(f"ALTER VIEW {dst} OWNER TO {GUARD_ROLE}")


def caggs_on_public(conn, schema):
    """Public hypertables that a continuous aggregate in schema reads from."""
    rows = conn.execute(
        """SELECT DISTINCT raw.table_name FROM _timescaledb_catalog.continuous_agg ca
           JOIN _timescaledb_catalog.hypertable raw ON raw.id = ca.raw_hypertable_id
           WHERE ca.user_view_schema = %s AND raw.schema_name = 'public'""",
        (schema,),
    ).fetchall()
    return sorted(r[0] for r in rows)


def needs_copy(output):
    """The table a guard-role permission error names, or None."""
    m = _DENIED.search(output)
    if not m:
        return None
    name = m.group(1).lower()
    return name.removeprefix("public.")


def _redact(text):
    return _URL.sub("postgres://<redacted>", text)


def _migrate_config(password, schemas, run_dir, name):
    base = json.loads((SHARED_DEV / "config" / "tsdb-gateway-writer.yaml").read_text())
    url = guard_url(password, schemas) + "&application_name=sd-migrate"
    for key in ("primary", "secondary", "free_secondary"):
        if key in base.get("timescaledb", {}):
            base["timescaledb"][key]["url"] = url
    path = Path(run_dir) / "config" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.write_text(json.dumps(base, indent=2))
    return path


def _gateway(gateway_bin, config, schema_yaml, args, *, mounts=(), timeout=1800):
    cmd = ["docker", "run", "--rm", "--platform", "linux/arm64", "--entrypoint", "/shared-dev/tsdb-gateway",
           "-v", f"{gateway_bin}:/shared-dev/tsdb-gateway:ro", "-v", f"{config}:/config.yaml:ro",
           "-v", f"{schema_yaml}:/schema.yaml:ro"]
    for host, target in mounts:
        cmd += ["-v", f"{host}:{target}:ro"]
    cmd += [IMAGE, "-c", "/config.yaml", "-s", "/schema.yaml", *args]
    return run(cmd, timeout=timeout, check=False)


def apply_delta(schema, versions, sources, gateway_bin, password, run_dir, *, schema_yaml):
    """Apply versions into schema as sd_guard with the gateway's own migrate."""
    from sd.migrations import stage

    staged = Path(run_dir) / f"migrations-{schema}"
    v0 = stage(versions, sources, staged)
    config = _migrate_config(password, [schema], run_dir, f"migrate-{schema}")
    mounts = [(staged, "/migrations")]
    for args in (["-M", "/migrations", "migrate", "force", str(v0)], ["-M", "/migrations", "migrate", "up"]):
        proc = _gateway(gateway_bin, config, schema_yaml, args, mounts=mounts)
        if proc.returncode != 0:
            out = _redact(proc.stdout + proc.stderr)
            table = needs_copy(out)
            if table:
                raise NeedsCopy(table)
            if re.search(r"permission denied for (?:database|schema)", out, re.I):
                raise MigrateFailed("a migration creates a schema or writes to public by name, which cannot be "
                                    "redirected into the scratch schema:\n" + out[-2000:])
            raise MigrateFailed(out[-2000:])


def apply_with_copies(conn, schema, versions, sources, gateway_bin, password, run_dir, *, copies, apply=apply_delta,
                      budget=None, max_rounds=5, **apply_kw):
    """Apply versions on a fresh schema, copying what the guard role refuses, at most max_rounds times.

    Never retries as the superuser: a table the guard will not let a
    migration touch gets a scratch copy instead.
    """
    copies = dict(copies)
    charged = set()
    rounds = 0
    while True:
        drop_schema(conn, schema)
        create_schema(conn, schema)
        for name, mode in copies.items():
            copy_object(conn, name, schema, mode=mode, budget=None if name in charged else budget)
            charged.add(name)
        try:
            apply(schema, versions, sources, gateway_bin, password, run_dir, **apply_kw)
            # The guard cannot stop a continuous aggregate over a public
            # hypertable (SELECT is enough), so check for one after the fact.
            needed = caggs_on_public(conn, schema)
            if not needed:
                return copies
        except NeedsCopy as exc:
            needed = [exc.table]
        repeated = [t for t in needed if t in copies]
        if repeated:
            raise TooManyCopies(f"{', '.join(repeated)} already copied and still needed from public "
                                "(named public. explicitly?)")
        if rounds >= max_rounds:
            raise TooManyCopies(f"more than {max_rounds} rounds of copies needed; last needed {', '.join(needed)}")
        for table in needed:
            copies[table] = "full"
        rounds += 1



def index_plan(gateway_bin, main_schema_yaml, branch_schema_yaml, password, run_dir, schema):
    """Index DDL the branch's schema yaml adds over main's, rewritten for the scratch schema."""
    config = _migrate_config(password, [schema], run_dir, f"index-{schema}")

    def ddl(schema_yaml):
        proc = _gateway(gateway_bin, config, schema_yaml, ["migrate", "index", "--dry-run"], timeout=600)
        if proc.returncode != 0:
            raise MigrateFailed(_redact(proc.stdout + proc.stderr)[-2000:])
        return {line.strip() for line in proc.stdout.splitlines() if re.match(r"\s*CREATE\s+(UNIQUE\s+)?INDEX", line, re.I)}

    main, branch = ddl(main_schema_yaml), ddl(branch_schema_yaml)
    return {"branch_only": sorted(rewrite_ddl(d, schema) for d in branch - main), "main_missing": sorted(main)}


def coverage(conn, schema, tables, kinds=None):
    """Per table: where it is read from and how much of it there is, from the catalog only."""
    kinds = kinds or {}
    out = []
    for table in tables:
        in_scratch = conn.execute(
            "SELECT 1 FROM pg_class WHERE relnamespace = %s::regnamespace AND relname = %s", (schema, table)
        ).fetchone()
        where = schema if in_scratch else "public"
        rel = f"{_ident(where)}.{_ident(table)}"
        row = conn.execute(
            """SELECT count(*), min(range_start), max(range_end) FROM timescaledb_information.chunks
               WHERE hypertable_schema = %s AND hypertable_name = %s""",
            (where, table),
        ).fetchone()
        if row[0]:
            rows = conn.execute("SELECT approximate_row_count(%s::regclass)", (rel,)).fetchone()[0]
            size = conn.execute("SELECT hypertable_size(%s::regclass)", (rel,)).fetchone()[0]
        else:
            rows = conn.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", (rel,)).fetchone()[0]
            size = conn.execute("SELECT pg_total_relation_size(%s::regclass)", (rel,)).fetchone()[0]
        out.append({"table": table, "read_from": where, "kind": kinds.get(table, "copy" if in_scratch else "clone"),
                    "rows": int(rows or 0), "bytes": int(size or 0), "chunks": row[0],
                    "from": row[1] and row[1].isoformat(), "to": row[2] and row[2].isoformat()})
    shared = conn.execute("SELECT current_setting('shared_buffers')").fetchone()[0]
    return {"tables": out, "shared_buffers": shared}


# --- selftest -------------------------------------------------------------

_PROBE_TABLES = ("open_interest", "trade")


def _snapshot(conn):
    snap = {}
    for t in _PROBE_TABLES:
        rel = f"public.{t}"
        cols = conn.execute(
            """SELECT attname, format_type(atttypid, atttypmod), attnotnull FROM pg_attribute
               WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum""", (rel,)).fetchall()
        idx = conn.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = %s "
                           "ORDER BY 1", (t,)).fetchall()
        trg = conn.execute("SELECT tgname FROM pg_trigger WHERE tgrelid = %s::regclass ORDER BY 1", (rel,)).fetchall()
        caggs = conn.execute(
            """SELECT count(*) FROM _timescaledb_catalog.continuous_agg ca
               JOIN _timescaledb_catalog.hypertable h ON h.id = ca.raw_hypertable_id
               WHERE h.schema_name = 'public' AND h.table_name = %s""", (t,)).fetchone()
        writes = conn.execute(
            """SELECT coalesce(sum(n_tup_ins + n_tup_upd + n_tup_del), 0) FROM pg_stat_all_tables
               WHERE relid = %s::regclass OR relid IN (SELECT show_chunks(%s::regclass))""", (rel, rel)).fetchone()
        snap[t] = {"columns": cols, "indexes": idx, "triggers": trg, "caggs": caggs[0], "writes": int(writes[0])}
    snap["public_relations"] = conn.execute(
        "SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace").fetchone()[0]
    return snap


def _expect_denied(guard, label, statement, *, transaction=True):
    import psycopg

    try:
        if transaction:
            with guard.transaction(force_rollback=True):
                guard.execute(statement)
        else:
            guard.execute(statement)
    except psycopg.errors.InsufficientPrivilege as exc:
        return f"ok   {label}: denied ({str(exc).splitlines()[0]})"
    except psycopg.Error as exc:
        return f"FAIL {label}: expected permission denied, got {type(exc).__name__}: {str(exc).splitlines()[0]}"
    return f"FAIL {label}: the guard role was allowed to do it"


def selftest():
    conn = connect()
    running = run(["docker", "ps", "--filter", "label=com.docker.compose.project", "--format", "{{.Names}}"],
                  timeout=20, check=False).stdout.split()
    if any(name.startswith("kiyotaka-shared-dev") for name in running):
        print("warn shared-dev containers are running; their writes would show up as public changes")
    password = ensure_guard(conn)
    tag = secrets.token_hex(3)
    schema, empty_schema = f"sd_selftest_{tag}", f"sd_selftest_{tag}_e"
    lines, failed = [], False
    before = _snapshot(conn)
    try:
        create_schema(conn, schema)
        create_schema(conn, empty_schema)
        since = conn.execute("SELECT max(range_start) - interval '24 hours' FROM timescaledb_information.chunks "
                             "WHERE hypertable_schema = 'public' AND hypertable_name = 'open_interest'").fetchone()[0]
        lines.append(f"ok   slice copy: {copy_table(conn, 'open_interest', schema, mode='slice', since=since)}")
        lines.append(f"ok   empty copy: {copy_table(conn, 'open_interest', empty_schema, mode='empty')}")
        guard = connect(guard_url(password, [schema]))
        try:
            with guard.transaction(force_rollback=True):
                guard.execute("INSERT INTO open_interest SELECT * FROM public.open_interest LIMIT 1")
            lines.append("ok   insert into the scratch copy (unqualified name resolves to the copy)")
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            lines.append(f"FAIL insert into the scratch copy: {type(exc).__name__}: {exc}")
        lines.append(_expect_denied(guard, "insert into public.open_interest",
                                    "INSERT INTO public.open_interest SELECT * FROM public.open_interest LIMIT 1"))
        lines.append(_expect_denied(guard, "alter public.open_interest",
                                    "ALTER TABLE public.open_interest ADD COLUMN sd_probe int"))
        lines.append(_expect_denied(guard, "create index on public.open_interest",
                                    "CREATE INDEX sd_probe_idx ON public.open_interest (symbol)"))
        lines.append(_expect_denied(guard, "create schema", "CREATE SCHEMA sd_probe_schema"))
        cagg = (f"CREATE MATERIALIZED VIEW {schema}.sd_probe_cagg WITH (timescaledb.continuous) AS "
                "SELECT time_bucket('1 hour', \"timestamp\") AS b, count(*) FROM public.trade GROUP BY 1 WITH NO DATA")
        # TimescaleDB lets SELECT create a cagg over public.trade; caggs_on_public must catch it.
        try:
            guard.execute(cagg)
            found = caggs_on_public(conn, schema)
            lines.append(("ok   " if found == ["trade"] else "FAIL ") + f"cagg over public.trade detected: {found}")
        except Exception as exc:  # noqa: BLE001 - reported
            lines.append(f"ok   cagg over public.trade refused outright: {type(exc).__name__}")
        finally:
            conn.execute(f"DROP MATERIALIZED VIEW IF EXISTS {_ident(schema)}.sd_probe_cagg")
        guard.close()
    finally:
        for s in (schema, empty_schema):
            drop_schema(conn, s)
    left = conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN (%s, %s)", (schema, empty_schema)).fetchone()[0]
    left += conn.execute("SELECT count(*) FROM _timescaledb_catalog.hypertable WHERE schema_name IN (%s, %s)",
                         (schema, empty_schema)).fetchone()[0]
    lines.append(("ok   " if left == 0 else "FAIL ") + f"scratch schemas dropped, {left} leftovers")
    time.sleep(2)  # let the guard session's stats flush
    conn.execute("SELECT pg_stat_clear_snapshot()")
    after = _snapshot(conn)
    for key in before:
        same = before[key] == after[key]
        lines.append(("ok   " if same else "FAIL ") + f"public.{key} unchanged" if key != "public_relations"
                     else ("ok   " if same else "FAIL ") + "no new relations in public")
    for line in lines:
        print(line)
        failed |= line.startswith("FAIL")
    print("selftest FAILED" if failed else "selftest ok")
    return 1 if failed else 0


def main(argv):
    ap = argparse.ArgumentParser(prog="scratch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    d = sub.add_parser("down")
    d.add_argument("--schema", required=True, action="append")
    c = sub.add_parser("coverage")
    c.add_argument("--schema", required=True)
    c.add_argument("tables", nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "selftest":
        sys.exit(selftest())
    conn = connect()
    if args.cmd == "down":
        for schema in args.schema:
            drop_schema(conn, schema)
            print(f"dropped {schema}")
    elif args.cmd == "coverage":
        json.dump(coverage(conn, args.schema, args.tables), sys.stdout, indent=2, default=str)
        print()
