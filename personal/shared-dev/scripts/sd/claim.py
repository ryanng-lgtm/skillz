"""Who is using a shared-dev compose project.

A claim file per project records the session, branch, schemas and run dir
that teardown needs, so a run left behind by a dead session can still be
cleaned up.

Usage: python -I run.py claim pick BRANCH SESSION
       python -I run.py claim state PROJECT
       python -I run.py claim add-topic PROJECT TOPIC   (a topic this run created; teardown reports it)
"""

import json
import sys
from datetime import datetime, timezone

from sd.common import STATE, run, slug

BASE = "kiyotaka-shared-dev"
# Base host ports run 4000-19090; +20000 and +40000 clear them and each other
# (+1000 would put a second tsdb-read on the base live-feed's 5080).
OFFSET_STEP = 20000


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


def pick(branch, session, second=False):
    """Choose the project, port offset and Kafka prefix for this run.

    The base project when it is free (or stale, or this session's own);
    otherwise, or when Ryan asks for one (second=True), a project of the
    run's own on spare ports and its own Kafka prefix. The returned state is
    the chosen project's.
    """
    base_state = state(BASE, session)
    if not second and base_state in ("free", "stale", "ours", "unclaimed"):
        return {"project": BASE, "offset": 0, "prefix": "dev.ryan.", "state": base_state,
                "other": read(BASE) if base_state == "stale" else None}
    name = slug(branch)
    project = f"{BASE}-{name}"
    mine = read(project)
    if mine and mine.get("offset"):
        offset = mine["offset"]
    else:
        used = {r.get("offset") for r in (json.loads(p.read_text()) for p in STATE.glob("claim-*.json"))}
        offset = next((n * OFFSET_STEP for n in (1, 2) if n * OFFSET_STEP not in used), None)
    if offset is None:
        raise SystemExit("two extra shared-dev projects are already claimed; there is no free port range. Ask Ryan.")
    return {"project": project, "offset": offset, "prefix": f"dev.ryan.{name}.", "state": state(project, session),
            "other": read(BASE)}


def main(argv):
    if argv[:1] == ["pick"] and len(argv) == 3:
        out = pick(argv[1], argv[2])
    elif argv[:1] == ["add-topic"] and len(argv) == 3:
        topics = (read(argv[1]) or {}).get("topics", [])
        update(argv[1], topics=sorted(set(topics) | {argv[2]}))
        return
    elif argv[:1] == ["state"] and len(argv) == 2:
        out = {"project": argv[1], "state": state(argv[1]), "claim": read(argv[1])}
    else:
        sys.exit(__doc__)
    json.dump(out, sys.stdout, indent=2)
    print()
