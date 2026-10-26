"""Bring a run up: claim, builds, scratch schema, meta_ryan, compose, start.

Each step that needs Ryan exits with its own code and a message saying why;
the claim is written first, so `stack down` can clean up a run that stopped
part way.

Exit codes: 3 an unclaimed stack is running; 4 a copy is over 70 GB;
5 public is behind main; 6 a capture needs a venue and symbols.

Usage:
  python -I run.py up --scope scope.json --plan plan.json --run-dir DIR --session ID
                      [--symbols A,B] [--venue V] [--seconds N] [--confirm-size]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from sd import builds, capture, claim, compose, meta, scratch, stack
from sd.capture import DEFAULT_SECONDS
from sd.common import STATE, schema_name, slug
from sd.migrations import delta, export_dir, parse_dir, scan
from sd.plan import MAP, REPOS
from sd.scope import Change


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _gateway_build(p, binaries, schemas):
    for service, b in p["builds"].items():
        if b["repo"] == "tsdb-gateway" and b["source"] == "worktree":
            return binaries[service], schemas[service]
    raise Stop(5, "the plan has tsdb migrations but no tsdb-gateway worktree build")


def _main_delta(repos, run_dir):
    """Main's tsdb-gateway migrations that public lacks."""
    base = json.loads((STATE / "public-baseline.json").read_text())
    main_dir = export_dir(repos / "tsdb-gateway", "origin/main", Path(run_dir) / "tsdb-main-migrations")
    return delta(set(base["versions"]), parse_dir(main_dir), {})[0]


def _tsdb_delta(conn, change, p, binaries, schemas, run_dir, password, schema, copies, budget, repos):
    """Apply the branch's own migrations into schema; returns (copies, warnings)."""
    base = json.loads((STATE / "public-baseline.json").read_text())
    main_dir = export_dir(repos / "tsdb-gateway", "origin/main", Path(run_dir) / "tsdb-main-migrations")
    branch_dir = Path(change.worktree) / "migrations"
    main, branch = parse_dir(main_dir), parse_dir(branch_dir)
    main_delta, branch_delta = delta(set(base["versions"]), main, branch)
    if main_delta:
        raise Stop(5, f"public is {len(main_delta)} migrations behind main ({main_delta[0]}..{main_delta[-1]}); "
                      "run `run.py rebaseline plan` and ask Ryan before `rebaseline apply --yes`")
    warnings = []
    if not branch_delta:
        scratch.create_schema(conn, schema)
        for table, mode in copies.items():
            scratch.copy_object(conn, table, schema, mode=mode, budget=budget)
        return copies, warnings
    sources = {v: branch_dir / f"{branch[v]}.up.sql" for v in branch_delta}
    for v in branch_delta:
        found = scan(sources[v].read_text())
        warnings += [f"{v}: {d} (runs on a scratch copy)" for d in found["destructive"]]
        for table in sorted(found["touched"] | found["cagg_sources"]):
            if table not in copies and conn.execute("SELECT to_regclass(%s) IS NOT NULL",
                                                    (f"public.{table}",)).fetchone()[0]:
                copies[table] = "full"
    gateway, schema_yaml = _gateway_build(p, binaries, schemas)
    copies = scratch.apply_with_copies(conn, schema, branch_delta, sources, gateway, password, run_dir,
                                       copies=copies, budget=budget, schema_yaml=schema_yaml)
    return copies, warnings


def _branch_indexes(conn, gateway, main_schema_yaml, branch_schema_yaml, password, run_dir, schema, copies, budget):
    """Build the branch's extra schema-yaml indexes on scratch copies; return main's index gaps."""
    found = scratch.index_plan(gateway, main_schema_yaml, branch_schema_yaml, password, run_dir, schema)
    guard = scratch.connect(scratch.guard_url(password, [schema]))
    for ddl in found["branch_only"]:
        m = re.search(r'ON\s+(?:ONLY\s+)?"?[\w]+"?\.("?)(\w+)\1', ddl, re.I)
        if m and m.group(2) not in copies:
            scratch.copy_object(conn, m.group(2), schema, mode="full", budget=budget)
            copies[m.group(2)] = "full"
        guard.execute(ddl)
    guard.close()
    return found["main_missing"]


def up(scope_path, plan_path, run_dir, session, *, symbols=(), venue=None, seconds=DEFAULT_SECONDS,
       confirm_size=False, repos=REPOS):
    changes = [Change(**{**c, "worktree": Path(c["worktree"])}) for c in json.loads(Path(scope_path).read_text())]
    p = json.loads(Path(plan_path).read_text())
    run_dir = Path(run_dir)
    by_repo = {c.repo: c for c in changes}
    built_repos = {b["repo"] for b in p["builds"].values() if b["source"] == "worktree"}
    branch = next((c.branch for c in changes if c.repo in built_repos), changes[0].branch)

    if p["capture"] is not None:
        venue = venue or p["capture"]["venue"]
        if not venue or not symbols:
            raise Stop(6, "a live capture needs --venue (none found in the change) and --symbols (the branch's "
                          "symbols, else two or three liquid ones)")

    if any(MAP["binaries"][svc]["repo"] == "tsdb-gateway" for svc in p["builds"]):
        # Gateway code from main or a branch off it expects main's schema, migrations or not.
        behind = _main_delta(repos, run_dir)
        if behind:
            raise Stop(5, f"public is {len(behind)} migrations behind main ({behind[0]}..{behind[-1]}); run "
                          "`run.py rebaseline plan` and ask Ryan before `rebaseline apply --yes`")

    picked = claim.pick(branch, session)
    if picked["state"] == "unclaimed":
        raise Stop(3, f"{picked['project']} has running containers and no claim (started by hand, or by a session "
                      "older than the skill). Ask Ryan before touching it.")
    project, offset, prefix = picked["project"], picked["offset"], picked["prefix"]
    schema = schema_name(branch)
    compose_path = run_dir / "compose.json"
    claim.write(project, session=session, branch=branch, worktrees=[str(c.worktree) for c in changes],
                schemas=[schema], run_dir=str(run_dir), offset=offset, prefix=prefix, compose=str(compose_path))

    binaries, schemas = {}, {}
    for service, b in p["builds"].items():
        if b["source"] == "worktree":
            out = builds.worktree_build(by_repo[b["repo"]], service, run_dir, replace=b.get("replace"))
        else:
            out = builds.main_build(repos / b["repo"], service, run_dir=run_dir, replace=b.get("replace"))
        binaries[service] = out
        if MAP["binaries"][service]["name"] == "tsdb-gateway":
            schemas[service] = builds.schema_for(out)

    cap = None
    if p["capture"] is not None:
        cap = capture.plan_capture(venue, list(symbols), seconds, binaries["streamd"], prefix, run_dir)

    conn = scratch.connect()
    password = scratch.ensure_guard(conn)
    budget = scratch.Budget(limit=float("inf") if confirm_size else scratch.LIMIT)
    copies = {t: "empty" for t in (cap or {}).get("tables", [])}
    warnings, index_gaps = [], []
    try:
        if p["migrations"]["tsdb"]:
            copies, warnings = _tsdb_delta(conn, by_repo["tsdb-gateway"], p, binaries, schemas, run_dir, password,
                                           schema, copies, budget, repos)
        else:
            scratch.create_schema(conn, schema)
            for table, mode in copies.items():
                scratch.copy_object(conn, table, schema, mode=mode, budget=budget)
    except scratch.TooBig as exc:
        raise Stop(4, f"{exc}. Ask Ryan; re-run with --confirm-size only after he agrees.") from exc

    main_reader = None
    if p["migrations"]["tsdb"] and "tsdb-read" in p["services"]:
        main_bin = builds.main_build(repos / "tsdb-gateway", "tsdb-read")
        main_reader = (main_bin, "public", builds.schema_for(main_bin))
        gateway, branch_yaml = _gateway_build(p, binaries, schemas)
        try:
            index_gaps = _branch_indexes(conn, gateway, main_reader[2], branch_yaml, password, run_dir, schema,
                                         copies, budget)
        except scratch.TooBig as exc:
            raise Stop(4, f"{exc}. Ask Ryan; re-run with --confirm-size only after he agrees.") from exc
        except Exception as exc:  # noqa: BLE001 - index parity is reported, not fatal
            warnings.append(f"index comparison skipped: {type(exc).__name__}: {str(exc)[:300]}")

    if p["migrations"]["meta"]:
        mconn = meta.connect()
        current = meta.check_clean(mconn)
        meta_main = export_dir(repos / "metadata-instrument", "origin/main", run_dir / "meta-main-migrations")
        meta_branch = Path(by_repo["metadata-instrument"].worktree) / "migrations"
        todo = meta.plan(current, parse_dir(meta_main), parse_dir(meta_branch))
        meta.apply(mconn, todo["catch_up"], meta_main)
        at_main = todo["catch_up"][-1] if todo["catch_up"] else current
        claim.update(project, meta={"before": at_main, "branch": todo["branch"], "dir": str(meta_branch)})
        meta.apply(mconn, todo["branch"], meta_branch)

    compose_path = compose.render(p, binaries, project=project, offset=offset, prefix=prefix, schema=schema,
                                  password=password, run_dir=run_dir, schemas=schemas, main_reader=main_reader,
                                  capture=cap)
    start = [s for s in p["services"] if s != "streamd"] + (["tsdb-read-main"] if main_reader else [])
    if start:
        stack.up(compose_path, project, start)

    summary = {
        "project": project, "offset": offset, "prefix": prefix, "schema": schema, "compose": str(compose_path),
        "services": start, "binaries": {s: str(b) for s, b in binaries.items()}, "copies": copies,
        "main_reader": main_reader is not None, "warnings": warnings, "index_gaps_vs_main": index_gaps,
        "capture": {"service": cap["service_name"], "venue": venue, "symbols": list(symbols), "seconds": seconds}
        if cap else None,
        "run_dir": str(run_dir), "session": session, "branch": branch, "slug": slug(branch),
    }
    (run_dir / "up.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv):
    ap = argparse.ArgumentParser(prog="up")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--venue")
    ap.add_argument("--seconds", type=int, default=DEFAULT_SECONDS)
    ap.add_argument("--confirm-size", action="store_true", help="Ryan agreed to copies over 70 GB")
    args = ap.parse_args(argv)
    Path(args.run_dir).mkdir(parents=True, exist_ok=True)
    try:
        summary = up(args.scope, args.plan, args.run_dir, args.session,
                     symbols=[s for s in args.symbols.split(",") if s], venue=args.venue, seconds=args.seconds,
                     confirm_size=args.confirm_size)
    except Stop as exc:
        print(f"stop: {exc}", file=sys.stderr)
        sys.exit(exc.code)
    json.dump(summary, sys.stdout, indent=2)
    print()
