import os, unittest
from unittest import mock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from tests.helpers import DbCase
from app import google_login

G = {"email": "asha@gmail.com", "name": "Asha K"}


class GoogleSignIn(DbCase):
    def setUp(self):
        super().setUp()
        from app.main import app
        self.c = TestClient(app)

    def google(self, info=G):
        with mock.patch("app.google_login.verify", return_value=info):
            return self.c.post("/auth/google", json={"credential": "fake-id-token"})

    def test_new_google_email_needs_phone_then_creates_account_without_any_otp(self):
        r = self.google(); self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["needs_phone"]); self.assertNotIn("access_token", r.json())
        done = self.c.post("/auth/google/complete", json={"signup_token": r.json()["signup_token"], "phone": "9876543210"})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["name"], "Asha K"); self.assertTrue(done.json()["access_token"])
        self.assertEqual(self.sent, [])                       # no email was sent
        again = self.google()                                  # next time: straight in
        self.assertEqual(again.json()["user_id"], done.json()["user_id"])
        me = self.c.get("/auth/me", headers={"Authorization": "Bearer " + again.json()["access_token"]}).json()
        self.assertTrue(me["has_email"])

    def test_existing_account_with_that_email_logs_in_directly(self):
        from app.models.core import User
        from app.auth import hash_password
        self.db.add(User(name="Old", phone="9999999999", password_hash=hash_password("secret123"), email="asha@gmail.com")); self.db.commit()
        r = self.google()
        self.assertTrue(r.json()["access_token"]); self.assertEqual(r.json()["name"], "Old")

    def test_phone_already_registered_is_refused(self):
        from app.models.core import User
        from app.auth import hash_password
        self.db.add(User(name="Other", phone="9876543210", password_hash=hash_password("secret123"), email="other@x.com")); self.db.commit()
        tok = self.google().json()["signup_token"]
        r = self.c.post("/auth/google/complete", json={"signup_token": tok, "phone": "9876543210"})
        self.assertEqual(r.status_code, 400)

    def test_bad_or_foreign_signup_token_is_refused(self):
        from app.otp import make_verification_token
        for tok in ("garbage", make_verification_token("9876543210", "asha@gmail.com")):   # an OTP token must not work here
            r = self.c.post("/auth/google/complete", json={"signup_token": tok, "phone": "9876543210"})
            self.assertEqual(r.status_code, 400, tok)

    def test_forged_google_token_is_rejected_and_config_shows_client_id(self):
        os.environ["GOOGLE_CLIENT_ID"] = "cid.apps.googleusercontent.com"
        try:
            self.assertEqual(self.c.post("/auth/google", json={"credential": "not-a-real-token"}).status_code, 401)
            self.assertEqual(self.c.get("/auth/config").json()["google_client_id"], "cid.apps.googleusercontent.com")
        finally:
            os.environ.pop("GOOGLE_CLIENT_ID", None)


class VerifyRules(unittest.TestCase):
    def test_not_configured_is_503(self):
        os.environ.pop("GOOGLE_CLIENT_ID", None)
        with self.assertRaises(HTTPException) as e: google_login.verify("x")
        self.assertEqual(e.exception.status_code, 503)

    def test_unverified_google_email_is_refused_and_verified_one_accepted(self):
        os.environ["GOOGLE_CLIENT_ID"] = "cid"
        try:
            with mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value={"email": "a@gmail.com", "email_verified": False}):
                with self.assertRaises(HTTPException): google_login.verify("x")
            with mock.patch("google.oauth2.id_token.verify_oauth2_token", return_value={"email": "A@Gmail.com", "email_verified": True, "name": "A"}) as m:
                self.assertEqual(google_login.verify("x"), {"email": "a@gmail.com", "name": "A"})
                self.assertEqual(m.call_args[0][2], "cid")        # audience is checked against OUR client id
        finally:
            os.environ.pop("GOOGLE_CLIENT_ID", None)


if __name__ == "__main__":
    unittest.main()
