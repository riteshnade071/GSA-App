"""OTP rules: 6 digits, valid 5 minutes, max 5 wrong tries per code, 60 s between sends, 5 sends per email per hour.
Codes go by email (Brevo) only. Only a keyed hash is stored. A new code cancels every older one for the same email + purpose."""
import hmac, hashlib, re, secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import text
from sqlalchemy.orm import Session
from app import mailer, ratelimit
from app.auth import SECRET_KEY, ALGORITHM
from app.models.core import OtpCode

OTP_REQUIRED = True            # always on: there is no setting that skips verification
COOLDOWN_S, MAX_PER_HOUR, MAX_ATTEMPTS = 60, 5, 5
OTP_MINUTES = mailer.OTP_MINUTES
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
CODE_RE = re.compile(r"[0-9]{6}")
# One fixed wording for both throttles, so the reply never depends on whether an account exists.
COOLDOWN_MSG = f"Please wait {COOLDOWN_S} seconds before asking for another OTP."
HOURLY_MSG = "Too many OTP requests for this email. Please try again after an hour."


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    # email + purpose are part of the hash, so a code for one purpose can never verify for another.
    return hmac.new(SECRET_KEY.encode(), f"{email}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()


def throttle_unsent(email: str, purpose: str) -> None:
    """Applies the same cooldown / hourly limits to requests where NO code is sent (unknown account, email already registered),
    so the reply (429 or not) is identical whether or not an account exists."""
    ratelimit.hit(f"otp-cool:{purpose}:{email}", 1, COOLDOWN_S, COOLDOWN_MSG)
    ratelimit.hit(f"otp-hour:{purpose}:{email}", MAX_PER_HOUR, 3600, HOURLY_MSG)


def _serialize(db: Session, email: str, purpose: str) -> None:
    """On PostgreSQL, make concurrent requests for the same email + purpose wait for each other (released at commit/rollback),
    so two simultaneous requests cannot both slip past the cooldown or the hourly limit."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"otp|{email}|{purpose}"})


def _cancel(db: Session, row_id: str) -> None:
    """Make an undelivered code unusable (delete it; if that fails, mark it used)."""
    try:
        db.rollback()
        db.query(OtpCode).filter(OtpCode.id == row_id).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        try:
            db.query(OtpCode).filter(OtpCode.id == row_id).update({"used": True}, synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()


def issue(db: Session, email: str, purpose: str) -> dict:
    """Make a new code for this email + purpose and send it through Brevo.
    Every older unused code for the same email + purpose stops working the moment the new one exists;
    if Brevo does not accept the email, the new code is cancelled too, so an undelivered code can never be used."""
    now = _now()
    _serialize(db, email, purpose)
    last = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < COOLDOWN_S:
        db.rollback()
        raise HTTPException(429, COOLDOWN_MSG)
    sent_last_hour = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose,
                                              OtpCode.created_at >= now - timedelta(hours=1)).count()
    if sent_last_hour >= MAX_PER_HOUR:
        db.rollback()
        raise HTTPException(429, HOURLY_MSG)
    code = f"{secrets.randbelow(10**6):06d}"
    db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose, OtpCode.used == False  # noqa: E712
                             ).update({"used": True}, synchronize_session=False)
    row = OtpCode(phone=email, purpose=purpose, code_hash=_hash(email, purpose, code), created_at=now,
                  expires_at=now + timedelta(minutes=OTP_MINUTES), attempts=0, used=False)
    db.add(row)
    db.commit()                      # one transaction: old codes cancelled + new code stored (also releases the lock)
    row_id = row.id
    try:
        mailer.send_email(email, code)
    except Exception as e:           # never log the code, the API key or the address
        detail = f" {e}" if isinstance(e, RuntimeError) else (f" (HTTP {e.code})" if getattr(e, "code", None) else "")
        print(f"[OTP] email delivery failed: {type(e).__name__}{detail}", flush=True)
        _cancel(db, row_id)
        raise HTTPException(502, "Unable to send verification email. Please try again later.")
    return {"sent": True, "cooldown": COOLDOWN_S}


def check(db: Session, email: str, purpose: str, code: str) -> bool:
    """True only for the newest unused, unexpired code of this email + purpose, within 5 tries. A correct code works once.
    Both the attempt counter and the 'used' flag are changed with single conditional UPDATE statements, so parallel requests
    can neither exceed 5 tries nor consume the same code twice."""
    code = (code or "").strip()
    if not CODE_RE.fullmatch(code):
        return False                 # not even shaped like a code: do not spend an attempt
    now = _now()
    row = db.query(OtpCode).filter(OtpCode.phone == email, OtpCode.purpose == purpose, OtpCode.used == False,  # noqa: E712
                                   OtpCode.expires_at >= now).order_by(OtpCode.created_at.desc()).first()
    if not row:
        return False
    row_id, stored_hash = row.id, row.code_hash
    claimed = db.query(OtpCode).filter(OtpCode.id == row_id, OtpCode.used == False, OtpCode.attempts < MAX_ATTEMPTS,  # noqa: E712
                                       OtpCode.expires_at >= now).update({"attempts": OtpCode.attempts + 1}, synchronize_session=False)
    db.commit()                      # the try is counted even if the answer below is wrong
    if claimed != 1:
        return False                 # no tries left, expired, or somebody else just used it
    if not hmac.compare_digest(stored_hash, _hash(email, purpose, code)):
        return False
    consumed = db.query(OtpCode).filter(OtpCode.id == row_id, OtpCode.used == False  # noqa: E712
                                        ).update({"used": True}, synchronize_session=False)
    db.commit()
    return consumed == 1             # exactly one of any number of parallel correct requests gets 1


def make_verification_token(phone: str, email: str) -> str:
    return jwt.encode({"sub": phone, "purpose": "signup_verified", "channel": "email", "email": email,
                       "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)


def verification_claims(token: str | None, phone: str) -> dict | None:
    """The token's claims if it is a valid signup-verification token (with a verified email) for exactly this phone, else None."""
    try:
        p = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
    return p if p.get("purpose") == "signup_verified" and p.get("sub") == phone and p.get("email") else None
