"""OTP rules: 6 digits, 10 minutes, max 5 wrong tries per code, 30 s between sends, 5 sends per email per hour. Codes go by email (Brevo) only."""
import hmac, hashlib, re, secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session
from app import mailer
from app.auth import SECRET_KEY, ALGORITHM
from app.models.core import OtpCode

OTP_REQUIRED = True            # always on: there is no setting that skips verification
COOLDOWN_S, MAX_PER_HOUR, MAX_ATTEMPTS = 30, 5, 5
OTP_MINUTES = mailer.OTP_MINUTES
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def normalize_email(raw: str) -> str:
    e = (raw or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.match(e):
        raise HTTPException(400, "Enter a valid email address.")
    return e


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(400, "Enter a valid 10-digit Indian mobile number.")
    return digits


def _hash(email: str, purpose: str, code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"{email}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()


def issue(db: Session, email: str, purpose: str) -> dict:
    """Make a new code for this email and send it through Brevo. Any older unused code for the same email+purpose stops working."""
    now = datetime.utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < COOLDOWN_S:
        wait = int(COOLDOWN_S - (now - last.created_at).total_seconds()) + 1
        raise HTTPException(429, f"Please wait {wait} seconds before asking for another OTP.")
    sent_last_hour = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose,
                                              OtpCode.created_at >= now - timedelta(hours=1)).count()
    if sent_last_hour >= MAX_PER_HOUR:
        raise HTTPException(429, "Too many OTP requests for this email. Please try again after an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    row = OtpCode(phone=email, purpose=purpose, code_hash=_hash(email, purpose, code), expires_at=now + timedelta(minutes=OTP_MINUTES))
    db.add(row); db.commit()
    try:
        mailer.send_email(email, code)
    except Exception as e:            # never log the code or the API key
        print(f"[OTP] sending email failed: {type(e).__name__}: {e}", flush=True)
        db.delete(row); db.commit()
        raise HTTPException(502, "Unable to send verification email. Please try again later.")
    # Only after the email really went out does the new code replace the older ones.
    db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose, OtpCode.used == False,  # noqa: E712
                             OtpCode.id != row.id).update({"used": True})
    db.commit()
    return {"sent": True, "cooldown": COOLDOWN_S}


def check(db: Session, email: str, purpose: str, code: str) -> bool:
    """True only for the newest unused, unexpired code of this email+purpose, within 5 tries. A correct code works once."""
    row = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose, OtpCode.used == False,  # noqa: E712
                                   OtpCode.expires_at >= datetime.utcnow()).order_by(OtpCode.created_at.desc()).first()
    if not row or row.attempts >= MAX_ATTEMPTS:
        return False
    row.attempts += 1
    ok = hmac.compare_digest(row.code_hash, _hash(email, purpose, code or ""))
    if ok:
        row.used = True
    db.commit()
    return ok


def make_verification_token(phone: str, email: str) -> str:
    return jwt.encode({"sub": phone, "purpose": "signup_verified", "channel": "email", "email": email,
                       "exp": datetime.utcnow() + timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)


def verification_claims(token: str | None, phone: str) -> dict | None:
    """The token's claims if it is a valid signup-verification token (with a verified email) for exactly this phone, else None."""
    try:
        p = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
    return p if p.get("purpose") == "signup_verified" and p.get("sub") == phone and p.get("email") else None
