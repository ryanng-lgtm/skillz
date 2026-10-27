import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import regroup

RULES = regroup.Rules()


def sh(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def lines(n, tag="x"):
    return "".join(f"{tag} {i}\n" for i in range(n))


class Repo:
    """A throwaway repo: `main` with one file, then a `feat` branch."""

    def __init__(self, case):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "repo"
        self.path.mkdir()
        sh(self.path, "init", "-q", "-b", "main")
        sh(self.path, "config", "user.email", "dev@example.com")
        sh(self.path, "config", "user.name", "Dev")
        self.commit({"README.md": "# r\n"}, "initial")
        self.base = self.head()
        sh(self.path, "checkout", "-q", "-b", "feat")

    def commit(self, files, msg):
        for rel, text in files.items():
            p = self.path / rel
            if text is None:
                p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        sh(self.path, "add", "-A")
        sh(self.path, "commit", "-q", "-m", msg)
        return self.head()

    def head(self):
        return sh(self.path, "rev-parse", "HEAD")

    def tree(self, rev="HEAD"):
        return sh(self.path, "rev-parse", f"{rev}^{{tree}}")

    def log(self):
        return sh(self.path, "log", "--format=%s", "main..HEAD").splitlines()[::-1]


class ClassifyTests(unittest.TestCase):
    def test_test_files(self):
        for path in ["pkg/a_test.go", "tests/x.py", "scripts/tests/helpers.py", "test_x.py", "x_test.py",
                     "src/x.test.ts", "src/x.spec.tsx", "src/__tests__/a.js", "conftest.py",
                     "test/unit/a.rb"]:
            self.assertEqual(RULES.kind(path), "test", path)

    def test_generated_files(self):
        for path in ["go.sum", "web/package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock",
                     "uv.lock", "poetry.lock", "vendor/x/y.go", "api/a.pb.go", "pkg/x_gen.go",
                     "pkg/zz_generated.deepcopy.go", "src/__snapshots__/a.snap", "dist/a.min.js"]:
            self.assertEqual(RULES.kind(path), "generated", path)

    def test_testdata_files(self):
        for path in ["pkg/testdata/f.json", "tests/fixtures/a.json", "src/__fixtures__/x.ts", "pkg/out.golden"]:
            self.assertEqual(RULES.kind(path), "testdata", path)

    def test_docs_files(self):
        for path in ["README.md", "CHANGELOG.md", "notes.rst", "a.mdx", "guide.adoc", "docs/arch.png",
                     "doc/x.html"]:
            self.assertEqual(RULES.kind(path), "docs", path)

    def test_code_files(self):
        for path in ["calc/core.py", "cmd/main.go", "src/latest.ts", "contest/a.py", "requirements.txt"]:
            self.assertEqual(RULES.kind(path), "code", path)

    def test_plan_kinds_override_the_defaults(self):
        rules = regroup.Rules({"internal/testutil/**": "test", "schema/*.sql.go": "generated",
                               "claude/skills/*/SKILL.md": "code"})
        self.assertEqual(rules.kind("internal/testutil/db.go"), "test")
        self.assertEqual(rules.kind("schema/q.sql.go"), "generated")
        self.assertEqual(rules.kind("claude/skills/x/SKILL.md"), "code")
        self.assertEqual(rules.kind("go.sum"), "generated")

    def test_unknown_kind_in_a_plan(self):
        with self.assertRaisesRegex(regroup.Refused, "bogus"):
            regroup.Rules({"x/**": "bogus"})


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)

    def review(self, max_lines=600):
        return regroup.review(self.r.path, self.r.base, self.r.head(), max_lines, RULES)

    def test_counts_exclude_generated_and_flag_mixed_commits(self):
        self.r.commit({"calc.py": lines(10), "go.sum": lines(900)}, "deps")
        self.r.commit({"calc.py": lines(12), "tests/test_calc.py": lines(5)}, "mixed")
        deps, mixed = self.review()
        self.assertEqual((deps["counted"], deps["excluded"], deps["problems"]), (10, 900, []))
        self.assertEqual(mixed["kind"], "mixed")
        self.assertIn("mixes kinds (code, test)", mixed["problems"][0])

    def test_docs_with_code_is_mixed(self):
        self.r.commit({"calc.py": lines(3), "README.md": lines(2)}, "mixed")
        self.assertIn("mixes kinds (code, docs)", self.review()[0]["problems"][0])

    def test_testdata_does_not_count(self):
        self.r.commit({"pkg/testdata/big.json": lines(900), "pkg/testdata/b.json": lines(5)}, "fixtures")
        c = self.review()[0]
        self.assertEqual((c["kind"], c["counted"], c["excluded"], c["problems"]), ("testdata", 0, 905, []))

    def test_oversize_is_a_problem_unless_it_is_one_file(self):
        self.r.commit({"a.py": lines(400), "b.py": lines(300)}, "two files")
        self.r.commit({"big.json": lines(800)}, "one file")
        two, one = self.review()
        self.assertIn("700 changed lines > 600", two["problems"][0])
        self.assertEqual(one["problems"], [])
        self.assertIn("single file over 600", one["notes"][0])

    def test_linguist_generated_attribute_is_excluded(self):
        (self.r.path / ".gitattributes").write_text("data/* linguist-generated\n")
        self.r.commit({"data/rates.json": lines(700), "calc.py": lines(4)}, "data")
        self.assertEqual(self.review()[-1]["counted"], 5)

    def test_only_code_commits_are_capped(self):
        self.r.commit({"tests/test_a.py": lines(400), "tests/test_b.py": lines(300)}, "tests")
        self.r.commit({"README.md": lines(400), "docs/x.md": lines(300)}, "docs")
        tests, docs = self.review()
        self.assertEqual((tests["counted"], tests["problems"], tests["oversize"]), (700, [], False))
        self.assertEqual((docs["problems"], docs["oversize"]), ([], False))

    def test_the_cap_counts_the_code_in_a_mixed_commit(self):
        self.r.commit({"a.py": lines(400), "b.py": lines(300), "tests/test_a.py": lines(50)}, "tdd")
        self.r.commit({"c.py": lines(500), "tests/test_c.py": lines(200)}, "tdd 2")
        big, small = self.review()
        self.assertTrue(big["oversize"])
        self.assertIn("700 changed lines > 600", big["problems"][1])
        self.assertFalse(small["oversize"])

    def test_deletions_count(self):
        self.r.commit({"a.py": lines(400)}, "add")
        self.r.commit({"a.py": None, "b.py": lines(250)}, "replace")
        self.assertEqual(self.review()[1]["counted"], 650)

    def test_merge_commits_are_refused(self):
        self.r.commit({"a.py": lines(3)}, "a")
        sh(self.r.path, "checkout", "-q", "main")
        self.r.commit({"m.py": lines(3)}, "on main")
        sh(self.r.path, "checkout", "-q", "feat")
        sh(self.r.path, "merge", "-q", "--no-edit", "main")
        with self.assertRaisesRegex(regroup.Refused, "merge commit"):
            regroup.commits(self.r.path, self.r.base, self.r.head())


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)

    def layout(self):
        return regroup.layout_problems(regroup.review(self.r.path, self.r.base, self.r.head(), 600, RULES))

    def test_the_intended_layout_is_clean(self):
        self.r.commit({"a.py": lines(3)}, "a")
        self.r.commit({"b.py": lines(3), "go.sum": lines(9)}, "b")
        self.r.commit({"pkg/testdata/f.json": lines(3)}, "testdata")
        self.r.commit({"tests/test_a.py": lines(3)}, "tests")
        self.r.commit({"README.md": lines(3)}, "docs")
        self.assertEqual(self.layout(), [])

    def test_tests_always_go_in_one_commit(self):
        self.r.commit({"tests/test_a.py": lines(400)}, "t1")
        self.r.commit({"tests/test_b.py": lines(300)}, "t2")
        self.assertEqual(self.layout(), ["tests are spread over 2 commits; they go in one"])

    def test_docs_always_go_in_one_commit(self):
        self.r.commit({"README.md": lines(3)}, "d1")
        self.r.commit({"docs/x.md": lines(3)}, "d2")
        self.assertEqual(self.layout(), ["docs are spread over 2 commits; they go in one"])

    def test_testdata_always_goes_in_one_commit(self):
        self.r.commit({"pkg/testdata/a.json": lines(700)}, "f1")
        self.r.commit({"pkg/testdata/b.json": lines(700)}, "f2")
        self.assertEqual(self.layout(), ["testdata are spread over 2 commits; they go in one"])

    def test_order_is_code_testdata_tests_docs(self):
        self.r.commit({"tests/test_a.py": lines(3)}, "tests first")
        late = self.r.commit({"a.py": lines(3)}, "code late")
        self.assertEqual(self.layout(), [f"{late[:8]} code late: code comes after a test commit; "
                                         "the order is code, testdata, tests, docs"])


class OfferTests(unittest.TestCase):
    def test_offer_reasons(self):
        r = Repo(self)
        for i in range(9):
            r.commit({f"f{i}.py": lines(3)}, f"c{i}")
        report = regroup.review(r.path, r.base, r.head(), 600, RULES)
        self.assertEqual(regroup.offer_reasons(report, 600), [])
        r.commit({"a.py": lines(400), "b.py": lines(300)}, "big")
        reasons = regroup.offer_reasons(regroup.review(r.path, r.base, r.head(), 600, RULES), 600)
        self.assertEqual(reasons, ["10 commits > 9", "1 commit over 600 changed lines"])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)
        self.c1 = self.r.commit({"tests/test_a.py": lines(5, "t")}, "red")
        self.c2 = self.r.commit({"a.py": lines(5, "a")}, "green")
        self.c3 = self.r.commit({"a.py": lines(8, "a"), "b.py": lines(4, "b")}, "more")
        self.head = self.r.head()

    def build(self, commits):
        return regroup.build(self.r.path, self.r.base, self.head, {"commits": commits})

    def test_builds_the_planned_commits_on_the_base_with_the_same_tree(self):
        tip = self.build([{"message": "feat: a and b\n\n- detail", "paths": ["a.py", "b.py"]},
                          {"message": "test: a", "paths": ["tests/test_a.py"]}])
        self.assertEqual(sh(self.r.path, "rev-parse", f"{tip}^{{tree}}"), self.r.tree())
        self.assertEqual(sh(self.r.path, "log", "--format=%B", "-1", tip), "test: a")
        self.assertEqual(sh(self.r.path, "rev-parse", f"{tip}~2"), self.r.base)
        self.assertEqual(sh(self.r.path, "log", "--format=%B", "-1", f"{tip}~1"), "feat: a and b\n\n- detail")
        self.assertEqual(self.r.head(), self.head, "build never moves the branch")

    def test_path_at_rev_takes_that_commits_version(self):
        tip = self.build([{"message": "feat: a", "paths": [f"a.py@{self.c2[:8]}"]},
                          {"message": "feat: grow a, add b", "paths": ["a.py", "b.py"]},
                          {"message": "test: a", "paths": ["tests/test_a.py"]}])
        self.assertEqual(sh(self.r.path, "show", f"{tip}~2:a.py"), lines(5, "a").strip())
        self.assertEqual(sh(self.r.path, "rev-parse", f"{tip}^{{tree}}"), self.r.tree())

    def test_deleted_paths(self):
        self.r.commit({"a.py": None}, "drop a")
        self.head = self.r.head()
        tip = self.build([{"message": "feat: b", "paths": ["b.py", "tests/test_a.py"]}])
        self.assertEqual(sh(self.r.path, "rev-parse", f"{tip}^{{tree}}"), self.r.tree())

    def test_unassigned_path(self):
        with self.assertRaisesRegex(regroup.Refused, "no commit takes: b.py"):
            self.build([{"message": "x", "paths": ["a.py", "tests/test_a.py"]}])

    def test_path_the_branch_does_not_change(self):
        with self.assertRaisesRegex(regroup.Refused, "README.md is not changed on this branch"):
            self.build([{"message": "x", "paths": ["a.py", "b.py", "tests/test_a.py", "README.md"]}])

    def test_rev_outside_the_branch(self):
        with self.assertRaisesRegex(regroup.Refused, "not a commit on this branch"):
            self.build([{"message": "x", "paths": [f"a.py@{self.r.base}", "a.py", "b.py", "tests/test_a.py"]}])

    def test_commit_that_changes_nothing(self):
        with self.assertRaisesRegex(regroup.Refused, "commit 2 .* changes nothing"):
            self.build([{"message": "x", "paths": ["a.py", "b.py", "tests/test_a.py"]},
                        {"message": "again", "paths": ["a.py"]}])

    def test_last_version_must_be_the_final_one(self):
        with self.assertRaisesRegex(regroup.Refused, "differs from the branch: a.py"):
            self.build([{"message": "x", "paths": ["b.py", "tests/test_a.py", f"a.py@{self.c2}"]}])

    def test_empty_message(self):
        with self.assertRaisesRegex(regroup.Refused, "commit 1 has no message"):
            self.build([{"message": " ", "paths": ["a.py", "b.py", "tests/test_a.py"]}])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)
        self.r.commit({"tests/test_a.py": lines(5, "t")}, "red")
        self.r.commit({"a.py": lines(5, "a")}, "green")
        self.head = self.r.head()
        self.plan = Path(self.r.path.parent) / "plan.json"
        self.write_plan([{"message": "feat: a", "paths": ["a.py"]},
                         {"message": "test: a", "paths": ["tests/test_a.py"]}])

    def write_plan(self, commits):
        self.plan.write_text(json.dumps({"commits": commits}))

    def apply(self, dry_run=False):
        return regroup.apply(self.r.path, self.plan, base_ref="main", max_lines=600, dry_run=dry_run)

    def test_moves_the_branch_and_keeps_a_backup(self):
        out = self.apply()
        self.assertEqual(self.r.log(), ["feat: a", "test: a"])
        self.assertEqual(self.r.tree(), self.r.tree(self.head))
        self.assertTrue(out["backup"].startswith("refs/regroup/feat/"))
        self.assertEqual(sh(self.r.path, "rev-parse", out["backup"]), self.head)
        self.assertEqual(sh(self.r.path, "status", "--porcelain"), "")

    def test_dry_run_leaves_the_branch(self):
        out = self.apply(dry_run=True)
        self.assertEqual(self.r.head(), self.head)
        self.assertIsNone(out["backup"])
        self.assertEqual(len(out["review"]), 2)

    def test_refuses_a_dirty_worktree(self):
        (self.r.path / "a.py").write_text("changed\n")
        with self.assertRaisesRegex(regroup.Refused, "uncommitted changes"):
            self.apply()

    def test_refuses_a_detached_head(self):
        sh(self.r.path, "checkout", "-q", "--detach")
        with self.assertRaisesRegex(regroup.Refused, "detached"):
            self.apply()

    def test_problems_keep_the_branch_where_it_was(self):
        self.write_plan([{"message": "feat: a with tests", "paths": ["a.py", "tests/test_a.py"]}])
        with self.assertRaisesRegex(regroup.Refused, "mixes kinds"):
            self.apply()
        self.assertEqual(self.r.head(), self.head)
        self.assertEqual(sh(self.r.path, "for-each-ref", "refs/regroup"), "")


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.r = Repo(self)
        self.r.commit({"a.py": "print(1)\n"}, "one")
        self.bad = self.r.commit({"a.py": "print(\n"}, "two")
        self.r.commit({"a.py": "print(3)\n"}, "three")

    def test_runs_the_command_on_every_commit(self):
        results = regroup.run_each(self.r.path, regroup.commits(self.r.path, self.r.base, self.r.head()),
                                   "python3 -I -c \"import ast; ast.parse(open('a.py').read())\"", links=[],
                                   timeout=60)
        self.assertEqual([ok for _, ok, _ in results], [True, False, True])
        self.assertEqual(results[1][0], self.bad)
        self.assertEqual(sh(self.r.path, "worktree", "list").count("\n"), 0, "temp worktree removed")

    def test_links_ignored_dirs_into_the_temp_worktree(self):
        (self.r.path / ".gitignore").write_text("deps/\n")
        (self.r.path / "deps").mkdir()
        (self.r.path / "deps" / "lib.txt").write_text("ok\n")
        results = regroup.run_each(self.r.path, [self.r.head()], "test -f deps/lib.txt", links=["deps"],
                                   timeout=60)
        self.assertTrue(results[0][1])

    def test_against_compares_trees(self):
        self.assertEqual(regroup.tree_diff(self.r.path, "HEAD", "HEAD"), [])
        self.assertEqual(regroup.tree_diff(self.r.path, "HEAD", self.bad), ["a.py"])


class CliTests(unittest.TestCase):
    def test_stats_json(self):
        r = Repo(self)
        r.commit({"a.py": lines(3), "tests/test_a.py": lines(2)}, "mixed")
        out = subprocess.run(["python3", "-I", str(Path(regroup.__file__)), "stats", "--json"], cwd=r.path,
                             capture_output=True, text=True, env={**os.environ})
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["base"], r.base)
        self.assertEqual(data["commits"][0]["kind"], "mixed")
        self.assertEqual(data["offer"], [])
        self.assertEqual(data["layout"], [])
        self.assertEqual(data["files"], [{"path": "a.py", "kind": "code", "lines": 3},
                                         {"path": "tests/test_a.py", "kind": "test", "lines": 2}])


if __name__ == "__main__":
    unittest.main()
