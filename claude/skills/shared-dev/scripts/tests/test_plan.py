import tempfile
import unittest
from pathlib import Path

from sd import plan
from sd.scope import Change


def change(repo, *files, branch="feat/x"):
    return Change(repo=repo, worktree=Path(f"/wt/{repo}"), branch=branch, head="h" * 40,
                  base="origin/main", base_sha="b" * 40, files=list(files), uncommitted=False)


class PlanTests(unittest.TestCase):
    def test_plan_reader_change(self):
        p = plan.plan([change("tsdb-gateway", "internal/gateway/reader/query.go")])
        self.assertEqual(p["services"], ["metadata-instrument", "tsdb-read", "tsdb-api"])
        self.assertEqual(p["data"], ["clones"])
        self.assertEqual(p["builds"]["tsdb-read"]["source"], "worktree")
        self.assertEqual(p["builds"]["tsdb-read"]["worktree"], "/wt/tsdb-gateway")
        self.assertEqual(p["builds"]["metadata-instrument"]["source"], "main")
        self.assertFalse(p["migrations"]["tsdb"])

    def test_plan_migration_change(self):
        p = plan.plan([change("tsdb-gateway", "migrations/1792800000_add_x.up.sql")])
        self.assertTrue(p["migrations"]["tsdb"])
        self.assertIn("tsdb-read", p["services"])
        self.assertIn("tsdb-api", p["services"])

    def test_plan_dedup_change(self):
        p = plan.plan([change("stream-deduplicated", "internal/dedup/bitget.go")])
        for service in ("streamd", "stream-deduplicated", "tsdb-write", "metadata-instrument"):
            self.assertIn(service, p["services"])
        self.assertEqual(p["data"], ["live"])
        self.assertEqual(p["builds"]["streamd"]["source"], "main")
        self.assertEqual(p["builds"]["tsdb-write"]["source"], "main")
        self.assertEqual(p["builds"]["stream-deduplicated"]["source"], "worktree")
        self.assertEqual(p["capture"], {"venue": "bitget"})

    def test_plan_venue_from_branch_name(self):
        p = plan.plan([change("stream-deduplicated", "internal/director/lookback.go", branch="feat/bitget-trade-ids")])
        self.assertEqual(p["capture"], {"venue": "bitget"})

    def test_plan_unmapped_files_reported(self):
        p = plan.plan([change("tsdb-gateway", "README.md")])
        self.assertEqual(p["services"], [])
        self.assertEqual(p["unmapped"], ["tsdb-gateway/README.md"])

    def test_plan_starts_dependencies_first(self):
        p = plan.plan([change("live-feed", "internal/server/ws.go")])
        order = p["services"]
        self.assertLess(order.index("metadata-instrument"), order.index("tsdb-read"))
        self.assertLess(order.index("tsdb-read"), order.index("live-feed"))

    def test_plan_library_change_rebuilds_consumers(self):
        module = "gitlab.com/openmarketxyz/go-backend/kiyotaka-go"
        with tempfile.TemporaryDirectory() as tmp:
            repos = Path(tmp)
            (repos / "stream-deduplicated").mkdir()
            (repos / "stream-deduplicated" / "go.mod").write_text(f"module x\n\nrequire (\n\t{module} v0.0.0-1\n)\n")
            (repos / "tsdb-gateway").mkdir()
            (repos / "tsdb-gateway" / "go.mod").write_text("module y\n")
            p = plan.plan([change("kiyotaka-go", "proto/trade.proto")], repos=repos)
        self.assertIn("stream-deduplicated", p["services"])
        self.assertNotIn("tsdb-read", p["services"])
        self.assertEqual(p["builds"]["stream-deduplicated"]["source"], "main")
        self.assertEqual(p["builds"]["stream-deduplicated"]["replace"], {module: "/wt/kiyotaka-go"})


if __name__ == "__main__":
    unittest.main()
