import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sd import scope


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class ScopeTests(unittest.TestCase):
    def test_changes_includes_uncommitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            origin = tmp / "tsdb-gateway.git"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
            work = tmp / "tsdb-gateway"
            subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
            git(work, "config", "user.email", "t@t")
            git(work, "config", "user.name", "t")
            (work / "README.md").write_text("base\n")
            git(work, "add", ".")
            git(work, "commit", "-m", "base")
            git(work, "push", "origin", "main")
            git(work, "remote", "set-head", "origin", "main")
            git(work, "switch", "-c", "feat/x")
            (work / "reader.go").write_text("package x\n")
            git(work, "add", ".")
            git(work, "commit", "-m", "feature")
            (work / "dirty.go").write_text("package x\n")

            change = scope.changes(work)

            self.assertEqual(change.repo, "tsdb-gateway")
            self.assertEqual(change.branch, "feat/x")
            self.assertEqual(change.base, "origin/main")
            self.assertIn("reader.go", change.files)
            self.assertIn("dirty.go", change.files)
            self.assertNotIn("README.md", change.files)
            self.assertIs(change.uncommitted, True)

            cli = subprocess.run(
                [sys.executable, "-I", str(Path(__file__).parents[1] / "run.py"), "scope", str(work)],
                cwd=tmp, capture_output=True, text=True, check=True,
            )
            self.assertEqual(json.loads(cli.stdout)[0]["branch"], "feat/x")


if __name__ == "__main__":
    unittest.main()
