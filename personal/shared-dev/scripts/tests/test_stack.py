import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sd import claim, stack
from sd.common import Stuck


class TeardownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(claim, "STATE", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.run_dir = Path(self.tmp.name) / "run"
        (self.run_dir / "config").mkdir(parents=True)
        (self.run_dir / "config" / "tsdb-read.yaml").write_text("{}")
        claim.write("kiyotaka-shared-dev", session="s", branch="feat/x", worktrees=[], schemas=["sd_feat_x"],
                    run_dir=str(self.run_dir), compose=str(self.run_dir / "compose.json"))

    def test_teardown_continues_after_docker_hang(self):
        with patch.object(stack, "run", side_effect=Stuck(["docker"], 120)), \
                patch.object(stack.scratch, "connect", return_value=MagicMock()), \
                patch.object(stack.scratch, "drop_schema") as drop:
            leftovers = stack.teardown("kiyotaka-shared-dev")
        drop.assert_called_once()
        self.assertEqual(drop.call_args.args[1], "sd_feat_x")
        self.assertTrue(any("kiyotaka-shared-dev" in line for line in leftovers))
        self.assertIsNone(claim.read("kiyotaka-shared-dev"))
        self.assertFalse((self.run_dir / "config").exists())

    def test_teardown_keeps_claim_when_schema_drop_fails(self):
        with patch.object(stack, "run"), patch.object(stack.scratch, "connect", side_effect=RuntimeError("no db")):
            leftovers = stack.teardown("kiyotaka-shared-dev")
        self.assertTrue(any("sd_feat_x" in line for line in leftovers))
        self.assertIsNotNone(claim.read("kiyotaka-shared-dev"))

    def test_teardown_deletes_recorded_topics(self):
        claim.update("kiyotaka-shared-dev", topics=["dev.ryan.dedup.long-ids.v1"])
        with patch.object(stack, "run"), patch.object(stack.scratch, "connect", return_value=MagicMock()), \
                patch.object(stack.scratch, "drop_schema"), patch.object(stack.topics, "delete") as delete:
            stack.teardown("kiyotaka-shared-dev")
        delete.assert_called_once_with("kiyotaka-shared-dev", "dev.ryan.dedup.long-ids.v1")

    def test_teardown_rolls_back_meta(self):
        claim.update("kiyotaka-shared-dev", meta={"before": 5, "branch": [9], "dir": "/wt/migrations"})
        with patch.object(stack, "run"), patch.object(stack.scratch, "connect", return_value=MagicMock()), \
                patch.object(stack.scratch, "drop_schema"), patch.object(stack.meta, "connect", return_value="mc"), \
                patch.object(stack.meta, "rollback") as rollback:
            stack.teardown("kiyotaka-shared-dev")
        rollback.assert_called_once_with("mc", [9], Path("/wt/migrations"), to=5)


class DownCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(claim, "STATE", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        claim.write("kiyotaka-shared-dev", session="A", branch="b", worktrees=[], schemas=["sd_a"], run_dir="/r")

    def test_down_requires_project_or_run_dir(self):
        with patch.object(stack, "teardown") as td, self.assertRaises(SystemExit):
            stack.main(["down"])
        td.assert_not_called()

    def test_down_refuses_other_session(self):
        with patch.object(stack, "teardown") as td, self.assertRaises(SystemExit) as ctx:
            stack.main(["down", "--project", "kiyotaka-shared-dev", "--session", "B"])
        td.assert_not_called()
        self.assertIn("A", str(ctx.exception.code))

    def test_down_from_run_dir_uses_its_project_and_session(self):
        run_dir = Path(self.tmp.name) / "run"
        run_dir.mkdir()
        (run_dir / "up.json").write_text('{"project": "kiyotaka-shared-dev", "session": "A"}')
        with patch.object(stack, "teardown", return_value=[]) as td, self.assertRaises(SystemExit) as ctx:
            stack.main(["down", "--run-dir", str(run_dir)])
        td.assert_called_once_with("kiyotaka-shared-dev")
        self.assertEqual(ctx.exception.code, 0)

    def test_down_force_overrides_ownership(self):
        with patch.object(stack, "teardown", return_value=[]) as td, self.assertRaises(SystemExit):
            stack.main(["down", "--project", "kiyotaka-shared-dev", "--force"])
        td.assert_called_once()


class RunOnceCliTests(unittest.TestCase):
    def test_run_once_cli_passes_args_after_separator(self):
        with patch.object(stack, "run", return_value=MagicMock(returncode=0, stdout="done", stderr="")) as run:
            with self.assertRaises(SystemExit) as ctx:
                stack.main(["run-once", "--compose", "/r/compose.json", "--project", "p", "--service", "tsdb-registry",
                            "--timeout", "600", "--", "cjob", "--dry-run", "dark-index"])
        self.assertEqual(ctx.exception.code, 0)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[-4:], ["/schema.yaml", "cjob", "--dry-run", "dark-index"][-4:])
        self.assertIn("--no-deps", cmd)


if __name__ == "__main__":
    unittest.main()
