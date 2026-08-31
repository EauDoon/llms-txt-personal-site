from __future__ import annotations

import importlib.util
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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
