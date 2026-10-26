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

    def test_teardown_rolls_back_meta(self):
        claim.update("kiyotaka-shared-dev", meta={"before": 5, "branch": [9], "dir": "/wt/migrations"})
        with patch.object(stack, "run"), patch.object(stack.scratch, "connect", return_value=MagicMock()), \
                patch.object(stack.scratch, "drop_schema"), patch.object(stack.meta, "connect", return_value="mc"), \
                patch.object(stack.meta, "rollback") as rollback:
            stack.teardown("kiyotaka-shared-dev")
        rollback.assert_called_once_with("mc", [9], Path("/wt/migrations"), to=5)


if __name__ == "__main__":
    unittest.main()
