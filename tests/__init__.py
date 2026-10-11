"""Test environment. Runs BEFORE any app module is imported (unittest imports this package first).
Everything here is test-only: a throw-away SQLite file and fake settings. Nothing in app/ reads a test mode."""
import os, tempfile

_dir = tempfile.mkdtemp(prefix="ohub-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_dir}/test.db"
os.environ["JWT_SECRET"] = "unit-test-secret-not-used-anywhere-else-0123456789"
os.environ["EMAIL_PROVIDER"] = "brevo"
os.environ["BREVO_API_KEY"] = "test-api-key"
os.environ["EMAIL_FROM"] = "no-reply@example.com"
for _k in ("RENDER", "APP_ENV", "OTP_DEV_ECHO", "OTP_REQUIRED", "BREVO_API_BASE"):
    os.environ.pop(_k, None)
