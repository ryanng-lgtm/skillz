import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sd import scratch

GB = 2**30


class NameTests(unittest.TestCase):
    def test_create_schema_refuses_non_sd_name(self):
        for bad in ("public", "fix", "sd-x", "sd_X", "sd_" + "a" * 70, "sd_x; drop schema public"):
            with self.assertRaises(ValueError, msg=bad):
                scratch.create_schema(None, bad)

    def test_drop_schema_refuses_non_sd_name(self):
        for bad in ("public", "lit_relist_archive", "probe_atr"):
            with self.assertRaises(ValueError, msg=bad):
                scratch.drop_schema(None, bad)

    def test_main_schema_name(self):
        self.assertEqual(scratch.main_schema("53a3510260ac4d5672173c6a1074c8014924fc8e"), "sd_main_53a3510260ac")


class CopySqlTests(unittest.TestCase):
    def test_copy_sql_slice_bounded(self):
        sql = scratch.copy_data_sql("open_interest", "sd_x", time_col="timestamp", since=datetime(2026, 10, 1))
        self.assertIn('WHERE "timestamp" >= %s', sql)
        self.assertIn('INSERT INTO "sd_x"."open_interest"', sql)
        self.assertIn('FROM "public"."open_interest"', sql)

    def test_copy_sql_full_has_no_bound(self):
        sql = scratch.copy_data_sql("registry", "sd_x", time_col=None, since=None)
        self.assertNotIn("WHERE", sql)

    def test_sequence_defaults_get_scratch_sequences(self):
        got = scratch.sequence_fixes("sd_x", "registry", [("id", "nextval('registry_id_seq'::regclass)"),
                                                          ("name", "'x'::text")])
        self.assertEqual(got, [
            'CREATE SEQUENCE "sd_x"."registry_id_seq" OWNED BY "sd_x"."registry"."id"',
            'ALTER TABLE "sd_x"."registry" ALTER COLUMN "id" SET DEFAULT nextval(\'"sd_x"."registry_id_seq"\')',
        ])

    def test_needs_copy_names_sequence_owner_issue(self):
        self.assertIsNone(scratch.needs_copy("permission denied for sequence registry_id_seq"))

    def test_rewrite_ddl_moves_index_to_scratch(self):
        ddl = 'CREATE INDEX IF NOT EXISTS trade_x_idx ON public.trade USING btree (symbol, "timestamp" DESC);'
        self.assertEqual(
            scratch.rewrite_ddl(ddl, "sd_x"),
            'CREATE INDEX IF NOT EXISTS trade_x_idx ON "sd_x".trade USING btree (symbol, "timestamp" DESC);',
        )


class BudgetTests(unittest.TestCase):
    def test_too_big_raises_without_confirm(self):
        with self.assertRaises(scratch.TooBig):
            scratch.Budget().charge("registry", 70 * GB + 1)
        scratch.Budget().charge("registry", 70 * GB + 1, confirmed=True)

    def test_run_total_cap(self):
        budget = scratch.Budget()
        budget.charge("a", 40 * GB)
        with self.assertRaises(scratch.TooBig):
            budget.charge("b", 40 * GB)


class NeedsCopyTests(unittest.TestCase):
    def test_needs_copy_parsed(self):
        for line in (
            'error: pq: permission denied for table registry in line 0: ALTER TABLE registry ADD ...',
            'migration failed: must be owner of table registry',
            'must be owner of hypertable "registry"',
            'ERROR: must be owner of relation registry (SQLSTATE 42501)',
        ):
            self.assertEqual(scratch.needs_copy(line), "registry", line)

    def test_needs_copy_ignores_other_errors(self):
        self.assertIsNone(scratch.needs_copy("syntax error at or near SELEC"))

    def test_public_qualified_create_is_not_a_copy(self):
        self.assertIsNone(scratch.needs_copy("permission denied for schema public"))


class ApplyWithCopiesTests(unittest.TestCase):
    def test_apply_with_copies_caps_rounds(self):
        seen = []

        def fake_apply(schema, versions, sources, gateway_bin, password, run_dir, **kw):
            seen.append(password)
            raise scratch.NeedsCopy(f"t{len(seen)}")

        with patch.object(scratch, "drop_schema"), patch.object(scratch, "create_schema"), \
                patch.object(scratch, "copy_object", return_value={"bytes": 1}), \
                patch.object(scratch, "caggs_on_public", return_value=[]):
            with self.assertRaises(scratch.TooManyCopies):
                scratch.apply_with_copies(object(), "sd_x", [3], {3: Path("/m/3_a.up.sql")}, Path("/bin/gw"),
                                          "guardpw", Path("/run"), copies={}, apply=fake_apply)
        self.assertEqual(len(seen), 6)
        self.assertEqual(set(seen), {"guardpw"})

    def test_apply_with_copies_copies_then_succeeds(self):
        calls = []

        def fake_apply(schema, versions, sources, gateway_bin, password, run_dir, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise scratch.NeedsCopy("registry")

        with patch.object(scratch, "drop_schema") as drop, patch.object(scratch, "create_schema"), \
                patch.object(scratch, "copy_object", return_value={"bytes": 1}) as copy, \
                patch.object(scratch, "caggs_on_public", return_value=[]):
            copies = scratch.apply_with_copies(object(), "sd_x", [3], {}, Path("/bin/gw"), "pw", Path("/run"),
                                               copies={"trade": "empty"}, apply=fake_apply)
        self.assertEqual(copies, {"trade": "empty", "registry": "full"})
        self.assertEqual(drop.call_count, 2)
        copied = [c.args[1] for c in copy.call_args_list]
        self.assertEqual(copied, ["trade", "trade", "registry"])

    def test_same_table_twice_stops(self):
        def fake_apply(*a, **kw):
            raise scratch.NeedsCopy("registry")

        with patch.object(scratch, "drop_schema"), patch.object(scratch, "create_schema"), \
                patch.object(scratch, "copy_object", return_value={"bytes": 1}), \
                patch.object(scratch, "caggs_on_public", return_value=[]):
            with self.assertRaises(scratch.TooManyCopies):
                scratch.apply_with_copies(object(), "sd_x", [3], {}, Path("/bin/gw"), "pw", Path("/run"),
                                          copies={"registry": "full"}, apply=fake_apply)

    def test_cagg_on_public_triggers_copy(self):
        def fake_apply(*a, **kw):
            return None

        with patch.object(scratch, "drop_schema") as drop, patch.object(scratch, "create_schema"), \
                patch.object(scratch, "copy_object", return_value={"bytes": 1}), \
                patch.object(scratch, "caggs_on_public", side_effect=[["trade"], []]):
            copies = scratch.apply_with_copies(object(), "sd_x", [3], {}, Path("/bin/gw"), "pw", Path("/run"),
                                               copies={}, apply=fake_apply)
        self.assertEqual(copies, {"trade": "full"})
        self.assertEqual(drop.call_count, 2)

    def test_cagg_on_public_despite_copy_stops(self):
        with patch.object(scratch, "drop_schema"), patch.object(scratch, "create_schema"), \
                patch.object(scratch, "copy_object", return_value={"bytes": 1}), \
                patch.object(scratch, "caggs_on_public", return_value=["trade"]):
            with self.assertRaises(scratch.TooManyCopies):
                scratch.apply_with_copies(object(), "sd_x", [3], {}, Path("/bin/gw"), "pw", Path("/run"),
                                          copies={"trade": "full"}, apply=lambda *a, **kw: None)


if __name__ == "__main__":
    unittest.main()
