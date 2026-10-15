import base64, email, io, json, os, threading, unittest, urllib.error
from unittest import mock
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


class _Resp:
    def __init__(self, body=b"{}", status=200):
        self._b, self.status = body, status
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False


class GmailApiTests(unittest.TestCase):
    KEYS = ("EMAIL_PROVIDER", "EMAIL_FROM", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")

    def setUp(self):
        self._old = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.update(EMAIL_PROVIDER="gmail_api", EMAIL_FROM="me@gmail.com", GMAIL_CLIENT_ID="cid",
                          GMAIL_CLIENT_SECRET="sec", GMAIL_REFRESH_TOKEN="ref")
        mailer._token.update(value="", exp=0.0)

    def tearDown(self):
        for k, v in self._old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def _fake(self, calls, send_error=None):
        def fake(req, timeout=0):
            calls.append(req)
            if "oauth2.googleapis.com" in req.full_url:
                return _Resp(b'{"access_token":"at-1","expires_in":3599}')
            if send_error:
                raise send_error
            return _Resp(b'{"id":"m1"}')
        return fake

    def test_sends_readable_mail_with_code_through_gmail_api(self):
        calls = []
        with mock.patch("urllib.request.urlopen", side_effect=self._fake(calls)):
            mailer.send_email("student@example.com", "482913")
        send = [c for c in calls if "gmail.googleapis.com" in c.full_url][0]
        self.assertEqual(send.headers["Authorization"], "Bearer at-1")
        msg = email.message_from_bytes(base64.urlsafe_b64decode(json.loads(send.data)["raw"]))
        self.assertEqual(msg["To"], "student@example.com")
        self.assertIn("me@gmail.com", msg["From"])
        body = "".join(p.get_payload(decode=True).decode() for p in msg.walk() if p.get_content_type().startswith("text/"))
        self.assertIn("482913", body); self.assertIn("5 minutes", body); self.assertIn("Do not share this code", body)

    def test_access_token_is_reused(self):
        calls = []
        with mock.patch("urllib.request.urlopen", side_effect=self._fake(calls)):
            mailer.send_email("a@example.com", "111111"); mailer.send_email("b@example.com", "222222")
        self.assertEqual(sum("oauth2" in c.full_url for c in calls), 1)

    def test_refusal_raises_so_code_is_cancelled(self):
        err = urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED"}}'))
        with mock.patch("urllib.request.urlopen", side_effect=self._fake([], send_error=err)):
            with self.assertRaises(RuntimeError):
                mailer.send_email("a@example.com", "111111")

    def test_missing_config_raises_and_status_reports_it(self):
        os.environ["GMAIL_REFRESH_TOKEN"] = ""
        with self.assertRaises(RuntimeError):
            mailer.send_email("a@example.com", "111111")
        self.assertFalse(mailer.status()["ok"])


class GmailSmtpTests(unittest.TestCase):
    def test_sends_via_smtp_ssl_with_app_password(self):
        old = {k: os.environ.get(k) for k in ("EMAIL_PROVIDER", "GMAIL_USER", "GMAIL_APP_PASSWORD")}
        os.environ.update(EMAIL_PROVIDER="gmail", GMAIL_USER="me@gmail.com", GMAIL_APP_PASSWORD="abcd efgh ijkl mnop")
        try:
            with mock.patch("smtplib.SMTP_SSL") as smtp:
                mailer.send_email("student@example.com", "482913")
            inst = smtp.return_value.__enter__.return_value
            inst.login.assert_called_once_with("me@gmail.com", "abcdefghijklmnop")
            self.assertIn("482913", str(inst.send_message.call_args[0][0]))
            self.assertEqual(smtp.call_args[0][:2], ("smtp.gmail.com", 465))
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


if __name__ == "__main__":
    unittest.main()
