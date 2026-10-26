"""Bring `public` on `data` up to main once, as a step Ryan approves.

Ordinary runs never migrate `public`. When `public` has fallen behind main
(main's catch-up swaps views into public and rewrites registry rows, which a
scratch schema cannot hold), Ryan approves this one-time catch-up: prod has
already run these exact migrations, so the clones end up closer to prod.

Usage:
  python -I run.py rebaseline plan [--repo R]
  python -I run.py rebaseline apply --yes [--repo R] [--log FILE]
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from sd import builds, migrations, scratch
from sd.common import SHARED_DEV, STATE

REPO = Path.home() / "Documents" / "GitLab" / "meta_repo" / "tsdb-gateway"
APPLY_TIMEOUT = 4 * 3600  # registry is ~46M rows; caggs over trade


class Unsafe(Exception):
    pass


def plan(base, main):
    """What a catch-up would do, from the recorded baseline and main's migrations."""
    version, dirty = base["version"], base.get("dirty", False)
    if version not in main:
        raise Unsafe(f"public is at {version}, which main does not have; ask Ryan which branch it came from")
    have = set(base["versions"])
    force = max(v for v in have if v < version) if dirty else None
    current = force if dirty else version
    apply = sorted(set(main) - have)
    skipped = [v for v in apply if v <= current]
    if skipped:
        raise Unsafe(f"main has migrations numbered at or below public's version that public lacks: {skipped}; "
                     "golang-migrate up would skip them")
    return {"from": version, "dirty": dirty, "force": force, "apply": apply, "to": max(main)}


_NON_TX = re.compile(r"^\s*(begin|commit|rollback|start\s+transaction|vacuum)\b|\bconcurrently\b", re.I | re.M)


def transactional(sql):
    """True when a failed run of this file rolls back completely."""
    return not _NON_TX.search(re.sub(r"--[^\n]*", "", sql))


_CREATE = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?(?:materialized\s+view|table|view|function)\s+"
                     r"(?:if\s+not\s+exists\s+)?(?:public\.)?([a-z_][a-z_0-9]*)", re.I)


def created_objects(sql):
    return {m.group(1).lower() for m in _CREATE.finditer(sql)}


def _main_inputs(repo):
    gateway = builds.main_build(repo, "tsdb-registry")
    sha = json.loads(gateway.with_name(gateway.name + ".json").read_text())["head"]
    return gateway, sha


def _preflight(conn, todo, main_dir, main):
    others = conn.execute(
        """SELECT application_name, client_addr::text, state FROM pg_stat_activity
           WHERE datname = current_database() AND pid <> pg_backend_pid() AND backend_type = 'client backend'"""
    ).fetchall()
    if others:
        raise Unsafe(f"other sessions are connected to data: {others}; stop them first (or ask Ryan)")
    if todo["dirty"]:
        sql = (main_dir / f"{main[todo['from']]}.up.sql").read_text()
        if not transactional(sql):
            raise Unsafe(f"{todo['from']} has statements that commit on their own; a failed run may have left "
                         "part of it behind. Ask Ryan.")
        names = sorted(created_objects(sql))
        left = conn.execute("SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace "
                            "AND relname = ANY(%s)", (names,)).fetchall()
        if left:
            raise Unsafe(f"the dirty migration {todo['from']} left objects behind: {left}. Ask Ryan.")


def apply(repo=REPO, log=None):
    base = json.loads((STATE / "public-baseline.json").read_text())
    gateway, sha = _main_inputs(repo)
    schema_yaml = builds.schema_for(gateway)
    config = SHARED_DEV / "config" / "tsdb-gateway-writer.yaml"  # dev's own URL: this step does write public
    with tempfile.TemporaryDirectory() as tmp:
        main_dir = migrations.export_dir(repo, sha, Path(tmp) / "migrations")
        main = migrations.parse_dir(main_dir)
        todo = plan(base, main)
        conn = scratch.connect()
        _preflight(conn, todo, main_dir, main)
        steps = ([["-M", "/migrations", "migrate", "force", str(todo["force"])]] if todo["dirty"] else []) + \
                [["-M", "/migrations", "migrate", "up"]]
        out = []
        for args in steps:
            proc = scratch._gateway(gateway, config, schema_yaml, args, mounts=[(main_dir, "/migrations")],
                                    timeout=APPLY_TIMEOUT)
            out.append(scratch._redact(proc.stdout + proc.stderr))
            if proc.returncode != 0:
                if log:
                    Path(log).write_text("\n".join(out))
                raise SystemExit(f"{' '.join(args)} failed; public stays at its last good version:\n{out[-1][-3000:]}")
    version, dirty = conn.execute("SELECT version, dirty FROM public.schema_migrations").fetchone()
    if dirty or version != todo["to"]:
        raise SystemExit(f"after the catch-up public is at {version} (dirty={dirty}), expected {todo['to']}")
    found = migrations.baseline(repo, version, sha)
    found["versions"] = sorted(found["versions"])
    (STATE / "public-baseline.json").write_text(json.dumps(found, indent=2) + "\n")
    scratch.ensure_guard(conn)  # SELECT on the tables and views the catch-up created
    if log:
        Path(log).write_text("\n".join(out))
    return {**todo, "main_sha": sha, "now": version}


def main(argv):
    ap = argparse.ArgumentParser(prog="rebaseline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--repo", default=str(REPO))
    a = sub.add_parser("apply")
    a.add_argument("--repo", default=str(REPO))
    a.add_argument("--yes", action="store_true", help="Ryan approved this catch-up of public")
    a.add_argument("--log")
    args = ap.parse_args(argv)
    if args.cmd == "apply" and not args.yes:
        sys.exit("rebaseline apply changes public on data; it needs --yes after Ryan's approval")
    if args.cmd == "plan":
        base = json.loads((STATE / "public-baseline.json").read_text())
        gateway, sha = _main_inputs(Path(args.repo))
        with tempfile.TemporaryDirectory() as tmp:
            main = migrations.parse_dir(migrations.export_dir(Path(args.repo), sha, Path(tmp) / "m"))
        todo = plan(base, main)
        print(json.dumps({**todo, "apply_count": len(todo["apply"]), "main_sha": sha}, indent=2))
        return
    print(json.dumps(apply(Path(args.repo), args.log), indent=2))
