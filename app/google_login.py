"""
"Continue with Google": Google proves the person owns the email address, so no OTP email is needed.

GOOGLE_CLIENT_ID   the Web OAuth client ID from Google Cloud (it is public by design; there is no secret to keep)

The browser gets an ID token from Google and sends it here. We check its signature, audience (our client ID), expiry and
that Google marked the email as verified. Nothing else from the browser is trusted.
"""
import os
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from jose import jwt
from app.auth import SECRET_KEY, ALGORITHM


def client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def verify(credential: str) -> dict:
    """-> {"email", "name"} for a valid Google ID token whose email Google has verified; otherwise an HTTP error."""
    cid = client_id()
    if not cid:
        raise HTTPException(503, "Google sign-in is not set up on this server yet.")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        info = id_token.verify_oauth2_token(credential, grequests.Request(), cid, clock_skew_in_seconds=10)
    except Exception:
        raise HTTPException(401, "Google sign-in could not be verified. Please try again.")
    email = (info.get("email") or "").strip().lower()
    if not email or str(info.get("email_verified")).lower() != "true":
        raise HTTPException(400, "Your Google email is not verified, so it cannot be used.")
    return {"email": email, "name": (info.get("name") or email.split("@")[0]).strip()[:100]}


def make_signup_token(email: str, name: str) -> str:
    """Short-lived proof that Google verified this email; the only thing /auth/google/complete accepts."""
    return jwt.encode({"purpose": "google_signup", "email": email, "name": name,
                       "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)


def signup_claims(token: str | None) -> dict | None:
    try:
        p = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
    return p if p.get("purpose") == "google_signup" and p.get("email") else None
