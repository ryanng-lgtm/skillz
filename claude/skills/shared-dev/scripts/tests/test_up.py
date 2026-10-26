import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from sd import up


def write(path, doc):
    path.write_text(json.dumps(doc))
    return path


class UpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.run_dir = root / "run"
        self.run_dir.mkdir()
        wt = root / "wt" / "tsdb-gateway"
        (wt / "migrations").mkdir(parents=True)
        self.scope = write(root / "scope.json", [{
            "repo": "tsdb-gateway", "worktree": str(wt), "branch": "feat/x", "head": "h" * 40, "base": "origin/main",
            "base_sha": "b" * 40, "files": ["internal/gateway/reader/q.go"], "uncommitted": False}])
        self.plan = {"services": ["metadata-instrument", "tsdb-read", "tsdb-api"],
                     "builds": {"metadata-instrument": {"repo": "metadata-instrument", "source": "main", "worktree": None},
                                "tsdb-read": {"repo": "tsdb-gateway", "source": "worktree", "worktree": str(wt)},
                                "tsdb-api": {"repo": "tsdb-gateway", "source": "worktree", "worktree": str(wt)}},
                     "data": ["clones"], "migrations": {"tsdb": False, "meta": False}, "cjob": False,
                     "capture": None, "fe": False, "unmapped": []}

    def patches(self, pick_state="free", behind=()):
        stack = ExitStack()
        self.addCleanup(stack.close)
        m = {}
        m["behind"] = stack.enter_context(patch.object(up, "_main_delta", return_value=list(behind)))
        m["pick"] = stack.enter_context(patch.object(up.claim, "pick", return_value={
            "project": "kiyotaka-shared-dev", "offset": 0, "prefix": "dev.ryan.", "state": pick_state, "other": None}))
        m["write"] = stack.enter_context(patch.object(up.claim, "write"))
        m["update"] = stack.enter_context(patch.object(up.claim, "update"))
        m["wt_build"] = stack.enter_context(patch.object(up.builds, "worktree_build", return_value=Path("/run/bin/tsdb-gateway")))
        m["main_build"] = stack.enter_context(patch.object(up.builds, "main_build", return_value=Path("/bin/main/x")))
        m["schema_for"] = stack.enter_context(patch.object(up.builds, "schema_for", return_value=Path("/wt/schema.yaml")))
        m["connect"] = stack.enter_context(patch.object(up.scratch, "connect", return_value=MagicMock()))
        m["guard"] = stack.enter_context(patch.object(up.scratch, "ensure_guard", return_value="pw"))
        m["create"] = stack.enter_context(patch.object(up.scratch, "create_schema"))
        m["render"] = stack.enter_context(patch.object(up.compose, "render", return_value=self.run_dir / "compose.json"))
        m["up"] = stack.enter_context(patch.object(up.stack, "up"))
        return m

    def test_unclaimed_stack_stops_before_anything(self):
        m = self.patches(pick_state="unclaimed")
        with self.assertRaises(up.Stop) as ctx:
            up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(ctx.exception.code, 3)
        m["write"].assert_not_called()
        m["wt_build"].assert_not_called()

    def test_reader_change_gets_main_reader_beside_it(self):
        m = self.patches()
        summary = up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertTrue(summary["main_reader"])
        self.assertIn("tsdb-read-main", m["up"].call_args.args[2])

    def test_second_project_flag_passed_to_pick(self):
        m = self.patches()
        up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1", second_project=True)
        self.assertTrue(m["pick"].call_args.kwargs.get("second"))

    def test_claim_written_before_builds(self):
        m = self.patches()
        order = []
        m["write"].side_effect = lambda *a, **k: order.append("claim")
        m["wt_build"].side_effect = lambda *a, **k: order.append("build") or Path("/run/bin/tsdb-gateway")
        up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(order[0], "claim")
        kwargs = m["write"].call_args.kwargs
        schema = "sd_feat_x_" + up.slug("feat/x")[-6:]
        self.assertEqual(kwargs["schemas"], [schema, schema + "_x"])
        created = [c.args[1] for c in m["create"].call_args_list]
        self.assertEqual(created, [schema, schema + "_x"])
        self.assertEqual(m["render"].call_args.kwargs["exposed"], schema + "_x")
        self.assertEqual(kwargs["compose"], str(self.run_dir / "compose.json"))

    def test_happy_path_starts_planned_services(self):
        m = self.patches()
        summary = up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        m["up"].assert_called_once_with(self.run_dir / "compose.json", "kiyotaka-shared-dev",
                                        ["metadata-instrument", "tsdb-read", "tsdb-api"])
        self.assertEqual(summary["project"], "kiyotaka-shared-dev")
        self.assertEqual(json.loads((self.run_dir / "up.json").read_text())["schema"], summary["schema"])
        self.assertEqual(m["wt_build"].call_count, 2)

    def test_behind_main_stops(self):
        m = self.patches()
        self.plan["migrations"]["tsdb"] = True
        with patch.object(up, "_tsdb_delta", side_effect=up.Stop(5, "public is 3 migrations behind main")):
            with self.assertRaises(up.Stop) as ctx:
                up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(ctx.exception.code, 5)
        m["up"].assert_not_called()

    def test_reader_only_branch_stops_when_public_behind_main(self):
        m = self.patches(behind=[1792749073, 1792754570])
        with self.assertRaises(up.Stop) as ctx:
            up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(ctx.exception.code, 5)
        self.assertIn("2 migrations behind", str(ctx.exception))
        m["write"].assert_not_called()

    def test_merged_branch_built_from_main_runs(self):
        # a squash-merged MR: its migrations are on main (and in public after a rebaseline)
        m = self.patches()
        self.plan["migrations"]["tsdb"] = True
        for b in self.plan["builds"].values():
            b["source"], b["worktree"] = "main", None
        with patch.object(up, "_tsdb_delta", return_value=({}, [])), \
                patch.object(up, "_branch_indexes", return_value=[]) as indexes:
            summary = up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertTrue(summary["main_reader"])
        indexes.assert_called_once()

    def test_stale_claim_torn_down_before_new_claim(self):
        m = self.patches(pick_state="stale")
        order = []
        with patch.object(up.stack, "teardown", side_effect=lambda p: order.append("teardown") or []) as td:
            m["write"].side_effect = lambda *a, **k: order.append("claim")
            up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        td.assert_called_once_with("kiyotaka-shared-dev")
        self.assertEqual(order[:2], ["teardown", "claim"])

    def test_own_earlier_run_torn_down_too(self):
        m = self.patches(pick_state="ours")
        with patch.object(up.stack, "teardown", return_value=[]) as td:
            up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        td.assert_called_once()

    def test_stale_teardown_leftovers_stop(self):
        m = self.patches(pick_state="stale")
        with patch.object(up.stack, "teardown", return_value=["could not drop sd_old: OperationalError"]):
            with self.assertRaises(up.Stop) as ctx:
                up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(ctx.exception.code, 8)
        m["write"].assert_not_called()

    def test_allow_behind_runs_with_warning(self):
        m = self.patches(behind=[1792749073])
        with patch.object(up, "_missing_objects", return_value=["market_stats_atr"]):
            summary = up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1",
                            allow_behind=True)
        self.assertTrue(any("behind main" in w and "market_stats_atr" in w for w in summary["warnings"]))
        m["up"].assert_called_once()

    def test_capture_service_not_started_with_stack(self):
        m = self.patches()
        self.plan["services"] = ["metadata-instrument", "tsdb-write", "stream-deduplicated", "streamd"]
        self.plan["builds"]["streamd"] = {"repo": "streamd", "source": "main", "worktree": None}
        self.plan["capture"] = {"venue": "bitget"}
        with patch.object(up.capture, "plan_capture", return_value={"service_name": "streamd-bitget", "service": {},
                                                                    "config": Path("/c")}), \
                patch.object(up.scratch, "copy_object", return_value={"bytes": 0}):
            summary = up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1",
                            symbols=["BTCUSDT"])
        started = m["up"].call_args.args[2]
        self.assertNotIn("streamd", started)
        self.assertNotIn("streamd-bitget", started)
        self.assertEqual(summary["capture"]["service"], "streamd-bitget")

    def test_capture_without_venue_or_symbols_stops(self):
        self.patches()
        self.plan["services"] = ["metadata-instrument", "tsdb-write", "stream-deduplicated", "streamd"]
        self.plan["capture"] = {"venue": None}
        with self.assertRaises(up.Stop) as ctx:
            up.up(self.scope, write(self.run_dir / "plan.json", self.plan), self.run_dir, "session-1")
        self.assertEqual(ctx.exception.code, 6)


if __name__ == "__main__":
    unittest.main()
