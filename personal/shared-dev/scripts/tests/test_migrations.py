import subprocess
import tempfile
import unittest
from pathlib import Path

from sd import migrations


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def add_migration(repo, version, msg=None):
    d = repo / "migrations"
    d.mkdir(exist_ok=True)
    (d / f"{version}_m{version}.up.sql").write_text(f"SELECT {version};\n")
    (d / f"{version}_m{version}.down.sql").write_text("SELECT 0;\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", msg or f"add {version}")


def history(root):
    """main: 1,2 -> branch feat/x off 2 adds 10 -> main adds 3,4 afterwards."""
    origin = root / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    repo = root / "tsdb-gateway"
    subprocess.run(["git", "clone", str(origin), str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    for v in (1, 2):
        add_migration(repo, v)
    git(repo, "switch", "-c", "feat/x")
    add_migration(repo, 10)
    git(repo, "push", "origin", "feat/x")
    git(repo, "switch", "main")
    for v in (3, 4):
        add_migration(repo, v)
    git(repo, "push", "origin", "main")
    git(repo, "fetch", "origin")
    return repo


class MigrationTests(unittest.TestCase):
    def test_parse_dir_ignores_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "5_a.generated.up.sql").write_text("")
            (d / "5_a.generated.down.sql").write_text("")
            (d / "templates").mkdir()
            (d / "templates" / "6_b.up.sql.template").write_text("")
            self.assertEqual(migrations.parse_dir(d), {5: "5_a.generated"})

    def test_baseline_from_branch_only_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = history(Path(tmp))
            self.assertEqual(migrations.baseline(repo, 10)["versions"], {1, 2, 10})

    def test_baseline_dirty_excludes_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = history(Path(tmp))
            found = migrations.baseline(repo, 10, dirty=True)
            self.assertEqual(found["versions"], {1, 2})
            self.assertIs(found["dirty"], True)

    def test_baseline_unknown_version_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = history(Path(tmp))
            with self.assertRaises(migrations.BaselineUnknown):
                migrations.baseline(repo, 99)

    def test_export_dir_from_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = history(Path(tmp))
            out = migrations.export_dir(repo, "origin/main", Path(tmp) / "main")
            self.assertEqual(set(migrations.parse_dir(out)), {1, 2, 3, 4})

    def test_delta_splits_main_and_branch(self):
        main = {v: f"{v}_m" for v in (1, 2, 3, 4)}
        branch = {v: f"{v}_m" for v in (1, 2, 3, 4, 20)}
        self.assertEqual(migrations.delta({1, 2, 10}, main, branch), ([3, 4], [20]))

    def test_scan_finds_cagg_sources_and_touched(self):
        sql = """
        -- a comment naming DELETE FROM nothing
        CREATE MATERIALIZED VIEW trade_agg_1m WITH (timescaledb.continuous) AS
          SELECT time_bucket('1 minute', "timestamp") AS bucket, symbol, sum(amount)
          FROM public.trade GROUP BY 1, 2 WITH NO DATA;
        ALTER TABLE public.registry ADD COLUMN y int;
        SELECT add_retention_policy('book_change', INTERVAL '7 days');
        CREATE INDEX IF NOT EXISTS ix ON "open_interest" (symbol);
        INSERT INTO trade_tiers (a) VALUES (1) ON CONFLICT (a) DO UPDATE SET a = excluded.a;
        """
        found = migrations.scan(sql)
        self.assertEqual(found["cagg_sources"], {"trade"})
        self.assertTrue({"registry", "book_change", "open_interest", "trade_tiers"} <= found["touched"])
        self.assertNotIn("set", found["touched"])
        self.assertEqual(found["destructive"], [])

    def test_scan_flags_destructive(self):
        found = migrations.scan("DELETE FROM registry WHERE x = 1;\nALTER TABLE trade DROP COLUMN y;\nDROP TABLE IF EXISTS old_t;")
        self.assertIn("DELETE FROM registry", found["destructive"])
        self.assertIn("ALTER TABLE trade DROP", found["destructive"])
        self.assertIn("DROP TABLE old_t", found["destructive"])
        self.assertTrue({"registry", "trade", "old_t"} <= found["touched"])

    def test_stage_adds_noop_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            for v in (3, 4):
                (src / f"{v}_m.up.sql").write_text(f"SELECT {v};")
                (src / f"{v}_m.down.sql").write_text("SELECT 0;")
            out = Path(tmp) / "staged"
            v0 = migrations.stage([4, 3], {3: src / "3_m.up.sql", 4: src / "4_m.up.sql"}, out)
            self.assertEqual(v0, 2)
            self.assertEqual((out / "2_sd_baseline.up.sql").read_text().strip(), "SELECT 1;")
            self.assertTrue((out / "2_sd_baseline.down.sql").exists())
            self.assertEqual(set(migrations.parse_dir(out)), {2, 3, 4})


if __name__ == "__main__":
    unittest.main()
