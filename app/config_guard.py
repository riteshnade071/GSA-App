"""Refuses to start a PRODUCTION server with a test or bypass setting.

Production = APP_ENV is `production`/`prod`, or Render's own `RENDER` variable is present.
There is no code anywhere that echoes, skips or fakes OTPs, so these checks are a second lock: if somebody
adds such a switch to the Render environment by mistake, the server stops instead of silently running unsafely.
Pure standard library on purpose, so it can be tested without the web framework.
"""
import os

DEV_SECRET = "dev-only-insecure-secret-change-me"     # the fallback in app/auth.py when JWT_SECRET is missing
MIN_SECRET_LEN = 16
TRUTHY = {"1", "true", "yes", "on", "y"}
# None of these exist in the code. If one is set in production, something is wrong.
BYPASS_FLAGS = ("OTP_DEV_ECHO", "OTP_ECHO", "OTP_DEBUG", "OTP_BYPASS", "OTP_TEST_MODE", "OTP_FAKE", "SKIP_OTP", "DISABLE_OTP")
BREVO_HOST = "https://api.brevo.com"


def is_production(env=None) -> bool:
    env = os.environ if env is None else env
    return (env.get("APP_ENV", "").strip().lower() in ("production", "prod")) or bool(env.get("RENDER"))


def problems(env=None) -> list[str]:
    """Everything that makes this environment unsafe for production (empty list = fine)."""
    env = os.environ if env is None else env
    found = []
    for flag in BYPASS_FLAGS:
        if env.get(flag, "").strip().lower() in TRUTHY:
            found.append(f"{flag} is enabled. OTP test/bypass modes are not allowed in production. Remove it.")
    required = env.get("OTP_REQUIRED")
    if required is not None and required.strip().lower() not in TRUTHY:
        found.append("OTP_REQUIRED is set to a false value. Verification can never be switched off in production. Remove it.")
    secret = env.get("JWT_SECRET", "")
    if not secret or secret == DEV_SECRET:
        found.append("JWT_SECRET is missing (or is the development default). Set a long random secret.")
    elif len(secret) < MIN_SECRET_LEN:
        found.append(f"JWT_SECRET is shorter than {MIN_SECRET_LEN} characters. Use a long random secret.")
    provider = env.get("EMAIL_PROVIDER", "").strip().lower()
    if provider and provider != "brevo":
        found.append(f"EMAIL_PROVIDER is '{provider}'. Only 'brevo' is allowed in production.")
    base = env.get("BREVO_API_BASE", "").strip()
    if base and not base.startswith(BREVO_HOST):
        found.append("BREVO_API_BASE points somewhere other than api.brevo.com. Remove it in production.")
    if not env.get("DATABASE_URL"):
        found.append("DATABASE_URL is not set (the server would use a local development database).")
    return found


def validate(env=None) -> None:
    """Raise at start-up when production is configured unsafely. Outside production this does nothing."""
    if not is_production(env):
        return
    found = problems(env)
    if found:
        raise RuntimeError("Refusing to start: insecure production configuration:\n - " + "\n - ".join(found))
