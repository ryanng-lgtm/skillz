import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sd import builds
from sd.scope import Change

BUILD_SH = Path(__file__).parents[1] / "build.sh"


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def stub_bin(root, *, file_says="ELF 64-bit LSB executable, ARM aarch64, statically linked"):
    """Stub docker, go and file that log their arguments; docker writes $STUB_OUT."""
    bin_dir = root / "stubbin"
    bin_dir.mkdir()
    log = root / "calls.log"
    (bin_dir / "docker").write_text(
        f'#!/bin/sh\necho "docker $*" >> {log}\n[ -n "$STUB_OUT" ] && printf fakebinary > "$STUB_OUT"\nexit 0\n'
    )
    (bin_dir / "go").write_text(f'#!/bin/sh\necho "go $*" >> {log}\nexit 0\n')
    (bin_dir / "file").write_text(f'#!/bin/sh\necho "$1: {file_says}"\n')
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    return bin_dir, log


def make_repo(root, name="tsdb-gateway", gomod="module x\n"):
    origin = root / f"{name}.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    work = root / name
    subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
    git(work, "config", "user.email", "t@t")
    git(work, "config", "user.name", "t")
    (work / "go.mod").write_text(gomod)
    git(work, "add", ".")
    git(work, "commit", "-m", "base")
    git(work, "push", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return work


class BuildShTests(unittest.TestCase):
    def run_build(self, root, src, out, file_says=None, extra=()):
        kwargs = {"file_says": file_says} if file_says else {}
        bin_dir, log = stub_bin(root, **kwargs)
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "STUB_OUT": str(out)}
        proc = subprocess.run(
            ["bash", str(BUILD_SH), "--src", str(src), "--pkg", "./cmd/tsdb-gateway", "--out", str(out), *extra],
            env=env, capture_output=True, text=True,
        )
        calls = log.read_text() if log.exists() else ""
        return proc, calls

    def test_build_passes_cgo_and_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_repo(root)
            proc, calls = self.run_build(root, src, root / "out" / "tsdb-gateway")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            docker = next(line for line in calls.splitlines() if line.startswith("docker run"))
            self.assertIn("--platform linux/arm64", docker)
            self.assertIn("CGO_ENABLED=1", docker)
            self.assertIn("GOFLAGS=-mod=vendor", docker)
            self.assertIn("-buildvcs=false", docker)
            self.assertIn("go mod vendor", calls)

    def test_build_rejects_macho(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_repo(root)
            proc, _ = self.run_build(root, src, root / "out" / "tsdb-gateway", file_says="Mach-O 64-bit executable arm64")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Mach-O", proc.stderr)

    def test_build_refuses_outside_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            line = "replace gitlab.com/x/lib => ../../elsewhere/lib"
            src = make_repo(root, gomod=f"module x\n\n{line}\n")
            before = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True).stdout
            proc, calls = self.run_build(root, src, root / "out" / "tsdb-gateway")
            after = subprocess.run(["git", "-C", str(src), "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(line, proc.stderr)
            self.assertNotIn("docker", calls)
            self.assertEqual(before, after)

    def test_build_allows_replace_inside_src(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_repo(root, gomod="module x\n\nreplace gitlab.com/x/lf => ./submodules/live-feed\n")
            proc, _ = self.run_build(root, src, root / "out" / "tsdb-gateway")
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_build_library_replace_uses_modfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = make_repo(root)
            lib = root / "kiyotaka-go"
            lib.mkdir()
            out = root / "out" / "tsdb-gateway"
            proc, calls = self.run_build(root, src, out, extra=["--replace", f"gitlab.com/x/kiyotaka-go={lib}"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"-replace=gitlab.com/x/kiyotaka-go={lib}", calls)
            self.assertIn("-modfile=/out/.tsdb-gateway.mod", calls)
            self.assertEqual((src / "go.mod").read_text(), "module x\n")


class BuildsPyTests(unittest.TestCase):
    def test_main_build_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clone = make_repo(root)
            sha = subprocess.run(["git", "-C", str(clone), "rev-parse", "origin/main"], capture_output=True, text=True).stdout.strip()
            cached = root / "bin" / f"linux-arm64-main-{sha[:12]}" / "tsdb-gateway"
            cached.parent.mkdir(parents=True)
            cached.write_text("cached")
            bin_dir, log = stub_bin(root)
            with patch.object(builds, "BIN_ROOT", root / "bin"), patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}):
                out = builds.main_build(clone, "tsdb-read")
            self.assertEqual(out, cached)
            self.assertFalse(log.exists() and "docker" in log.read_text())

    def test_provenance_records_uncommitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = make_repo(root)
            (work / "dirty.go").write_text("package x\n")
            change = Change(repo="tsdb-gateway", worktree=work, branch="main", head="h" * 40, base="origin/main",
                            base_sha="b" * 40, files=["dirty.go"], uncommitted=True)
            run_dir = root / "run"
            bin_dir, _ = stub_bin(root)
            out_path = run_dir / "bin" / "tsdb-gateway"
            with patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}", "STUB_OUT": str(out_path)}):
                out = builds.worktree_build(change, "tsdb-read", run_dir)
            self.assertEqual(out, out_path)
            prov = json.loads(out.with_name("tsdb-gateway.json").read_text())
            self.assertIs(prov["uncommitted"], True)
            self.assertEqual(prov["source"], "worktree")
            self.assertRegex(prov["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(re.match(r"^[0-9a-f]{40}$", prov["head"]))


if __name__ == "__main__":
    unittest.main()
