import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from sd import query


class QueryTests(unittest.TestCase):
    def test_prints_rows_as_tsv_with_header(self):
        cur = MagicMock()
        cur.description = [MagicMock(name="symbol"), MagicMock(name="n")]
        cur.description[0].name, cur.description[1].name = "symbol", "n"
        cur.fetchall.return_value = [("BTCUSDT", 3), ("ETHUSDT", None)]
        conn = MagicMock()
        conn.execute.return_value = cur
        buf = io.StringIO()
        with patch.object(query.scratch, "connect", return_value=conn) as connect, \
                patch.object(query.scratch, "guard_url", return_value="postgres://sd_guard:SECRET@h/data") as gurl, \
                patch.object(query, "_guard_password", return_value="SECRET"), contextlib.redirect_stdout(buf):
            query.main(["--schema", "sd_x", "-c", "SELECT symbol, n FROM trade"])
        gurl.assert_called_once_with("SECRET", ["sd_x"])
        connect.assert_called_once_with("postgres://sd_guard:SECRET@h/data")
        self.assertEqual(buf.getvalue(), "symbol\tn\nBTCUSDT\t3\nETHUSDT\t\n")
        self.assertNotIn("SECRET", buf.getvalue())
        self.assertIn("statement_timeout", conn.execute.call_args_list[0].args[0])

    def test_dev_role_is_read_only(self):
        conn = MagicMock()
        conn.execute.return_value.description = None
        with patch.object(query.scratch, "connect", return_value=conn), contextlib.redirect_stdout(io.StringIO()):
            query.main(["--as", "dev", "-c", "SELECT 1"])
        sql = [c.args[0] for c in conn.execute.call_args_list]
        self.assertTrue(any("default_transaction_read_only" in s for s in sql[:2]))


if __name__ == "__main__":
    unittest.main()
