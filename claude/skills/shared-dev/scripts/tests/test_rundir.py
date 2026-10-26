import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from sd import rundir


class RunDirTests(unittest.TestCase):
    def test_uses_the_newest_plans_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = Path(tmp) / "plans"
            (plans / "2026-10-20").mkdir(parents=True)
            (plans / "2026-10-20" / "delist-plan.md").write_text("branch feat/delist-search here")
            (plans / "2026-10-20" / "delist-plan-evidence").mkdir()
            (plans / "2026-10-20" / "delist-plan-evidence" / "notes.md").write_text("feat/delist-search")
            out = rundir.run_dir("feat/delist-search", scratchpad=Path(tmp) / "scratch", plans=plans, stamp="2026-10-26-1737")
            self.assertEqual(out, plans / "2026-10-20" / "delist-plan-evidence" / "shared-dev" / "2026-10-26-1737")
            self.assertTrue(out.is_dir())

    def test_falls_back_to_the_scratchpad(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = Path(tmp) / "plans"
            plans.mkdir()
            out = rundir.run_dir("feat/nothing", scratchpad=Path(tmp) / "scratch", plans=plans, stamp="2026-10-26-1737")
            self.assertEqual(out, Path(tmp) / "scratch" / "shared-dev" / "2026-10-26-1737")

    def test_cli_prints_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rundir.main(["--branch", "feat/x", "--scratchpad", tmp, "--plans", tmp])
            self.assertTrue(Path(buf.getvalue().strip()).is_absolute())


if __name__ == "__main__":
    unittest.main()
