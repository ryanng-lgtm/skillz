"""Build the binaries a run needs: from session worktrees, or from main.

Main builds are cached by commit; worktree builds go into the run dir.
Each binary gets a provenance JSON next to it.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sd.common import SHARED_DEV, run
from sd.plan import MAP

BUILD_SH = Path(__file__).resolve().parents[1] / "build.sh"
BIN_ROOT = SHARED_DEV / "bin"
SRC_CACHE = Path.home() / ".cache" / "shared-dev" / "src"
IMAGE = "golang:1.27-alpine"


def _git(repo, *args, timeout=120):
    return run(["git", "-C", str(repo), *args], timeout=timeout).stdout.strip()


def _build(src, service, out, replace=None):
    binary = MAP["binaries"][service]
    cmd = ["bash", str(BUILD_SH), "--src", str(src), "--pkg", binary["pkg"], "--out", str(out), "--image", IMAGE]
    for module, path in (replace or {}).items():
        cmd += ["--replace", f"{module}={path}"]
    run(cmd, timeout=2400)


def _provenance(out, *, repo, source, worktree, head, uncommitted, replace=None):
    record = {
        "repo": repo,
        "source": source,
        "worktree": str(worktree),
        "head": head,
        "uncommitted": uncommitted,
        "sha256": hashlib.sha256(Path(out).read_bytes()).hexdigest(),
        "image": IMAGE,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if replace:
        record["replace"] = replace
    Path(out).with_name(Path(out).name + ".json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def worktree_build(change, service, run_dir, replace=None):
    """Build service's binary from the session worktree into run_dir/bin."""
    name = MAP["binaries"][service]["name"]
    out = Path(run_dir) / "bin" / name
    if out.exists() and out.with_name(name + ".json").exists():
        return out  # services sharing a binary build it once per run
    out.parent.mkdir(parents=True, exist_ok=True)
    _build(change.worktree, service, out, replace)
    dirty = bool(_git(change.worktree, "status", "--porcelain", "--untracked-files=normal"))
    _provenance(out, repo=change.repo, source="worktree", worktree=change.worktree,
                head=_git(change.worktree, "rev-parse", "HEAD"), uncommitted=dirty, replace=replace)
    return out


def main_build(repo_clone, service, *, run_dir=None, replace=None):
    """Build service's binary from freshly fetched origin/<default>.

    The source is a detached worktree under SRC_CACHE; the anchor clone's
    checkout is never touched. Without replace, the result is cached by commit.
    """
    repo_clone = Path(repo_clone)
    base = _git(repo_clone, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    remote, _, branch = base.partition("/")
    run(["git", "-C", str(repo_clone), "fetch", "--quiet", remote, branch], timeout=300)
    sha = _git(repo_clone, "rev-parse", base)
    name = MAP["binaries"][service]["name"]
    if replace:
        out = Path(run_dir) / "bin" / name
    else:
        out = BIN_ROOT / f"linux-arm64-main-{sha[:12]}" / name
        if out.exists():
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    repo = MAP["binaries"][service]["repo"]
    src = SRC_CACHE / f"{repo}-{sha[:12]}"
    if not src.exists():
        src.parent.mkdir(parents=True, exist_ok=True)
        _git(repo_clone, "worktree", "add", "--detach", str(src), sha, timeout=300)
    try:
        _build(src, service, out, replace)
    finally:
        _git(repo_clone, "worktree", "remove", "--force", str(src), timeout=120)
    _provenance(out, repo=repo, source="main", worktree=base, head=sha, uncommitted=False, replace=replace)
    return out
