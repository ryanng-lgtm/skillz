"""Turn worktree changes into the services, builds and data a run needs.

Usage: python -I -m sd.plan scope.json > plan.json
"""

import json
import re
import sys
from pathlib import Path, PurePosixPath

from sd.scope import Change

MAP = json.loads(Path(__file__).with_name("service_map.json").read_text())
REPOS = Path.home() / "Documents" / "GitLab" / "meta_repo"
DATA_ORDER = ["live", "api", "clones"]
# Measured: metadata-instrument holds the catalog (~950 MiB); tsdb-registry was
# OOM-killed at 2g and runs at 4g; the rest stay well under 512 MiB.
MEMORY_MIB = {"metadata-instrument": 1024, "tsdb-registry": 3072}
DEFAULT_MIB = 512


def _rule_for(repo, path):
    for rule in MAP["rules"].get(repo, []):
        if any(PurePosixPath(path).full_match(glob) for glob in rule["globs"]):
            return rule
    return None


def _venue(files):
    """Return the longest venue named by a path component, file stem or branch."""
    words = set()
    for f in files:
        for part in PurePosixPath(f).parts:
            words.update(w.replace("_", "") for w in re.split(r"[._-]", part.lower()) if w)
            words.add(part.lower().replace("_", "").split(".")[0])
    names = [v for v in MAP["venues"] if v.replace("_", "") in words]
    return max(names, key=len) if names else None


def _consumers(module, repos):
    """Repos with a rule whose go.mod requires module."""
    pattern = re.compile(rf"^\s*(require\s+)?{re.escape(module)}\s+v", re.M)
    out = []
    for repo in MAP["rules"]:
        gomod = repos / repo / "go.mod"
        if gomod.is_file() and pattern.search(gomod.read_text()):
            out.append(repo)
    return out


def _with_deps(services):
    ordered, seen = [], set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        for dep in MAP["deps"][name]:
            visit(dep)
        ordered.append(name)

    for name in sorted(services, key=MAP["order"].index):
        visit(name)
    return ordered


def plan(changes, *, fe=False, only=None, repos=REPOS):
    if only:
        changes = [c for c in changes if c.repo in only] or changes
    worktrees = {c.repo: str(c.worktree) for c in changes}
    services, data, unmapped = set(), set(), []
    migrations = {"tsdb": False, "meta": False}
    cjob, capture_files, capture = False, [], None
    replace = {}  # consumer repo -> {module: library worktree}

    def apply(rule, files, branch):
        nonlocal cjob, capture
        services.update(rule["services"])
        data.update(rule["data"])
        if rule.get("migrations"):
            migrations[rule["migrations"]] = True
        cjob = cjob or rule.get("cjob", False)
        if rule.get("capture"):
            capture_files.extend([*files, branch])
            capture = {}

    for c in changes:
        if c.repo in MAP["libraries"]:
            module = MAP["libraries"][c.repo]
            for consumer in _consumers(module, repos):
                apply(MAP["rules"][consumer][-1], c.files, c.branch)
                replace.setdefault(consumer, {})[module] = str(c.worktree)
            continue
        for f in c.files:
            rule = _rule_for(c.repo, f)
            if rule is None or rule.get("skip"):
                unmapped.append(f"{c.repo}/{f}")
            else:
                apply(rule, [f], c.branch)

    if only:
        named = [s for s in only if s in MAP["binaries"]]
        if named:
            services &= set(named)
    ordered = _with_deps(services)

    builds = {}
    for service in ordered + (["tsdb-registry"] if cjob and "tsdb-registry" not in ordered else []):
        repo = MAP["binaries"][service]["repo"]
        builds[service] = {
            "repo": repo,
            "source": "worktree" if repo in worktrees else "main",
            "worktree": worktrees.get(repo),
        }
        if repo in replace:
            builds[service]["replace"] = replace[repo]

    if capture is not None:
        capture = {"venue": _venue(capture_files)}

    return {
        "need_mib": sum(MEMORY_MIB.get(svc, DEFAULT_MIB) for svc in ordered),
        "services": ordered,
        "builds": builds,
        "data": [d for d in DATA_ORDER if d in data],
        "migrations": migrations,
        "cjob": cjob,
        "capture": capture,
        "fe": fe,
        "unmapped": unmapped,
    }


def main(argv):
    raw = json.loads(Path(argv[0]).read_text())
    changes = [Change(**{**c, "worktree": Path(c["worktree"])}) for c in raw]
    json.dump(plan(changes, fe="--fe" in argv), sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
