import json
import tempfile
import unittest
from pathlib import Path

from sd import capture

PLAYBOOK = """\
kafka_topic: "{{ topic }}"
bitget_exchange_config:
  bitget:
    url: wss://ws.bitget.com/v3/ws/public
    connection_limit: 90
    connection_limit_total: 90
    needed_types:
    - trade
    - book_change
    type_channels:
      trade: [trade, kline]
      book_change: [books]
gemini_exchange_config: &gemini_exchange_config
  gemini:
    url: wss://api.gemini.com/v2/marketdata
    # a comment with {{ jinja }} inside
    connection_limit: 4
    needed_types:
    - trade
    type_channels:
      trade: [trades]
other_key: 1
"""
BASE = {"metrics": {"listen": ":9082"},
        "cex": {"kafka": {"enabled": True, "topic": "dev.ryan.normalized",
                          "options": {"bootstrap.servers": "100.82.235.54:19092", "client.id": "dev.ryan.streamd"}},
                "metadata_instrument": {"address": "metadata-instrument:8092"},
                "exchange_configs": {"bitget": {"url": "x"}}}}


class CaptureTests(unittest.TestCase):
    def test_capture_time_boxed(self):
        svc = capture.service("bitget", ["BTCUSDT"], 180, Path("/run/bin/streamd"), Path("/run/config/streamd-bitget.yaml"))
        self.assertEqual(svc["command"][:6], ["timeout", "--signal=TERM", "--kill-after=15s", "180s", "/shared-dev/streamd", "-c"])
        self.assertEqual(svc["command"][-1], "cex")
        self.assertIn("/run/bin/streamd:/shared-dev/streamd:ro", svc["volumes"])
        self.assertEqual(svc["depends_on"], {"metadata-instrument": {"condition": "service_healthy"}})
        self.assertEqual(svc["platform"], "linux/arm64")

    def test_capture_config_single_venue(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "streamd.yaml.j2").write_text(PLAYBOOK)
            base = tmp / "streamd-bitget.yaml"
            base.write_text(json.dumps(BASE))
            path = capture.config("gemini", ["BTCUSD", "ETHUSD"], "dev.ryan.x.", tmp / "run",
                                  base=base, playbook=tmp / "streamd.yaml.j2")
            cfg = json.loads(path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        venues = cfg["cex"]["exchange_configs"]
        self.assertEqual(list(venues), ["gemini"])
        self.assertEqual(venues["gemini"]["url"], "wss://api.gemini.com/v2/marketdata")
        self.assertEqual(venues["gemini"]["symbol_filters"], {"trade": {"whitelisted_symbols": ["BTCUSD", "ETHUSD"]}})
        self.assertLessEqual(venues["gemini"]["connection_limit"], 2)
        self.assertEqual(cfg["cex"]["kafka"]["topic"], "dev.ryan.x.normalized")
        self.assertEqual(cfg["cex"]["kafka"]["options"]["client.id"], "dev.ryan.x.streamd")

    def test_unknown_venue_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            pb = Path(tmp) / "streamd.yaml.j2"
            pb.write_text(PLAYBOOK)
            with self.assertRaises(KeyError):
                capture.venue_block("kraken", pb)

    def test_writer_tables_for_trade(self):
        self.assertEqual(capture.writer_tables(["trade", "book_change"]), ["trade", "book_change"])


if __name__ == "__main__":
    unittest.main()
