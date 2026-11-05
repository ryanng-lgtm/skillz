import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from sd import api


class ApiTests(unittest.TestCase):
    def test_get_sends_key_without_printing_it(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok": true}'
        response.__enter__.return_value = response
        buf = io.StringIO()
        with patch.object(api, "load_env", return_value={"DEV_API_KEY": "KEY123"}), \
                patch.object(api, "urlopen", return_value=response) as urlopen, contextlib.redirect_stdout(buf):
            api.main(["--port", "4084", "/v1/exchanges?type=TRADE"])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:4084/v1/exchanges?type=TRADE")
        self.assertEqual(request.get_header("X-kiyotaka-key"), "KEY123")
        self.assertEqual(request.get_header("Authorization"), "KEY123")
        self.assertNotIn("KEY123", buf.getvalue())
        self.assertIn('HTTP 200', buf.getvalue())


if __name__ == "__main__":
    unittest.main()
