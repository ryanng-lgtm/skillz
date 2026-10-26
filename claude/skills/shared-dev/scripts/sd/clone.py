"""Prod reads: short-batch clones from tsdb2 or pgmeta0, and guarded probes.

The rule over everything here: prod connections are short and light, so
live queries never notice them. Every prod session goes through a named
profile in ~/.pg_service.conf, whose options set read-only, lock_timeout
3s, statement_timeout 30s and idle_in_transaction_session_timeout 60s.
Nothing here overrides those options: no -long profiles, no PGOPTIONS, no
`set transaction`. Every prod read needs Ryan's go for that request.

Usage (the skill calls these from Python; there is no unattended CLI):
  clone.proposal(...) -> show it to Ryan -> clone.run(proposal, go=True)
  clone.probe("tsdb2", sql)
"""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, unquote, urlsplit

from sd.common import load_env, slug
from sd.scratch import LIMIT, TooBig

SOURCES = {"tsdb2", "pgmeta0"}
ALL_TSDB = {"tsdb0", "tsdb1", "tsdb2", "tsdb3"}
FLOOR = timedelta(minutes=1)
MAX_CHUNKS = 4
BATCH_TIMEOUT = 120  # wall clock per batch process; the server-side cap is the profile's 30 s


class Refused(Exception):
    pass


class BatchTimeout(Exception):
    pass


class CloneStopped(Exception):
    pass


def _psql():
    return shutil.which("psql") or "/opt/homebrew/opt/libpq/bin/psql"


def _prod_env(appname):
    """The environment for a prod psql: no PGOPTIONS, so the profile's limits hold."""
    env = {k: v for k, v in os.environ.items() if k != "PGOPTIONS"}
    env["PGAPPNAME"] = appname
    return env


def _check_source(source, explicit_nodes=False):
    if source.endswith("-long"):
        raise Refused(f"{source}: -long profiles lift the 30 s cap; never used by the skill")
    if source in SOURCES:
        return
    if source in ALL_TSDB and explicit_nodes:
        return
    raise Refused(f"{source}: clones and probes use tsdb2 or pgmeta0; other tsdb nodes only when Ryan says so")


def _ts(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def proposal(source, table, *, since, until, batch, target, explicit_nodes=False):
    """What Ryan sees before saying go."""
    _check_source(source, explicit_nodes)
    if not re.match(r"^[a-z_][a-z0-9_]*$", target):
        raise Refused(f"target {target!r} is not a plain table name")
    return {"source": source, "table": table, "since": since, "until": until, "batch": batch,
            "statement_timeout": "30s (service profile)", "target": f"public.{target}",
            "explicit_nodes": explicit_nodes}


def _prod(source, sql, appname, *, timeout=60):
    proc = subprocess.run([_psql(), f"service={source}", "-X", "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
                          capture_output=True, text=True, timeout=timeout, env=_prod_env(appname))
    if proc.returncode != 0:
        _raise_for(proc.stderr)
    return proc.stdout


def _raise_for(stderr):
    if "could not translate host name" in stderr or "nodename nor servname" in stderr:
        raise CloneStopped("prod database names do not resolve; connect the org VPN. Stopped after one attempt.")
    if "canceling statement due to statement timeout" in stderr:
        raise BatchTimeout(stderr.strip().splitlines()[-1])
    raise CloneStopped(stderr.strip()[-500:])


def size(source, table, since, until):
    """Bytes the slice occupies on the source, from the catalog only."""
    sql = f"""SELECT coalesce(sum(s.total_bytes), 0)
              FROM chunks_detailed_size('public.{table}') s
              JOIN timescaledb_information.chunks c ON c.chunk_schema = s.chunk_schema AND c.chunk_name = s.chunk_name
              WHERE c.hypertable_name = '{table}' AND c.range_end > '{_ts(since)}' AND c.range_start < '{_ts(until)}'"""
    return int(_prod(source, sql, "sd-clone-size").strip() or 0)


def source_layout(source, table):
    """Columns, time column and chunk interval of public.<table> on the source (catalog only)."""
    cols = _prod(source, f"""SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute
                             WHERE attrelid = 'public.{table}'::regclass AND attnum > 0 AND NOT attisdropped
                             ORDER BY attnum""", "sd-clone-layout")
    dim = _prod(source, f"""SELECT column_name, extract(epoch FROM time_interval)::bigint
                            FROM timescaledb_information.dimensions
                            WHERE hypertable_schema = 'public' AND hypertable_name = '{table}'
                            ORDER BY dimension_number LIMIT 1""", "sd-clone-layout").strip()
    if not dim:
        raise Refused(f"{table} is not a hypertable on {source}; a time-bounded clone needs one")
    time_col, seconds = dim.split("|")
    return {"columns": [tuple(line.split("|", 1)) for line in cols.splitlines() if line],
            "time_col": time_col, "interval": timedelta(seconds=int(seconds))}


def batch_sql(table, columns, time_col, lo, hi):
    cols = ", ".join(f'"{c}"' for c in columns)
    return (f'COPY (SELECT {cols} FROM public."{table}" WHERE "{time_col}" >= \'{_ts(lo)}\' '
            f'AND "{time_col}" < \'{_ts(hi)}\') TO STDOUT (FORMAT csv)')


def _align_up(t, chunk):
    epoch = datetime(1970, 1, 1, tzinfo=t.tzinfo)
    n = -(-((t - epoch) // timedelta(microseconds=1)) // (chunk // timedelta(microseconds=1)))
    return epoch + n * chunk


def _align_down(t, chunk):
    epoch = datetime(1970, 1, 1, tzinfo=t.tzinfo)
    return epoch + ((t - epoch) // chunk) * chunk


def batches(since, until, batch, chunk):
    """[lo, hi) ranges covering [since, until), each at most `batch`, ending on chunk boundaries."""
    out, lo = [], since
    while lo < until:
        hi = min(lo + batch, until)
        if batch <= chunk:
            hi = min(hi, _align_up(lo + timedelta(microseconds=1), chunk))
        elif hi < until and _align_down(hi, chunk) > lo:
            hi = _align_down(hi, chunk)
        out.append((lo, hi))
        lo = hi
    return out


def explain_ok(source, table, layout, lo, hi):
    """Plain EXPLAIN of one batch: no execution, just the plan's chunk count."""
    cols = [c for c, _ in layout["columns"]]
    select = batch_sql(table, cols, layout["time_col"], lo, hi)[len("COPY ("):-len(") TO STDOUT (FORMAT csv)")]
    plan = json.loads(_prod(source, f"EXPLAIN (FORMAT JSON) {select}", "sd-clone-explain"))
    chunks = set()

    def walk(node):
        name = node.get("Relation Name", "")
        if name.startswith("_hyper_") or name.startswith("compress_hyper_"):
            chunks.add(name)
        for child in node.get("Plans", []):
            walk(child)

    walk(plan[0]["Plan"])
    expected = max(MAX_CHUNKS, 2 * (-(-(hi - lo) // layout["interval"])) + 1)
    if len(chunks) > expected:
        return False, f"plan scans {len(chunks)} chunks for one batch (expected at most {expected}); not running it"
    return True, f"plan scans {len(chunks)} chunk relations"


def _local_url():
    return load_env()["TIMESCALE_URL"]


def _local_env():
    """libpq environment for the dev tsdb, so its password never sits in argv (visible in ps)."""
    parts = urlsplit(_local_url())
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    env.update({"PGHOST": parts.hostname or "", "PGPORT": str(parts.port or 5432),
                "PGUSER": unquote(parts.username or ""), "PGPASSWORD": unquote(parts.password or ""),
                "PGDATABASE": parts.path.lstrip("/")})
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            env["PGSSLMODE"] = value
    return env


def target_exists(target):
    from sd import scratch

    return scratch.connect().execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{target}",)).fetchone()[0]


def create_target(target, layout):
    """public.<target> on data as dev, with the source's columns and chunk interval."""
    from sd import scratch

    conn = scratch.connect()
    cols = ", ".join(f'"{name}" {typ}' for name, typ in layout["columns"])
    conn.execute(f'CREATE TABLE public."{target}" ({cols})')
    conn.execute("SELECT create_hypertable(%s, by_range(%s, %s))",
                 (f"public.{target}", layout["time_col"], layout["interval"]))


def _copy_batch(source, table, layout, lo, hi, target, appname):
    cols = [c for c, _ in layout["columns"]]
    prod = subprocess.Popen([_psql(), f"service={source}", "-X", "-v", "ON_ERROR_STOP=1", "-c",
                             batch_sql(table, cols, layout["time_col"], lo, hi)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_prod_env(appname))
    local = subprocess.Popen([_psql(), "-X", "-v", "ON_ERROR_STOP=1", "-c",
                              f'\\copy public."{target}" FROM STDIN (FORMAT csv)'],
                             stdin=prod.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_local_env())
    prod.stdout.close()
    try:
        _, prod_err = prod.communicate(timeout=BATCH_TIMEOUT)
        _, local_err = local.communicate(timeout=BATCH_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        prod.kill()
        local.kill()
        raise CloneStopped(f"batch {_ts(lo)}..{_ts(hi)} ran past {BATCH_TIMEOUT}s; stopped") from exc
    if prod.returncode != 0:
        _raise_for(prod_err.decode())
    if local.returncode != 0:
        raise CloneStopped(f"writing into public.{target} failed: {local_err.decode().strip()[-500:]}")


def _copy_split(source, table, layout, lo, hi, target, appname, done):
    try:
        _copy_batch(source, table, layout, lo, hi, target, appname)
        done.append((lo, hi))
    except BatchTimeout as exc:
        half = (hi - lo) / 2
        if half < FLOOR:
            raise CloneStopped(f"batch {_ts(lo)}..{_ts(hi)} still hits the 30 s statement timeout at the "
                               f"1-minute floor; stopped. public.{target} holds the batches before it.") from exc
        mid = lo + half
        _copy_split(source, table, layout, lo, mid, target, appname, done)
        _copy_split(source, table, layout, mid, hi, target, appname, done)


def run(prop, *, go, confirmed_size=False, pause=2.0):
    """Clone the proposal's slice into its new public table, batch by batch."""
    if not go:
        raise Refused("a prod clone needs Ryan's go for this request")
    source, table, target = prop["source"], prop["table"], prop["target"].removeprefix("public.")
    _check_source(source, prop.get("explicit_nodes", False))
    if target_exists(target):
        raise Refused(f"public.{target} already exists; a clone never writes into an existing table")
    nbytes = size(source, table, prop["since"], prop["until"])
    if nbytes > LIMIT and not confirmed_size:
        raise TooBig(table, nbytes)
    layout = source_layout(source, table)
    plan = batches(prop["since"], prop["until"], prop["batch"], layout["interval"])
    ok, detail = explain_ok(source, table, layout, *plan[0])
    if not ok:
        raise Refused(detail)
    create_target(target, layout)
    appname = f"sd-clone-{slug(target)}"[:63]
    done = []
    for i, (lo, hi) in enumerate(plan):
        _copy_split(source, table, layout, lo, hi, target, appname, done)
        if pause and i + 1 < len(plan):
            time.sleep(pause)
    return {"target": f"public.{target}", "batches": len(done), "bytes_on_source": nbytes, "explain": detail,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


_WRITES = re.compile(r"^\s*(set|reset|insert|update|delete|truncate|create|alter|drop|grant|revoke|vacuum|analyze|"
                     r"copy|call|do|refresh|cluster|reindex|lock|begin|start|commit|rollback|select\s+.*\binto\b)\b",
                     re.I | re.S)


def probe(source, sql, *, analyze_approved=False, explicit_nodes=False):
    """Run one read-only statement on prod as plain EXPLAIN unless told otherwise."""
    _check_source(source, explicit_nodes)
    stmt = sql.strip().rstrip(";").strip()
    if ";" in stmt:
        raise Refused("one statement per probe")
    if re.search(r"\bset\s+transaction\b", stmt, re.I) or _WRITES.match(stmt):
        raise Refused(f"probes are read-only SELECTs: {stmt[:80]}")
    if re.match(r"^explain\b", stmt, re.I):
        if re.match(r"^explain\s*(\(|\s)[^)]*\banalyze\b", stmt, re.I) and not analyze_approved:
            raise Refused("EXPLAIN ANALYZE executes the query on prod; it needs its own go")
    else:
        stmt = f"EXPLAIN {stmt}"
    return _prod(source, stmt, "sd-probe")


def _expose(schema, name, target):
    from sd import scratch

    scratch.expose(scratch.connect(), schema, name, target)


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(prog="clone")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("propose", "run"):
        c = sub.add_parser(name)
        c.add_argument("--source", required=True)
        c.add_argument("--table", required=True)
        c.add_argument("--since", required=True, type=datetime.fromisoformat)
        c.add_argument("--until", required=True, type=datetime.fromisoformat)
        c.add_argument("--batch", type=int, default=60, help="minutes per batch")
        c.add_argument("--target", required=True, help="new table name in public")
        c.add_argument("--explicit-nodes", action="store_true", help="Ryan named a node other than tsdb2")
        if name == "run":
            c.add_argument("--go", action="store_true", help="Ryan said go for this clone")
            c.add_argument("--confirm-size", action="store_true", help="Ryan agreed to more than 70 GB")
            c.add_argument("--expose-in", help="scratch schema to expose the clone in under the table's name")
    pr = sub.add_parser("probe")
    pr.add_argument("--source", default="tsdb2")
    pr.add_argument("--analyze-approved", action="store_true")
    pr.add_argument("--explicit-nodes", action="store_true")
    pr.add_argument("-c", "--command", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "probe":
        print(probe(args.source, args.command, analyze_approved=args.analyze_approved,
                    explicit_nodes=args.explicit_nodes), end="")
        return
    prop = proposal(args.source, args.table, since=args.since, until=args.until,
                    batch=timedelta(minutes=args.batch), target=args.target, explicit_nodes=args.explicit_nodes)
    if args.cmd == "propose":
        print(json.dumps(prop, indent=2, default=str))
        return
    if not args.go:
        raise SystemExit("a prod clone runs only with --go, after Ryan said go for this clone")
    result = run(prop, go=True, confirmed_size=args.confirm_size)
    if args.expose_in:
        _expose(args.expose_in, args.table, prop["target"].removeprefix("public."))
    print(json.dumps(result, indent=2, default=str))
