"""Bring a run up: claim, builds, scratch schema, meta_ryan, compose, start.

Each step that needs Ryan exits with its own code and a message saying why;
the claim is written first, so `stack down` can clean up a run that stopped
part way.

Exit codes: 3 an unclaimed stack is running; 4 a copy is over 70 GB;
5 public is behind main; 6 a capture needs a venue and symbols; 7 plan.json
is inconsistent; 8 the previous run on the project did not tear down.

Usage:
  python -I run.py up --scope scope.json --plan plan.json --run-dir DIR --session ID
                      [--symbols A,B] [--venue V] [--seconds N] [--confirm-size]
                      [--patch SERVICE=FILE ...] [--allow-behind] [--second-project]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from sd import builds, capture, claim, compose, meta, scratch, stack
from sd.capture import DEFAULT_SECONDS
from sd.common import STATE, run, schema_name, slug
from sd.migrations import delta, export_dir, parse_dir, scan
from sd.plan import MAP, REPOS
from sd.scope import Change


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _gateway_build(p, binaries, schemas):
    """The branch's gateway build; a merged branch built from main uses that main build."""
    gateway = [(s, b) for s, b in p["builds"].items() if b["repo"] == "tsdb-gateway"]
    for service, b in sorted(gateway, key=lambda sb: sb[1]["source"] != "worktree"):
        return binaries[service], schemas[service]
    raise Stop(7, "the plan has tsdb migrations but builds no tsdb-gateway service; check plan.json")


def _main_delta(repos, run_dir):
    """Main's tsdb-gateway migrations that public lacks, from a freshly fetched origin."""
    clone = repos / "tsdb-gateway"
    ref = run(["git", "-C", str(clone), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], timeout=30).stdout.strip()
    run(["git", "-C", str(clone), "fetch", "--quiet", "origin", ref.partition("/")[2]], timeout=300)
    base = json.loads((STATE / "public-baseline.json").read_text())
    main_dir = export_dir(clone, ref, Path(run_dir) / "tsdb-main-migrations")
    return delta(set(base["versions"]), parse_dir(main_dir), {})[0]


def _skipped():
    """Migrations the catch-up marked applied without running (see rebaseline --skip)."""
    path = STATE / "public-baseline.json"
    return json.loads(path.read_text()).get("skipped", []) if path.exists() else []


def _missing_objects(repos, run_dir, versions):
    """Tables, views and functions main's missing migrations would create."""
    from sd.rebaseline import created_objects

    main_dir = Path(run_dir) / "tsdb-main-migrations"
    stems = parse_dir(main_dir)
    names = set()
    for v in versions:
        names |= created_objects((main_dir / f"{stems[v]}.up.sql").read_text())
    return sorted(names)


def _tsdb_delta(conn, change, p, binaries, schemas, run_dir, password, schema, copies, budget, repos,
                allow_behind=False):
    """Apply the branch's own migrations into schema; returns (copies, warnings)."""
    base = json.loads((STATE / "public-baseline.json").read_text())
    main_dir = export_dir(repos / "tsdb-gateway", "origin/main", Path(run_dir) / "tsdb-main-migrations")
    branch_dir = Path(change.worktree) / "migrations"
    main, branch = parse_dir(main_dir), parse_dir(branch_dir)
    main_delta, branch_delta = delta(set(base["versions"]), main, branch)
    if main_delta and not allow_behind:
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
       confirm_size=False, repos=REPOS, patches=None, allow_behind=False, second_project=False):
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

    early_warnings = []
    if any(MAP["binaries"][svc]["repo"] == "tsdb-gateway" for svc in p["builds"]):
        # Gateway code from main or a branch off it expects main's schema, migrations or not.
        behind = _main_delta(repos, run_dir)
        if behind and not allow_behind:
            raise Stop(5, f"public is {len(behind)} migrations behind main ({behind[0]}..{behind[-1]}); run "
                          "`run.py rebaseline plan` and ask Ryan before `rebaseline apply --yes`")
        if _skipped():
            early_warnings.append(f"public skipped migration(s) {_skipped()} in its catch-up (the dev DB's "
                                  "kiyotaka_toolkit was too old); their objects are missing and probes that "
                                  "read them are not valid")
        if behind:
            early_warnings.append(f"public is {len(behind)} migrations behind main ({behind[0]}..{behind[-1]}); "
                                  f"objects main has that public lacks: {', '.join(_missing_objects(repos, run_dir, behind))}")

    picked = claim.pick(branch, session, second=second_project)
    if picked["state"] == "unclaimed":
        raise Stop(3, f"{picked['project']} has running containers and no claim (started by hand, or by a session "
                      "older than the skill). Ask Ryan before touching it.")
    project, offset, prefix = picked["project"], picked["offset"], picked["prefix"]
    if picked["state"] in ("stale", "ours"):
        # A dead session's run (or this session's earlier one): clean it up before claiming again,
        # so its schemas, meta_ryan migrations and topics are not orphaned.
        leftovers = stack.teardown(project)
        if leftovers:
            raise Stop(8, f"the previous run on {project} did not tear down cleanly: {'; '.join(leftovers)}. "
                          "Ask Ryan.")
    schema = schema_name(branch)
    exposed = schema + "_x"  # views over prod clones made during the run; both readers search it
    compose_path = run_dir / "compose.json"
    claim.write(project, session=session, branch=branch, worktrees=[str(c.worktree) for c in changes],
                schemas=[schema, exposed], run_dir=str(run_dir), offset=offset, prefix=prefix,
                compose=str(compose_path))

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
                                           schema, copies, budget, repos, allow_behind)
        else:
            scratch.create_schema(conn, schema)
            for table, mode in copies.items():
                scratch.copy_object(conn, table, schema, mode=mode, budget=budget)
    except scratch.TooBig as exc:
        raise Stop(4, f"{exc}. Ask Ryan; re-run with --confirm-size only after he agrees.") from exc
    scratch.create_schema(conn, exposed)

    main_reader = None
    branch_reader = p["builds"].get("tsdb-read", {}).get("source") == "worktree"
    if "tsdb-read" in p["services"] and (branch_reader or p["migrations"]["tsdb"]):
        # Every reader probe runs against main too, on host ports +100.
        main_bin = builds.main_build(repos / "tsdb-gateway", "tsdb-read")
        main_reader = (main_bin, "public", builds.schema_for(main_bin))
    if main_reader and p["migrations"]["tsdb"]:
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
                                  capture=cap, exposed=exposed, patches=patches)
    start = [s for s in p["services"] if s != "streamd"] + (["tsdb-read-main"] if main_reader else [])
    if start:
        stack.up(compose_path, project, start)

    summary = {
        "project": project, "offset": offset, "prefix": prefix, "schema": schema, "exposed_schema": exposed,
        "compose": str(compose_path),
        "services": start, "binaries": {s: str(b) for s, b in binaries.items()}, "copies": copies,
        "main_reader": main_reader is not None, "warnings": early_warnings + warnings,
        "index_gaps_vs_main": index_gaps,
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
    ap.add_argument("--second-project", action="store_true",
                    help="run in a project of its own even though the base project is free or unclaimed")
    ap.add_argument("--allow-behind", action="store_true",
                    help="run while public is behind main (Ryan's call); the report lists what public lacks")
    ap.add_argument("--patch", action="append", default=[], metavar="SERVICE=FILE",
                    help="merge a JSON file of non-secret config keys into SERVICE's run config")
    args = ap.parse_args(argv)
    patches = {}
    for item in args.patch:
        service, _, path = item.partition("=")
        patches[service] = json.loads(Path(path).read_text())
    Path(args.run_dir).mkdir(parents=True, exist_ok=True)
    try:
        summary = up(args.scope, args.plan, args.run_dir, args.session,
                     symbols=[s for s in args.symbols.split(",") if s], venue=args.venue, seconds=args.seconds,
                     confirm_size=args.confirm_size, patches=patches, allow_behind=args.allow_behind,
                     second_project=args.second_project)
    except Stop as exc:
        print(f"stop: {exc}", file=sys.stderr)
        sys.exit(exc.code)
    json.dump(summary, sys.stdout, indent=2)
    print()
