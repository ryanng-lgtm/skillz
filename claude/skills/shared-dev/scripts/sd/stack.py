"""Bring a run's compose project up and down, and tear a run down completely.

Usage:
  python -I run.py stack up --compose F --project P SERVICE...
  python -I run.py stack status --project P
  python -I run.py stack down [--project P]
  python -I run.py stack run-once --compose F --project P [--service S] [--timeout N] -- GATEWAY ARGS...
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from sd import claim, meta, scratch, topics
from sd.common import Stuck, run


def _compose(project, compose=None):
    cmd = ["docker", "compose", "-p", project]
    return cmd + (["-f", str(compose)] if compose else [])


def up(compose, project, services):
    proc = run([*_compose(project, compose), "up", "-d", "--wait", "--wait-timeout", "120", *services],
               timeout=300, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"compose up failed for {project}:\n{proc.stderr[-3000:]}")


def status(project):
    out = run([*_compose(project), "ps", "--all", "--format", "json"], timeout=30).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def run_once(compose, project, service, args, timeout):
    """docker compose run --rm --no-deps for cjobs and other one-off gateway commands."""
    return run([*_compose(project, compose), "run", "--rm", "--no-deps", service, "/shared-dev/tsdb-gateway",
                "-c", "/config.yaml", "-s", "/schema.yaml", *args], timeout=timeout, check=False)


def down(project, compose=None):
    """Stop and remove the project's containers; return what could not be done."""
    try:
        proc = run([*_compose(project, compose), "down", "--remove-orphans"], timeout=120, check=False)
    except Stuck:
        return [f"docker compose down for {project} timed out; containers may still run "
                f"(docker ps --filter label=com.docker.compose.project={project})"]
    if proc.returncode != 0:
        return [f"docker compose down for {project} failed: {proc.stderr.strip()[-500:]}"]
    return []


def teardown(project):
    """Every teardown step runs even when an earlier one fails; returns the leftovers.

    The claim is released only when the database steps succeeded, so a
    schema that could not be dropped stays findable by the next run.
    """
    record = claim.read(project) or {}
    leftovers = down(project, record.get("compose"))
    db_ok = True
    schemas = record.get("schemas", [])
    if schemas:
        try:
            conn = scratch.connect()
            for schema in schemas:
                scratch.drop_schema(conn, schema)
        except Exception as exc:  # noqa: BLE001 - every step runs, failures are reported
            db_ok = False
            leftovers.append(f"could not drop {', '.join(schemas)}: {type(exc).__name__}: {exc}")
    m = record.get("meta")
    if m and m.get("branch"):
        try:
            meta.rollback(meta.connect(), m["branch"], Path(m["dir"]), to=m["before"])
        except Exception as exc:  # noqa: BLE001
            db_ok = False
            leftovers.append(f"could not roll back meta_ryan {m['branch']} to {m['before']}: {type(exc).__name__}: {exc}")
    if record.get("run_dir"):
        shutil.rmtree(Path(record["run_dir"]) / "config", ignore_errors=True)
    for topic in record.get("topics", []):
        try:
            topics.delete(project, topic)
        except BaseException as exc:  # noqa: BLE001 - SystemExit included; every step runs
            leftovers.append(f"could not delete topic {topic}: {exc}")
    if db_ok:
        claim.release(project)
    return leftovers


def main(argv):
    ap = argparse.ArgumentParser(prog="stack")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("up")
    u.add_argument("--compose", required=True)
    u.add_argument("--project", required=True)
    u.add_argument("services", nargs="+")
    s = sub.add_parser("status")
    s.add_argument("--project", default=claim.BASE)
    d = sub.add_parser("down")
    d.add_argument("--project", default=claim.BASE)
    r = sub.add_parser("run-once")
    r.add_argument("--compose", required=True)
    r.add_argument("--project", required=True)
    r.add_argument("--service", default="tsdb-registry")
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("args", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.cmd == "run-once":
        extra = args.args[1:] if args.args[:1] == ["--"] else args.args
        proc = run_once(args.compose, args.project, args.service, extra, args.timeout)
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        sys.exit(proc.returncode)
    if args.cmd == "up":
        up(args.compose, args.project, args.services)
    elif args.cmd == "status":
        json.dump(status(args.project), sys.stdout, indent=2)
        print()
    else:
        leftovers = teardown(args.project)
        for line in leftovers:
            print(f"leftover: {line}")
        print("teardown complete" if not leftovers else "teardown finished with leftovers")
        sys.exit(1 if leftovers else 0)
