import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sd import claim

BASE = "kiyotaka-shared-dev"


class ClaimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(claim, "STATE", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def write(self, project=BASE, session="other", schemas=("sd_other",)):
        claim.write(project, session=session, branch="feat/other", worktrees=["/wt"], schemas=list(schemas),
                    run_dir="/run", offset=0, prefix="dev.ryan.")

    def test_claim_states(self):
        with patch.object(claim, "containers", return_value=[]):
            self.assertEqual(claim.state(BASE), "free")
        with patch.object(claim, "containers", return_value=["kiyotaka-shared-dev-tsdb-read-1"]):
            self.assertEqual(claim.state(BASE), "unclaimed")
        self.write()
        with patch.object(claim, "containers", return_value=["kiyotaka-shared-dev-tsdb-read-1"]):
            self.assertEqual(claim.state(BASE), "live")
            self.assertEqual(claim.state(BASE, session="other"), "ours")
        with patch.object(claim, "containers", return_value=[]):
            self.assertEqual(claim.state(BASE), "stale")

    def test_pick_second_project_when_live(self):
        self.write()
        with patch.object(claim, "containers", return_value=["x"]):
            picked = claim.pick("feat/mine", session="me")
        self.assertEqual(picked["project"], "kiyotaka-shared-dev-feat_mine_" + claim.slug("feat/mine")[-6:])
        self.assertEqual(picked["offset"], 20000)
        self.assertEqual(picked["prefix"], f"dev.ryan.{claim.slug('feat/mine')}.")
        self.assertEqual(picked["other"]["session"], "other")

    def test_pick_refuses_when_no_offset_free(self):
        self.write()
        self.write(project="kiyotaka-shared-dev-a", session="a")
        claim.update("kiyotaka-shared-dev-a", offset=20000)
        self.write(project="kiyotaka-shared-dev-b", session="b")
        claim.update("kiyotaka-shared-dev-b", offset=40000)
        with patch.object(claim, "containers", return_value=["x"]):
            with self.assertRaises(SystemExit):
                claim.pick("feat/mine", session="me")

    def test_pick_base_when_free(self):
        with patch.object(claim, "containers", return_value=[]):
            picked = claim.pick("feat/mine", session="me")
        self.assertEqual((picked["project"], picked["offset"], picked["prefix"], picked["state"]), (BASE, 0, "dev.ryan.", "free"))

    def test_pick_reports_unclaimed(self):
        with patch.object(claim, "containers", return_value=["x"]):
            self.assertEqual(claim.pick("feat/mine", session="me")["state"], "unclaimed")

    def test_stale_claim_keeps_schema_name(self):
        self.write(schemas=("sd_feat_x", "sd_main_abc"))
        with patch.object(claim, "containers", return_value=[]):
            self.assertEqual(claim.state(BASE), "stale")
        self.assertEqual(claim.read(BASE)["schemas"], ["sd_feat_x", "sd_main_abc"])

    def test_update_and_release(self):
        self.write()
        claim.update(BASE, meta={"before": 1, "branch": [2], "dir": "/m"})
        self.assertEqual(claim.read(BASE)["meta"]["before"], 1)
        claim.release(BASE)
        self.assertIsNone(claim.read(BASE))


if __name__ == "__main__":
    unittest.main()
