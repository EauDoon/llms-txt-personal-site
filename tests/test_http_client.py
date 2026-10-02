from __future__ import annotations

import importlib.util
import io
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.response import addinfourl

ROOT = Path(__file__).resolve().parents[1]


class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/gone")
        else:
            self.send_response(410)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


class HttpClientTests(unittest.TestCase):
    def test_success_and_error_bodies_are_bounded_without_trusting_length(self) -> None:
        spec = importlib.util.spec_from_file_location("bounded_client", ROOT / "scripts" / "http_client.py")
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
        for status in (200, 500):
            for length in (None, "1", "1024"):
                for size in (64, 1024):
                    with self.subTest(status=status, content_length=length, bytes=size):
                        body = io.BytesIO(b"x" * size)
                        headers = {} if length is None else {"Content-Length": length}
                        response = addinfourl(body, headers, "https://example.test", status)
                        effect = {"return_value": response} if status == 200 else {
                            "side_effect": HTTPError("https://example.test", status, "error", headers, body)}
                        with patch.object(client, "MAX_RESPONSE_BYTES", 64), patch.object(client.OPENER, "open", **effect), patch.object(body, "read", wraps=body.read) as read:
                            result_status, _, content, error = client.fetch_url("https://example.test")
                        read.assert_called_once_with(65)
                        self.assertTrue(body.closed)
                        if size == 64:
                            self.assertEqual(result_status, status)
                            self.assertEqual(content, b"x" * 64)
                            self.assertEqual(error, "")
                        else:
                            self.assertEqual(result_status, 0)
                            self.assertEqual(content, b"")
                            self.assertIn("Response exceeds", error)

    def test_redirect_status_is_not_replaced_by_target_status(self) -> None:
        client_path = ROOT / "scripts" / "http_client.py"
        self.assertTrue(
            client_path.is_file(),
            "portable live client with an explicit redirect policy is missing",
        )
        spec = importlib.util.spec_from_file_location("http_client_under_test", client_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            status, _, _, error = module.fetch_url(
                "http://127.0.0.1:%d/redirect" % server.server_port,
                timeout=2,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

        self.assertEqual(error, "")
        self.assertEqual(status, 302)


if __name__ == "__main__":
    unittest.main()
