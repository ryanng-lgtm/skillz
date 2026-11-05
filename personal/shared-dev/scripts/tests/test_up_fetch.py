import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sd import up


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class MainDeltaFetchTests(unittest.TestCase):
    def test_main_delta_sees_migrations_pushed_after_the_last_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "tsdb-gateway.git"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
            repos = root / "repos"
            clone = repos / "tsdb-gateway"
            subprocess.run(["git", "clone", str(origin), str(clone)], check=True, capture_output=True)
            for d in (clone,):
                git(d, "config", "user.email", "t@t")
                git(d, "config", "user.name", "t")
            (clone / "migrations").mkdir()
            (clone / "migrations" / "1_a.up.sql").write_text("SELECT 1;")
            git(clone, "add", ".")
            git(clone, "commit", "-m", "1")
            git(clone, "push", "origin", "main")
            git(clone, "remote", "set-head", "origin", "main")
            other = root / "other"
            subprocess.run(["git", "clone", str(origin), str(other)], check=True, capture_output=True)
            git(other, "config", "user.email", "t@t")
            git(other, "config", "user.name", "t")
            (other / "migrations" / "2_b.up.sql").write_text("SELECT 2;")
            git(other, "add", ".")
            git(other, "commit", "-m", "2")
            git(other, "push", "origin", "main")
            state = root / "state"
            state.mkdir()
            (state / "public-baseline.json").write_text(json.dumps({"version": 1, "versions": [1]}))
            run_dir = root / "run"
            run_dir.mkdir()
            with patch.object(up, "STATE", state):
                self.assertEqual(up._main_delta(repos, run_dir), [2])


if __name__ == "__main__":
    unittest.main()
