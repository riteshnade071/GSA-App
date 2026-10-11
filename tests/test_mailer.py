import json, os, threading, unittest, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from app import mailer


class _Brevo(BaseHTTPRequestHandler):
    status = 201
    seen = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        _Brevo.seen.append((self.path, dict(self.headers), json.loads(body)))
        self.send_response(_Brevo.status); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"messageId":"<x@y>"}' if _Brevo.status < 300 else b'{"message":"nope"}')

    def log_message(self, *a):
        pass


class MailerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Brevo)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        _Brevo.status = 201; _Brevo.seen.clear()
        self._old = {k: os.environ.get(k) for k in ("EMAIL_PROVIDER", "BREVO_API_KEY", "EMAIL_FROM", "BREVO_API_BASE")}
        os.environ.update(EMAIL_PROVIDER="brevo", BREVO_API_KEY="k-123", EMAIL_FROM="no-reply@example.com",
                          BREVO_API_BASE=f"http://127.0.0.1:{self.srv.server_port}")

    def tearDown(self):
        for k, v in self._old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_validity_is_five_minutes(self):
        self.assertEqual(mailer.OTP_MINUTES, 5)

    def test_email_has_code_validity_warning_html_and_text(self):
        mailer.send_email("student@example.com", "482913")
        path, headers, body = _Brevo.seen[0]
        self.assertEqual(path, "/v3/smtp/email")
        self.assertEqual({k.lower(): v for k, v in headers.items()}.get("api-key"), "k-123")   # HTTP header names are case-insensitive
        self.assertEqual(body["to"], [{"email": "student@example.com"}])
        for part in (body["textContent"], body["htmlContent"]):
            self.assertIn("482913", part)
            self.assertIn("5 minutes", part)
            self.assertIn("Do not share this code", part)
        self.assertIn("<", body["htmlContent"])

    def test_provider_refusal_raises_so_nothing_is_claimed_as_sent(self):
        _Brevo.status = 401
        with self.assertRaises(urllib.error.HTTPError):
            mailer.send_email("student@example.com", "482913")

    def test_missing_configuration_raises(self):
        os.environ["BREVO_API_KEY"] = ""
        with self.assertRaises(RuntimeError):
            mailer.send_email("student@example.com", "482913")
        os.environ.update(BREVO_API_KEY="k", EMAIL_PROVIDER="console")
        with self.assertRaises(RuntimeError):
            mailer.send_email("student@example.com", "482913")
        self.assertEqual(_Brevo.seen, [])


if __name__ == "__main__":
    unittest.main()
