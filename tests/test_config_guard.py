import unittest
from app import config_guard as g

GOOD = {"RENDER": "true", "JWT_SECRET": "x" * 40, "DATABASE_URL": "postgresql://u:p@h/db", "EMAIL_PROVIDER": "brevo"}


class ConfigGuard(unittest.TestCase):
    def test_good_production_config_passes(self):
        g.validate(dict(GOOD))

    def test_not_production_never_raises(self):
        g.validate({"OTP_DEV_ECHO": "true"})     # local development: nothing enforced

    def test_each_bypass_flag_is_rejected_in_production(self):
        for flag in g.BYPASS_FLAGS:
            with self.subTest(flag=flag):
                with self.assertRaises(RuntimeError):
                    g.validate({**GOOD, flag: "true"})

    def test_otp_required_false_rejected(self):
        for v in ("false", "0", "no", "off", ""):
            with self.subTest(v=v):
                with self.assertRaises(RuntimeError):
                    g.validate({**GOOD, "OTP_REQUIRED": v})
        g.validate({**GOOD, "OTP_REQUIRED": "true"})

    def test_weak_or_missing_secret_rejected(self):
        for secret in (None, "", g.DEV_SECRET, "short"):
            env = {k: v for k, v in GOOD.items() if k != "JWT_SECRET"}
            if secret is not None:
                env["JWT_SECRET"] = secret
            with self.subTest(secret=secret):
                with self.assertRaises(RuntimeError):
                    g.validate(env)

    def test_other_email_provider_and_redirected_brevo_rejected(self):
        with self.assertRaises(RuntimeError):
            g.validate({**GOOD, "EMAIL_PROVIDER": "console"})
        with self.assertRaises(RuntimeError):
            g.validate({**GOOD, "BREVO_API_BASE": "http://evil.example"})

    def test_missing_database_url_rejected(self):
        env = {k: v for k, v in GOOD.items() if k != "DATABASE_URL"}
        with self.assertRaises(RuntimeError):
            g.validate(env)

    def test_app_env_production_also_counts(self):
        env = {k: v for k, v in GOOD.items() if k != "RENDER"}
        env["APP_ENV"] = "production"; env["OTP_DEV_ECHO"] = "1"
        with self.assertRaises(RuntimeError):
            g.validate(env)

    def test_auth_module_uses_the_same_dev_secret_constant(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "auth.py").read_text()
        self.assertIn('os.getenv("JWT_SECRET", DEV_SECRET)', src)
        self.assertNotIn(g.DEV_SECRET, src)       # the literal lives only in config_guard.py


if __name__ == "__main__":
    unittest.main()
