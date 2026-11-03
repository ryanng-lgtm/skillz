import json
import os
import re
import shutil
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


def stub_bin(root, *, file_says="ELF 64-bit LSB executable, ARM aarch64, statically linked", go=True):
    """Stub docker, go (unless go=False) and file; docker and go log their arguments, docker writes $STUB_OUT."""
    bin_dir = root / "stubbin"
    bin_dir.mkdir()
    log = root / "calls.log"
    (bin_dir / "docker").write_text(
        f'#!/bin/sh\necho "docker $*" >> {log}\n[ -n "$STUB_OUT" ] && printf fakebinary > "$STUB_OUT"\nexit 0\n'
    )
    if go:
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
    def run_build(self, root, src, out, file_says=None, extra=(), go=True, cwd=None):
        kwargs = {"file_says": file_says} if file_says else {}
        bin_dir, log = stub_bin(root, go=go, **kwargs)
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "STUB_OUT": str(out)}
        proc = subprocess.run(
            ["bash", str(BUILD_SH), "--src", str(src), "--pkg", "./cmd/tsdb-gateway", "--out", str(out), *extra],
            env=env, capture_output=True, text=True, cwd=cwd,
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

    def test_build_accepts_outside_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kiyotaka-go").mkdir()
            gomod = "module x\n\nreplace gitlab.com/x/kiyotaka-go => ../kiyotaka-go\n"
            src = make_repo(root, gomod=gomod)
            proc, calls = self.run_build(root, src, root / "out" / "tsdb-gateway")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("docker run", calls)
            self.assertEqual((src / "go.mod").read_text(), gomod)

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

    @unittest.skipUnless(shutil.which("go"), "needs a real go toolchain")
    def test_build_library_replace_from_outside_any_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lib = root / "lib"
            lib.mkdir()
            (lib / "go.mod").write_text("module a.com/lib\n\ngo 1.22\n")
            (lib / "lib.go").write_text("package lib\n\nfunc V() string { return \"lib\" }\n")
            gomod = "module x\n\ngo 1.22\n\nrequire a.com/lib v0.0.0\n"
            src = make_repo(root, gomod=gomod)
            (src / "main.go").write_text('package main\n\nimport "a.com/lib"\n\nfunc main() { println(lib.V()) }\n')
            proc, _ = self.run_build(root, src, root / "out" / "tsdb-gateway", go=False, cwd=root,
                                     extra=["--replace", f"a.com/lib={lib}"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((src / "vendor" / "a.com" / "lib" / "lib.go").exists())
            self.assertEqual((src / "go.mod").read_text(), gomod)


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
            self.assertFalse(cached.with_name("schema.yaml").exists())  # this repo has no schema.yaml

    def test_main_build_cache_hit_backfills_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clone = make_repo(root)
            (clone / "schema.yaml").write_text("tables: {}\n")
            git(clone, "add", ".")
            git(clone, "commit", "-m", "schema")
            git(clone, "push", "origin", "main")
            sha = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            cached = root / "bin" / f"linux-arm64-main-{sha[:12]}" / "tsdb-gateway"
            cached.parent.mkdir(parents=True)
            cached.write_text("cached")
            with patch.object(builds, "BIN_ROOT", root / "bin"):
                out = builds.main_build(clone, "tsdb-read")
            self.assertEqual(out.with_name("schema.yaml").read_text(), "tables: {}\n")

    def test_main_build_keeps_schema_beside_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clone = make_repo(root)
            (clone / "schema.yaml").write_text("tables: {}\n")
            git(clone, "add", ".")
            git(clone, "commit", "-m", "schema")
            git(clone, "push", "origin", "main")
            bin_dir, _ = stub_bin(root)
            sha = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            out_path = root / "bin" / f"linux-arm64-main-{sha[:12]}" / "tsdb-gateway"
            with patch.object(builds, "BIN_ROOT", root / "bin"), patch.object(builds, "SRC_CACHE", root / "src"), \
                    patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}", "STUB_OUT": str(out_path)}):
                out = builds.main_build(clone, "tsdb-read")
            self.assertEqual(out.with_name("schema.yaml").read_text(), "tables: {}\n")
            self.assertEqual(builds.schema_for(out), out.with_name("schema.yaml"))

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

    def test_provenance_records_outside_gomod_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kiyotaka-go").mkdir()
            work = make_repo(root)
            (work / "go.mod").write_text(
                "module x\n\nreplace (\n\tgitlab.com/x/kiyotaka-go => ../kiyotaka-go\n"
                "\tgitlab.com/x/lf v1.2.3 => ./submodules/live-feed\n)\n"
            )
            change = Change(repo="tsdb-gateway", worktree=work, branch="main", head="h" * 40, base="origin/main",
                            base_sha="b" * 40, files=["go.mod"], uncommitted=True)
            run_dir = root / "run"
            bin_dir, _ = stub_bin(root)
            out_path = run_dir / "bin" / "tsdb-gateway"
            with patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}", "STUB_OUT": str(out_path)}):
                out = builds.worktree_build(change, "tsdb-read", run_dir)
            prov = json.loads(out.with_name("tsdb-gateway.json").read_text())
            self.assertEqual(prov["replace"], {"gitlab.com/x/kiyotaka-go": str((root / "kiyotaka-go").resolve())})


if __name__ == "__main__":
    unittest.main()
