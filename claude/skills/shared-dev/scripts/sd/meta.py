"""metadata-instrument migrations on meta_ryan, Ryan's own database.

meta_ryan sits on a shared Postgres instance (Sean's and Alex's databases
too), so nothing here touches roles, extensions or settings. A run brings
meta_ryan up to main, applies the branch's own migrations, and teardown
rolls those back so it ends at main.

Usage:
  python -I run.py meta apply --clone CLONE [--branch-worktree WT] [--main-ref origin/main]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from sd.common import load_env
from sd.migrations import export_dir, parse_dir


class ForeignVersion(Exception):
    def __init__(self, version):
        super().__init__(f"meta_ryan is at {version}, which is in neither main's nor the branch's migrations")
        self.version = version


class Dirty(Exception):
    pass


def connect():
    import psycopg

    return psycopg.connect(load_env()["METADATA_POSTGRES_URL"], autocommit=True, connect_timeout=10)


def version(conn):
    row = conn.execute("SELECT version, dirty FROM schema_migrations").fetchone()
    return int(row[0]), bool(row[1])


def check_clean(conn):
    current, dirty = version(conn)
    if dirty:
        raise Dirty(f"meta_ryan schema_migrations is dirty at {current}; a past migration failed. Ask Ryan.")
    return current


def plan(current, main, branch):
    """Main's migrations newer than current, then the branch's own."""
    if current not in main and current not in branch:
        raise ForeignVersion(current)
    return {
        "catch_up": sorted(v for v in main if v > current),
        "branch": sorted(set(branch) - set(main)),
    }


def _sql(d, v, direction):
    return (Path(d) / f"{parse_dir(d)[v]}.{direction}.sql").read_text()


def apply(conn, versions, dir):
    """Run each up file in its own transaction, ascending, recording the version."""
    for v in sorted(versions):
        body = _sql(dir, v, "up")
        with conn.transaction():
            conn.execute(body)
            conn.execute("UPDATE schema_migrations SET version = %s, dirty = false", (v,))


def rollback(conn, versions, dir, to):
    """Run each down file in its own transaction, descending, ending at version `to`."""
    ordered = sorted(versions, reverse=True)
    for i, v in enumerate(ordered):
        body = _sql(dir, v, "down")
        after = ordered[i + 1] if i + 1 < len(ordered) else to
        with conn.transaction():
            conn.execute(body)
            conn.execute("UPDATE schema_migrations SET version = %s, dirty = false", (after,))


def main(argv):
    ap = argparse.ArgumentParser(prog="meta")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--clone", required=True, help="metadata-instrument clone to read main's migrations from")
    a.add_argument("--branch-worktree")
    a.add_argument("--main-ref", default="origin/main")
    args = ap.parse_args(argv)

    conn = connect()
    current = check_clean(conn)
    with tempfile.TemporaryDirectory() as tmp:
        main_dir = export_dir(Path(args.clone), args.main_ref, Path(tmp) / "main")
        branch_dir = Path(args.branch_worktree) / "migrations" if args.branch_worktree else main_dir
        todo = plan(current, parse_dir(main_dir), parse_dir(branch_dir))
        apply(conn, todo["catch_up"], main_dir)
        apply(conn, todo["branch"], branch_dir)
    at_main = todo["catch_up"][-1] if todo["catch_up"] else current
    json.dump({"before": at_main, "branch": todo["branch"], "dir": str(branch_dir), "caught_up": todo["catch_up"]},
              sys.stdout)
    print()
