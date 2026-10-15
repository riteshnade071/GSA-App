import json, unittest
from unittest import mock
from fastapi.testclient import TestClient
from tests.helpers import DbCase

PHONE, EMAIL, PW = "9876543210", "student@example.com", "secret123"


class AuthApi(DbCase):
    def setUp(self):
        super().setUp()
        from app.main import app
        self.c = TestClient(app)                 # no startup event: tables are made by DbCase

    # ---- helpers
    def request_otp(self, purpose="signup", email=EMAIL, phone=PHONE):
        return self.c.post("/auth/otp/request", json={"phone": phone, "email": email, "purpose": purpose})

    def signup(self, phone=PHONE, email=EMAIL):
        r = self.request_otp("signup", email, phone); self.assertEqual(r.status_code, 200, r.text)
        code = self.sent[-1][1]
        v = self.c.post("/auth/otp/verify", json={"phone": phone, "email": email, "code": code}); self.assertEqual(v.status_code, 200, v.text)
        r = self.c.post("/auth/register", json={"name": "Asha", "phone": phone, "password": PW, "verification_token": v.json()["verification_token"]})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ---- registration + login regression
    def test_full_signup_then_login(self):
        self.signup()
        ok = self.c.post("/auth/login", json={"phone": PHONE, "password": PW})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.c.post("/auth/login", json={"phone": PHONE, "password": "nope-nope"}).status_code, 401)

    def test_otp_is_never_in_any_api_response(self):
        r = self.request_otp()
        code = self.sent[-1][1]
        self.assertNotIn(code, r.text)
        self.assertEqual(set(r.json()), {"sent", "cooldown"})
        self.assertEqual(r.json()["cooldown"], 60)
        bad = self.c.post("/auth/otp/verify", json={"phone": PHONE, "email": EMAIL, "code": "000000" if code != "000000" else "111111"})
        self.assertEqual(bad.status_code, 400); self.assertNotIn(code, bad.text)

    def test_register_without_or_with_forged_verification_is_refused(self):
        for token in (None, "", "verified=true", "a.b.c"):
            r = self.c.post("/auth/register", json={"name": "X", "phone": PHONE, "password": PW, "verification_token": token})
            self.assertEqual(r.status_code, 400)
        r = self.c.post("/auth/register", json={"name": "X", "phone": PHONE, "password": PW, "verified": True})
        self.assertEqual(r.status_code, 400)

    def test_token_is_bound_to_the_phone_it_was_issued_for(self):
        self.request_otp(); code = self.sent[-1][1]
        v = self.c.post("/auth/otp/verify", json={"phone": PHONE, "email": EMAIL, "code": code}).json()
        r = self.c.post("/auth/register", json={"name": "X", "phone": "9123456780", "password": PW, "verification_token": v["verification_token"]})
        self.assertEqual(r.status_code, 400)

    # ---- cooldown / rate limit
    def test_resend_cooldown_via_api(self):
        self.assertEqual(self.request_otp().status_code, 200)
        r = self.request_otp()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(self.sent), 1)

    def test_ip_rate_limit(self):
        with mock.patch("app.routers.auth.OTP_IP_LIMIT", 2):
            codes = [self.request_otp(email=f"u{i}@example.com", phone=f"98765432{i:02d}").status_code for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_verify_ip_rate_limit(self):
        self.request_otp()
        with mock.patch("app.routers.auth.VERIFY_IP_LIMIT", 3):
            codes = [self.c.post("/auth/otp/verify", json={"phone": PHONE, "email": EMAIL, "code": "000000"}).status_code for _ in range(4)]
        self.assertEqual(codes[-1], 429)

    # ---- delivery failure
    def test_delivery_failure_gives_generic_502_and_no_usable_code(self):
        DbCase.fail_delivery = True
        try:
            r = self.request_otp()
        finally:
            DbCase.fail_delivery = False
        self.assertEqual(r.status_code, 502)
        code = self.sent[-1][1]
        self.assertNotIn(code, r.text)
        self.assertEqual(self.c.post("/auth/otp/verify", json={"phone": PHONE, "email": EMAIL, "code": code}).status_code, 400)

    # ---- account enumeration
    def test_signup_with_an_already_registered_email_looks_like_a_normal_send(self):
        self.signup()
        before = len(self.sent)
        r = self.request_otp("signup", EMAIL, "9123456780")        # different phone, same email
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"sent": True, "cooldown": 60})
        self.assertEqual(len(self.sent), before)                     # nothing was actually emailed

    def test_reset_reply_is_identical_for_unknown_phone_wrong_email_and_real_account(self):
        self.signup()
        real = self.request_otp("reset", EMAIL, PHONE)
        unknown = self.request_otp("reset", "x@example.com", "9000000001")
        wrong_email = self.request_otp("reset", "other@example.com", PHONE)
        self.assertEqual({real.status_code, unknown.status_code, wrong_email.status_code}, {200})
        self.assertEqual(real.json(), unknown.json()); self.assertEqual(real.json(), wrong_email.json())
        self.assertEqual([to for to, _ in self.sent].count(EMAIL), 2)   # signup code + the one reset code; nobody else got mail

    # ---- password reset + purpose isolation
    def test_password_reset_works_and_old_code_cannot_be_reused(self):
        self.signup()
        self.age(EMAIL, "signup", 61)
        self.assertEqual(self.request_otp("reset").status_code, 200)
        code = self.sent[-1][1]
        body = {"phone": PHONE, "email": EMAIL, "code": code, "new_password": "brand-new-1"}
        self.assertEqual(self.c.post("/auth/password/reset", json=body).status_code, 200)
        self.assertEqual(self.c.post("/auth/password/reset", json=body).status_code, 400)       # replay
        self.assertEqual(self.c.post("/auth/login", json={"phone": PHONE, "password": "brand-new-1"}).status_code, 200)
        self.assertEqual(self.c.post("/auth/login", json={"phone": PHONE, "password": PW}).status_code, 401)

    def test_a_signup_code_cannot_reset_a_password(self):
        self.signup()
        self.age(EMAIL, "signup", 61)                                # get past the resend cooldown
        # Even a genuine signup-purpose code for this email must not work for reset:
        from app import otp
        from app.database import SessionLocal
        s = SessionLocal(); otp.issue(s, EMAIL, "signup"); s.close()
        signup_code = self.sent[-1][1]
        r = self.c.post("/auth/password/reset", json={"phone": PHONE, "email": EMAIL, "code": signup_code, "new_password": "hijacked-1"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.c.post("/auth/login", json={"phone": PHONE, "password": PW}).status_code, 200)

    def test_unknown_purpose_rejected(self):
        self.assertEqual(self.request_otp("login").status_code, 400)

    # ---- add email for old accounts
    def test_old_account_can_add_email_with_otp(self):
        from app.database import SessionLocal
        from app.models.core import User
        from app.auth import hash_password
        s = SessionLocal(); s.add(User(name="Old", phone="9811111111", password_hash=hash_password(PW))); s.commit(); s.close()
        tok = self.c.post("/auth/login", json={"phone": "9811111111", "password": PW}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        self.assertEqual(self.c.post("/auth/email/request", json={"email": "old@example.com"}, headers=h).status_code, 200)
        code = self.sent[-1][1]
        self.assertEqual(self.c.post("/auth/email/verify", json={"email": "old@example.com", "code": code}, headers=h).status_code, 200)
        self.assertTrue(self.c.get("/auth/me", headers=h).json()["has_email"])

    def test_config_endpoint_always_says_otp_required(self):
        self.assertEqual(self.c.get("/auth/config").json(), {"otp_required": True})


if __name__ == "__main__":
    unittest.main()
