"""Who is using a shared-dev compose project.

A claim file per project records the session, branch, schemas and run dir
that teardown needs, so a run left behind by a dead session can still be
cleaned up.

Usage: python -I run.py claim pick BRANCH SESSION
       python -I run.py claim state PROJECT
"""

import json
import sys
from datetime import datetime, timezone

from sd.common import STATE, run, slug

BASE = "kiyotaka-shared-dev"
OFFSET_STEP = 1000


def _path(project):
    return STATE / f"claim-{project}.json"


def containers(project):
    """Names of running containers in the compose project."""
    out = run(["docker", "ps", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}"],
              timeout=20).stdout
    return [line for line in out.splitlines() if line]


def read(project):
    path = _path(project)
    return json.loads(path.read_text()) if path.exists() else None


def write(project, *, session, branch, worktrees, schemas, run_dir, **extra):
    STATE.mkdir(parents=True, exist_ok=True)
    record = {"project": project, "session": session, "branch": branch, "worktrees": list(worktrees),
              "schemas": list(schemas), "run_dir": str(run_dir),
              "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
    _path(project).write_text(json.dumps(record, indent=2) + "\n")
    return _path(project)


def update(project, **fields):
    record = read(project)
    if record is None:
        raise SystemExit(f"no claim for {project}")
    record.update(fields)
    _path(project).write_text(json.dumps(record, indent=2) + "\n")


def release(project):
    _path(project).unlink(missing_ok=True)


def state(project, session=None):
    """free, ours, live, stale (claim but no containers) or unclaimed (containers but no claim)."""
    record = read(project)
    if record and session and record["session"] == session:
        return "ours"
    running = bool(containers(project))
    if record:
        return "live" if running else "stale"
    return "unclaimed" if running else "free"


def pick(branch, session):
    """Choose the project, port offset and Kafka prefix for this run."""
    base_state = state(BASE, session)
    if base_state in ("free", "stale", "ours", "unclaimed"):
        return {"project": BASE, "offset": 0, "prefix": "dev.ryan.", "state": base_state,
                "other": read(BASE) if base_state == "stale" else None}
    used = {r.get("offset") for r in (json.loads(p.read_text()) for p in STATE.glob("claim-*.json"))}
    offset = next(n * OFFSET_STEP for n in range(1, 100) if n * OFFSET_STEP not in used)
    name = slug(branch)
    return {"project": f"{BASE}-{name}", "offset": offset, "prefix": f"dev.ryan.{name}.", "state": "live",
            "other": read(BASE)}


def main(argv):
    if argv[:1] == ["pick"] and len(argv) == 3:
        out = pick(argv[1], argv[2])
    elif argv[:1] == ["state"] and len(argv) == 2:
        out = {"project": argv[1], "state": state(argv[1]), "claim": read(argv[1])}
    else:
        sys.exit(__doc__)
    json.dump(out, sys.stdout, indent=2)
    print()
