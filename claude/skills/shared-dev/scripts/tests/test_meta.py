import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from sd import meta


class FakeConn:
    def __init__(self, version=(5, False)):
        self.executed = []
        self.version = version

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        conn = self

        class Result:
            def fetchone(self):
                return conn.version

        return Result()


def write_dir(root, versions):
    for v in versions:
        (root / f"{v}_m{v}.up.sql").write_text(f"-- up {v}\nSELECT {v};")
        (root / f"{v}_m{v}.down.sql").write_text(f"-- down {v}\nSELECT -{v};")
    return root


class MetaTests(unittest.TestCase):
    def test_meta_plan_catch_up_then_branch(self):
        main = {v: f"{v}_m" for v in (1, 5, 7)}
        branch = {v: f"{v}_m" for v in (1, 5, 9)}
        self.assertEqual(meta.plan(5, main, branch), {"catch_up": [7], "branch": [9]})

    def test_meta_plan_foreign_version_raises(self):
        with self.assertRaises(meta.ForeignVersion):
            meta.plan(6, {5: "5_m"}, {5: "5_m", 9: "9_m"})

    def test_apply_ascending_then_sets_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_dir(Path(tmp), (7, 9))
            conn = FakeConn()
            meta.apply(conn, [9, 7], d)
        bodies = [sql for sql, _ in conn.executed if sql.startswith("-- up")]
        self.assertEqual(bodies, ["-- up 7\nSELECT 7;", "-- up 9\nSELECT 9;"])
        self.assertEqual(conn.executed[-1][1], (9,))

    def test_rollback_order_descending(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_dir(Path(tmp), (7, 9))
            conn = FakeConn()
            meta.rollback(conn, [7, 9], d, to=5)
        bodies = [sql for sql, _ in conn.executed if sql.startswith("-- down")]
        self.assertEqual(bodies, ["-- down 9\nSELECT -9;", "-- down 7\nSELECT -7;"])
        self.assertEqual(conn.executed[-1][1], (5,))

    def test_dirty_meta_refuses(self):
        with self.assertRaises(meta.Dirty):
            meta.check_clean(FakeConn(version=(5, True)))


if __name__ == "__main__":
    unittest.main()
