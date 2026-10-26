"""What a worktree changed against its default branch.

Usage: python -I -m sd.scope WORKTREE... > scope.json
"""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sd.common import run


@dataclass
class Change:
    repo: str
    worktree: Path
    branch: str
    head: str
    base: str
    base_sha: str
    files: list
    uncommitted: bool


def _git(wt, *args):
    return run(["git", "-C", str(wt), *args], timeout=60).stdout.strip()


def _default_base(wt):
    found = run(["git", "-C", str(wt), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], timeout=30, check=False)
    if found.returncode == 0 and found.stdout.strip():
        return found.stdout.strip()
    for ref in ("origin/main", "origin/master"):
        if run(["git", "-C", str(wt), "rev-parse", "--verify", "--quiet", ref], timeout=30, check=False).returncode == 0:
            return ref
    raise SystemExit(f"{wt}: no origin/HEAD, origin/main or origin/master")


def _dirty_files(wt):
    out = run(["git", "-C", str(wt), "status", "--porcelain=v1", "-z", "-uall"], timeout=60).stdout
    entries = out.split("\0")
    files, i = [], 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        files.append(entry[3:])
        if entry[0] in "RC":
            i += 1  # the rename source follows
    return files


def changes(worktree):
    wt = Path(_git(Path(worktree), "rev-parse", "--show-toplevel"))
    origin = run(["git", "-C", str(wt), "remote", "get-url", "origin"], timeout=30, check=False).stdout.strip()
    repo = Path(origin.rstrip("/")).name.removesuffix(".git") if origin else wt.name
    base = _default_base(wt)
    base_sha = _git(wt, "merge-base", "HEAD", base)
    committed = _git(wt, "diff", "--name-only", base_sha, "HEAD").splitlines()
    dirty = _dirty_files(wt)
    return Change(
        repo=repo,
        worktree=wt,
        branch=_git(wt, "branch", "--show-current") or "HEAD",
        head=_git(wt, "rev-parse", "HEAD"),
        base=base,
        base_sha=base_sha,
        files=sorted(set(committed) | set(dirty)),
        uncommitted=bool(dirty),
    )


def main(argv):
    out = [{**asdict(c), "worktree": str(c.worktree)} for c in map(changes, argv)]
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
