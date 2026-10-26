import os
import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sd import clone

GB = 2**30
T0 = datetime(2026, 10, 20)
LAYOUT = {"columns": [("timestamp", "timestamp without time zone"), ("symbol", "text")], "time_col": "timestamp",
          "interval": timedelta(hours=1), "tz": False, "indexes": [], "compression": None}

STUB = """#!/bin/sh
# printf, not echo: macOS sh's echo treats the "\\c" in "\\copy" as end of output
printf '%s\\n' "$* |PGOPTIONS=${PGOPTIONS-unset}|PGPASSWORD=${PGPASSWORD:+set}" >> "$STUB_LOG"
case "$*" in
  *service=*)
    case "$STUB_MODE" in
      timeout) echo "ERROR:  canceling statement due to statement timeout" >&2; exit 1 ;;
      dns) echo 'psql: error: could not translate host name "timescaledb-2.int.ore.kiyotaka.ai" to address' >&2; exit 2 ;;
      *) echo "2026-10-20 00:00:00,BTCUSDT" ;;
    esac ;;
  *) cat > /dev/null ;;
esac
"""


class StubPsql:
    def __init__(self, mode="ok"):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "psql").write_text(STUB)
        (root / "psql").chmod(0o755)
        self.log = root / "calls.log"
        self.env = {"PATH": f"{root}:{os.environ['PATH']}", "STUB_LOG": str(self.log), "STUB_MODE": mode,
                    "PGOPTIONS": "-c statement_timeout=0"}

    def __enter__(self):
        self.patcher = patch.dict(os.environ, self.env)
        self.patcher.start()
        return self

    def __exit__(self, *exc):
        self.patcher.stop()
        self.tmp.cleanup()

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []


def proposal(source="tsdb2", hours=2, batch=timedelta(hours=1)):
    return clone.proposal(source, "trade", since=T0, until=T0 + timedelta(hours=hours), batch=batch,
                          target="trade_tsdb2_20261020")


def checks_pass():
    return [patch.object(clone, "target_exists", return_value=False),
            patch.object(clone, "size", return_value=GB),
            patch.object(clone, "source_layout", return_value=LAYOUT),
            patch.object(clone, "explain_ok", return_value=(True, "1 chunk")),
            patch.object(clone, "create_target"),
            patch.object(clone, "finish_target"),
            patch.object(clone, "compressed_starts", return_value=[])]


class RefusalTests(unittest.TestCase):
    def test_refuses_without_go(self):
        with self.assertRaises(clone.Refused):
            clone.run(proposal(), go=False)

    def test_refuses_source_tsdb0(self):
        with self.assertRaises(clone.Refused):
            proposal(source="tsdb0")
        self.assertEqual(clone.proposal("tsdb0", "trade", since=T0, until=T0 + timedelta(hours=1),
                                        batch=timedelta(hours=1), target="t", explicit_nodes=True)["source"], "tsdb0")

    def test_refuses_long_profile(self):
        with self.assertRaises(clone.Refused):
            proposal(source="tsdb0-long")
        with self.assertRaises(clone.Refused):
            clone.probe("tsdb0-long", "SELECT 1", explicit_nodes=True)

    def test_existing_target_refused(self):
        with patch.object(clone, "target_exists", return_value=True):
            with self.assertRaises(clone.Refused):
                clone.run(proposal(), go=True)

    def test_size_over_70gb_needs_confirm(self):
        patches = checks_pass()
        patches[1] = patch.object(clone, "size", return_value=70 * GB + 1)
        for p in patches:
            p.start()
        self.addCleanup(patch.stopall)
        with StubPsql():
            with self.assertRaises(clone.TooBig):
                clone.run(proposal(), go=True, pause=0)
            self.assertEqual(clone.run(proposal(), go=True, confirmed_size=True, pause=0)["batches"], 2)


class SqlTests(unittest.TestCase):
    def test_batch_sql_always_bounded(self):
        sql = clone.batch_sql("trade", ["timestamp", "symbol"], "timestamp", T0, T0 + timedelta(hours=1))
        self.assertEqual(
            sql,
            'COPY (SELECT "timestamp", "symbol" FROM public."trade" WHERE "timestamp" >= \'2026-10-20 00:00:00\' '
            'AND "timestamp" < \'2026-10-20 01:00:00\') TO STDOUT (FORMAT csv)',
        )

    def test_aware_bounds_become_utc(self):
        plus8 = timezone(timedelta(hours=8))
        sql = clone.batch_sql("trade", ["timestamp"], "timestamp", datetime(2026, 10, 20, 8, tzinfo=plus8),
                              datetime(2026, 10, 20, 9, tzinfo=plus8))
        self.assertIn("\"timestamp\" >= '2026-10-20 00:00:00' AND", sql)

    def test_timestamptz_column_bounds_carry_offset(self):
        sql = clone.batch_sql("trade", ["ts"], "ts", T0, T0 + timedelta(hours=1), tz=True)
        self.assertIn("\"ts\" >= '2026-10-20 00:00:00+00' AND \"ts\" < '2026-10-20 01:00:00+00'", sql)

    def test_index_ddl_rewritten_for_target(self):
        defs = ['CREATE INDEX trade_timestamp_idx ON public.trade USING btree ("timestamp" DESC)',
                'CREATE INDEX trade_symbol_ts_idx ON public.trade USING btree (exchange, symbol, "timestamp" DESC)',
                'CREATE UNIQUE INDEX trade_pk ON public.trade USING btree (id, "timestamp")']
        got = clone.index_ddl_for(defs, "trade", "trade_tsdb2_x", "timestamp")
        self.assertEqual(got, [
            'CREATE INDEX "trade_tsdb2_x_1_idx" ON public."trade_tsdb2_x" USING btree (exchange, symbol, "timestamp" DESC)',
            'CREATE UNIQUE INDEX "trade_tsdb2_x_2_idx" ON public."trade_tsdb2_x" USING btree (id, "timestamp")',
        ])

    def test_batches_chunk_aligned(self):
        got = clone.batches(T0, T0 + timedelta(days=2), timedelta(hours=6), timedelta(days=1))
        self.assertEqual(len(got), 8)
        for lo, hi in got:
            self.assertLessEqual(hi - lo, timedelta(hours=6))
            self.assertEqual(lo.date(), (hi - timedelta(microseconds=1)).date())

    def test_batches_wider_than_chunks_stay_on_boundaries(self):
        got = clone.batches(T0 + timedelta(minutes=30), T0 + timedelta(hours=5), timedelta(hours=2), timedelta(hours=1))
        self.assertEqual(got[0], (T0 + timedelta(minutes=30), T0 + timedelta(hours=2)))
        self.assertTrue(all(hi.minute == 0 for _, hi in got))
        self.assertEqual(got[-1][1], T0 + timedelta(hours=5))


class BatchRunTests(unittest.TestCase):
    def setUp(self):
        for p in checks_pass():
            p.start()
        self.addCleanup(patch.stopall)

    def test_timeout_splits_then_stops(self):
        with StubPsql(mode="timeout") as stub:
            with self.assertRaises(clone.CloneStopped):
                clone.run(proposal(hours=1), go=True, pause=0)
            calls = [c for c in stub.calls() if "service=" in c]
        spans = []
        for call in calls:
            lo, hi = re.findall(r"'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)'", call)
            spans.append(datetime.fromisoformat(hi) - datetime.fromisoformat(lo))
        self.assertTrue(all(b < a for a, b in zip(spans, spans[1:])), spans)
        self.assertLess(spans[-1], timedelta(minutes=2))
        self.assertGreaterEqual(spans[-1], timedelta(minutes=1))
        self.assertTrue(all("service=tsdb2" in c for c in calls))

    def test_vpn_down_stops(self):
        with StubPsql(mode="dns") as stub:
            with self.assertRaises(clone.CloneStopped) as ctx:
                clone.run(proposal(), go=True, pause=0)
            self.assertEqual(len([c for c in stub.calls() if "service=" in c]), 1)
        self.assertIn("VPN", str(ctx.exception))

    def test_prod_calls_never_see_pgoptions(self):
        with StubPsql() as stub:
            clone.run(proposal(), go=True, pause=0)
            calls = stub.calls()
        prod = [c for c in calls if "service=" in c]
        self.assertTrue(prod and all("|PGOPTIONS=unset|" in c for c in prod))

    def test_local_credentials_stay_off_the_command_line(self):
        with StubPsql() as stub, patch.object(clone, "_local_url", return_value="postgres://dev:s3cret@h:25432/data?sslmode=disable"):
            clone.run(proposal(), go=True, pause=0)
            calls = stub.calls()
        local = [c for c in calls if "\\copy" in c]
        self.assertTrue(local)
        self.assertFalse(any("s3cret" in c for c in calls))
        self.assertTrue(all("PGPASSWORD=set" in c for c in local))


class CliTests(unittest.TestCase):
    ARGS = ["--source", "tsdb2", "--table", "trade", "--since", "2026-10-20T00:00", "--until", "2026-10-20T02:00",
            "--batch", "60", "--target", "trade_tsdb2_20261020"]

    def test_run_without_go_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            clone.main(["run", *self.ARGS])
        self.assertIn("--go", str(ctx.exception.code))

    def test_propose_prints_without_touching_prod(self):
        import contextlib
        import io
        buf = io.StringIO()
        with patch.object(clone, "_prod") as prod, contextlib.redirect_stdout(buf):
            clone.main(["propose", *self.ARGS])
        prod.assert_not_called()
        self.assertIn('"target": "public.trade_tsdb2_20261020"', buf.getvalue())

    def test_run_exposes_under_service_name(self):
        with patch.object(clone, "run", return_value={"target": "public.trade_tsdb2_20261020"}) as run_, \
                patch.object(clone, "_expose") as expose:
            clone.main(["run", *self.ARGS, "--go", "--expose-in", "sd_x"])
        self.assertTrue(run_.call_args.kwargs["go"])
        expose.assert_called_once_with("sd_x", "trade", "trade_tsdb2_20261020")


class ProbeTests(unittest.TestCase):
    def test_probe_rewrites_to_explain(self):
        with StubPsql() as stub:
            clone.probe("tsdb2", "SELECT count(*) FROM trade WHERE \"timestamp\" >= now() - interval '1 minute'")
            self.assertIn("-c EXPLAIN SELECT count(*)", stub.calls()[0])

    def test_probe_refuses_analyze_without_approval(self):
        with self.assertRaises(clone.Refused):
            clone.probe("tsdb2", "EXPLAIN ANALYZE SELECT 1")

    def test_probe_refuses_writes_and_settings(self):
        for sql in ("SET statement_timeout = 0", "begin; set transaction read write; delete from trade",
                    "DELETE FROM trade", "SELECT 1; SELECT 2", "CREATE TABLE x (a int)"):
            with self.assertRaises(clone.Refused, msg=sql):
                clone.probe("tsdb2", sql)

    def test_probe_other_nodes_need_explicit(self):
        with self.assertRaises(clone.Refused):
            clone.probe("tsdb1", "SELECT 1")


if __name__ == "__main__":
    unittest.main()
