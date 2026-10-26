import json
import subprocess
import sys
import unittest
from pathlib import Path

from sd import rebaseline

MAIN = {v: f"{v}_m" for v in (1, 2, 3, 4, 5)}


class PlanTests(unittest.TestCase):
    def test_plan_dirty_forces_previous(self):
        base = {"version": 3, "dirty": True, "versions": [1, 2]}
        self.assertEqual(rebaseline.plan(base, MAIN), {"from": 3, "dirty": True, "force": 2, "apply": [3, 4, 5], "to": 5})

    def test_plan_clean_needs_no_force(self):
        base = {"version": 3, "dirty": False, "versions": [1, 2, 3]}
        self.assertEqual(rebaseline.plan(base, MAIN)["force"], None)
        self.assertEqual(rebaseline.plan(base, MAIN)["apply"], [4, 5])

    def test_plan_refuses_lower_numbered_delta(self):
        # main gained 2 after public moved past it; golang-migrate up would skip it
        base = {"version": 4, "dirty": False, "versions": [1, 3, 4]}
        with self.assertRaises(rebaseline.Unsafe):
            rebaseline.plan(base, MAIN)

    def test_plan_refuses_version_not_on_main(self):
        with self.assertRaises(rebaseline.Unsafe):
            rebaseline.plan({"version": 9, "dirty": False, "versions": [1, 9]}, MAIN)


class SafetyTests(unittest.TestCase):
    def test_transactional_detection(self):
        self.assertTrue(rebaseline.transactional("CREATE MATERIALIZED VIEW x WITH (timescaledb.continuous) AS SELECT 1 WITH NO DATA;"))
        for sql in ("BEGIN; SELECT 1; COMMIT;", "CREATE INDEX CONCURRENTLY i ON t (a);", "VACUUM t;", "commit;"):
            self.assertFalse(rebaseline.transactional(sql), sql)

    def test_created_objects(self):
        sql = "CREATE MATERIALIZED VIEW a_1m WITH (x) AS SELECT 1;\nCREATE TABLE IF NOT EXISTS b (x int);\nCREATE OR REPLACE FUNCTION c() RETURNS int AS $$ SELECT 1 $$ LANGUAGE sql;"
        self.assertEqual(rebaseline.created_objects(sql), {"a_1m", "b", "c"})

    def test_apply_requires_yes(self):
        proc = subprocess.run([sys.executable, "-I", str(Path(__file__).parents[1] / "run.py"), "rebaseline", "apply"],
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--yes", proc.stderr)


if __name__ == "__main__":
    unittest.main()
