import os
import shutil
import tempfile
import unittest

from gitrepo import git, git_env, script


class ScanTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.env = git_env(tmp)
        origin = os.path.join(tmp, "origin.git")
        seed = os.path.join(tmp, "seed")
        git(self.env, tmp, "init", "-q", "--bare", origin)
        git(self.env, tmp, "clone", "-q", origin, seed)
        git(self.env, seed, "commit", "-q", "--allow-empty", "-m", "base")
        git(self.env, seed, "push", "-q", "origin", "main")
        self.root = os.path.join(tmp, "my repos")
        os.mkdir(self.root)
        self.repo = os.path.join(self.root, "alpha")
        git(self.env, tmp, "clone", "-q", origin, self.repo)

    def test_scan_roots_with_spaces(self):
        for how, args, env in (
            ("--root", ["--root", self.root], self.env),
            ("REPO_SYNC_ROOT", [], {**self.env, "REPO_SYNC_ROOT": self.root}),
        ):
            with self.subTest(how=how):
                r = script(env, "scan.sh", "--all", *args)

                self.assertEqual(r.returncode, 0, r.stderr)
                rows = [line.split("\t") for line in r.stdout.splitlines()]
                self.assertEqual([(row[7], row[8]) for row in rows], [(self.repo, "ok")])

    def test_no_roots_no_paths_refuses(self):
        r = script(self.env, "scan.sh", "--all")

        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertIn("pass repo paths", r.stderr)
        self.assertIn("REPO_SYNC_ROOT", r.stderr)


if __name__ == "__main__":
    unittest.main()
