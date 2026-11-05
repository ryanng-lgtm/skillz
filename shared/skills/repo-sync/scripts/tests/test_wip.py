import os
import shutil
import tempfile
import unittest

from gitrepo import git, git_env, script

LINES = [f"line {i}\n" for i in range(1, 21)]


class WipTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        self.env = git_env(tmp)
        self.repo = os.path.join(tmp, "work repo")
        os.mkdir(self.repo)
        self.git("init", "-q")
        self.write("f.txt", LINES)
        self.git("add", "f.txt")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args, check=True):
        return git(self.env, self.repo, *args, check=check)

    def wip(self, cmd):
        return script(self.env, "wip.sh", cmd, self.repo)

    def write(self, name, lines):
        with open(os.path.join(self.repo, name), "w") as f:
            f.writelines(lines)

    def read(self, name):
        with open(os.path.join(self.repo, name)) as f:
            return f.read()

    def edit(self, name, index, text):
        lines = self.read(name).splitlines(keepends=True)
        lines[index] = text
        self.write(name, lines)

    def stage_mixed(self):
        """Stage a change to line 2 of f.txt, then leave one to line 19 unstaged."""
        self.edit("f.txt", 1, "line 2 staged\n")
        self.git("add", "f.txt")
        self.edit("f.txt", 18, "line 19 unstaged\n")

    def upstream(self, name, lines):
        """Commit `lines` to `name` on branch upstream, off main's tip."""
        self.git("checkout", "-q", "-b", "upstream")
        self.write(name, lines)
        self.git("add", name)
        self.git("commit", "-q", "-m", "upstream change")
        self.git("checkout", "-q", "main")

    def state(self):
        return (
            self.git("status", "--porcelain"),
            self.git("diff", "--cached"),
            self.git("diff"),
        )

    def patch_path(self):
        rel = self.git("rev-parse", "--git-path", "repo-sync-index.patch")
        return os.path.join(self.repo, rel.decode().strip())

    def test_clean_tree_noop(self):
        head = self.git("rev-parse", "HEAD")

        r = self.wip("save")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertFalse(os.path.exists(self.patch_path()))

    def test_wip_dropped(self):
        edited = ["line 1 edited\n"] + LINES[1:]
        self.upstream("f.txt", edited)
        self.write("f.txt", edited)
        self.wip("save")
        self.git("rebase", "-q", "upstream")  # drops the WIP commit: all of it is upstream

        r = self.wip("restore")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("wip-dropped", r.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "upstream"))
        self.assertFalse(os.path.exists(self.patch_path()))

    def test_patch_conflict_falls_back(self):
        self.upstream("f.txt", LINES[:1] + ["line 2 upstream\n"] + LINES[2:])
        self.stage_mixed()

        self.wip("save")
        rebase = self.git("rebase", "-q", "upstream", check=False)
        self.assertNotEqual(self.git("diff", "--name-only", "--diff-filter=U"), b"", rebase)
        self.git("checkout", "--theirs", "f.txt")  # the WIP commit's side
        self.git("add", "f.txt")
        self.git("rebase", "--continue")
        r = self.wip("restore")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("index-approximate", r.stdout)
        self.assertIn("f.txt", r.stdout)
        text = self.read("f.txt")
        self.assertIn("line 2 staged\n", text)
        self.assertIn("line 19 unstaged\n", text)
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"f.txt\n")
        self.assertFalse(os.path.exists(self.patch_path()))

    def test_round_trip_through_a_message_replacing_hook(self):
        self.upstream("other.txt", ["unrelated\n"])
        hook = os.path.join(self.repo, ".git", "hooks", "prepare-commit-msg")
        with open(hook, "w") as f:
            f.write('#!/bin/sh\n[ "$2" = message ] && echo "replaced by hook" >"$1"\nexit 0\n')
        os.chmod(hook, 0o755)
        self.stage_mixed()
        self.write(".env.local", ["SECRET=1\n"])
        before = self.state()

        self.wip("save")
        self.git("rebase", "-q", "upstream")
        subject = self.git("log", "-1", "--format=%s").decode()
        r = self.wip("restore")

        self.assertEqual(subject, "replaced by hook\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "upstream"))
        self.assertEqual(self.state(), before)
        self.assertFalse(os.path.exists(self.patch_path()))

    def test_intent_to_add_comes_back_untracked(self):
        self.write("ita.txt", ["planned\n"])
        self.git("add", "-N", "ita.txt")

        self.wip("save")
        r = self.wip("restore")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.git("status", "--porcelain", "--", "ita.txt"), b"?? ita.txt\n")
        self.assertEqual(self.read("ita.txt"), "planned\n")

    def test_textconv_does_not_reach_the_saved_index(self):
        with open(os.path.join(self.repo, ".git", "info", "attributes"), "w") as f:
            f.write("*.txt diff=upper\n")
        self.git("config", "diff.upper.textconv", "sed s/line/LINE/")
        self.upstream("other.txt", ["unrelated\n"])
        self.stage_mixed()
        before = self.state()

        self.wip("save")
        self.git("rebase", "-q", "upstream")
        r = self.wip("restore")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.state(), before)

    def test_wip_below_head_refuses(self):
        self.stage_mixed()
        self.wip("save")
        self.write("g.txt", ["later\n"])
        self.git("add", "g.txt")
        self.git("commit", "-q", "-m", "later work")
        head = self.git("rev-parse", "HEAD")

        r = self.wip("restore")

        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("wip-dropped", r.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertTrue(os.path.exists(self.patch_path()))


if __name__ == "__main__":
    unittest.main()
