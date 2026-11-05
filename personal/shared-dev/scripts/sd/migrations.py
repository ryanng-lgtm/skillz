"""golang-migrate directories: what `public` already has, what a run must add.

`public` on `data` is never migrated, so its migration state is fixed. Its
recorded version may exist only on some branch; the baseline is the set of
migrations in the commit that added that version, up to that version.

Usage: python -I run.py migrations baseline --repo REPO --version V [--dirty]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from sd.common import STATE, run

UP = re.compile(r"^(\d+)_(.+)\.up\.sql$")


class BaselineUnknown(Exception):
    def __init__(self, version):
        super().__init__(f"no commit in any branch adds migration {version}")
        self.version = version


def parse_dir(d):
    """Version -> file stem for the *.up.sql files directly in d."""
    out = {}
    for f in Path(d).iterdir():
        m = UP.match(f.name)
        if m and f.is_file():
            out[int(m.group(1))] = f.name.removesuffix(".up.sql")
    return out


def _versions_at(repo, ref):
    names = run(["git", "-C", str(repo), "ls-tree", "--name-only", f"{ref}:migrations"], timeout=60).stdout.split()
    return {int(m.group(1)) for m in map(UP.match, names) if m}


def baseline(repo, version, main_ref="origin/main", dirty=False):
    """The migrations `public` reflects, given its recorded version.

    A dirty version started and failed, so it is not counted as applied.
    """
    commits = run(["git", "-C", str(repo), "log", "--all", "--diff-filter=A", "--format=%H", "--",
                   f"migrations/{version}_*.up.sql"], timeout=120).stdout.split()
    if not commits:
        raise BaselineUnknown(version)
    commit = commits[0]
    merge_base = run(["git", "-C", str(repo), "merge-base", commit, main_ref], timeout=60).stdout.strip()
    versions = {v for v in _versions_at(repo, commit) if v < version or (v == version and not dirty)}
    return {
        "version": version,
        "dirty": dirty,
        "branch_commit": commit,
        "merge_base": merge_base,
        "versions": versions,
    }


def export_dir(repo, ref, out):
    """Write ref's migrations directory into out/ and return out."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", ref, "migrations"], capture_output=True,
                             check=True, timeout=120)
    subprocess.run(["tar", "-x", "-C", str(out), "--strip-components=1"], input=archive.stdout, check=True,
                   timeout=120)
    return out


def delta(base, main, branch):
    """(main's migrations missing from base, the branch's own missing ones)."""
    main_delta = sorted(set(main) - set(base))
    branch_delta = sorted(set(branch) - set(main) - set(base))
    return main_delta, branch_delta


_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_NAME = r'((?:"?[\w]+"?\.)?"?[\w]+"?)'
_TOUCH = [
    (re.compile(rf"\bALTER\s+(?:MATERIALIZED\s+VIEW|TABLE)\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?{_NAME}", re.I), None),
    (re.compile(rf"\bINSERT\s+INTO\s+{_NAME}", re.I), None),
    (re.compile(rf"(?<!\bDO\s)\bUPDATE\s+(?:ONLY\s+)?{_NAME}\s+SET\b", re.I), "UPDATE"),
    (re.compile(rf"\bDELETE\s+FROM\s+(?:ONLY\s+)?{_NAME}", re.I), "DELETE FROM"),
    (re.compile(rf"\bTRUNCATE\s+(?:TABLE\s+)?(?:ONLY\s+)?{_NAME}", re.I), "TRUNCATE"),
    (re.compile(rf"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?{_NAME}", re.I), "DROP TABLE"),
    (re.compile(rf"\bDROP\s+(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+EXISTS\s+)?{_NAME}", re.I), "DROP VIEW"),
    (re.compile(rf"\bREFRESH\s+MATERIALIZED\s+VIEW\s+(?:CONCURRENTLY\s+)?{_NAME}", re.I), None),
    (re.compile(rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\s+)?ON\s+(?:ONLY\s+)?{_NAME}", re.I), None),
    (re.compile(r"\b(?:add|remove)_\w+_policy\s*\(\s*'([^']+)'", re.I), None),
    (re.compile(r"\b(?:set_chunk_time_interval|refresh_continuous_aggregate|create_hypertable)\s*\(\s*'([^']+)'", re.I), None),
]
_ALTER_DROP = re.compile(rf"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?{_NAME}\s+[^;]*?\bDROP\b", re.I)
_CAGG = re.compile(r"\bCREATE\s+MATERIALIZED\s+VIEW\b[^;]*?timescaledb\.continuous[^;]*?\bAS\b([^;]*)", re.I)
_FROM = re.compile(rf"\b(?:FROM|JOIN)\s+(?:ONLY\s+)?{_NAME}", re.I)
_INTERNAL = ("_timescaledb", "timescaledb_", "information_schema", "pg_catalog")


def _norm(name):
    name = name.replace('"', "").lower()
    if name.startswith("public."):
        name = name[len("public."):]
    return None if name.startswith(_INTERNAL) else name


def scan(sql):
    """Best-effort: the tables a migration changes, its cagg sources, and destructive statements.

    The guard role is the enforcement; this only warns early and picks copies.
    """
    sql = _COMMENTS.sub(" ", sql)
    touched, destructive = set(), []
    for pattern, kind in _TOUCH:
        for m in pattern.finditer(sql):
            name = _norm(m.group(1))
            if name:
                touched.add(name)
                if kind:
                    destructive.append(f"{kind} {name}")
    for m in _ALTER_DROP.finditer(sql):
        name = _norm(m.group(1))
        if name:
            destructive.append(f"ALTER TABLE {name} DROP")
    sources = set()
    for body in _CAGG.finditer(sql):
        sources.update(n for n in (_norm(m.group(1)) for m in _FROM.finditer(body.group(1))) if n)
    return {"touched": touched, "cagg_sources": sources, "destructive": destructive}


def stage(versions, sources, out):
    """Copy versions' up/down files into out, plus a no-op baseline migration v0.

    golang-migrate's `up` needs the forced version to exist in the source dir,
    so the run forces v0 and then applies everything after it.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for v in versions:
        up = Path(sources[v])
        shutil.copy2(up, out / up.name)
        down = up.with_name(up.name.removesuffix(".up.sql") + ".down.sql")
        if down.exists():
            shutil.copy2(down, out / down.name)
    v0 = min(versions) - 1
    for direction in ("up", "down"):
        (out / f"{v0}_sd_baseline.{direction}.sql").write_text("SELECT 1;\n")
    return v0


def main(argv):
    ap = argparse.ArgumentParser(prog="migrations")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--repo", required=True)
    b.add_argument("--version", type=int, required=True)
    b.add_argument("--main-ref", default="origin/main")
    b.add_argument("--dirty", action="store_true", help="schema_migrations.dirty is true")
    args = ap.parse_args(argv)
    try:
        found = baseline(Path(args.repo), args.version, args.main_ref, args.dirty)
    except BaselineUnknown as exc:
        sys.exit(str(exc))
    found["versions"] = sorted(found["versions"])
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "public-baseline.json").write_text(json.dumps(found, indent=2) + "\n")
    print(json.dumps({k: v for k, v in found.items() if k != "versions"} | {"count": len(found["versions"])}))
