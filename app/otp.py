"""OTP rules: 6 digits, 10 minutes, max 5 wrong tries per code, 30 s between sends, 5 sends per phone per hour."""
import hmac, hashlib, os, re, secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session
from app import sms
from app.auth import SECRET_KEY, ALGORITHM
from app.models.core import OtpCode

OTP_REQUIRED = os.getenv("OTP_REQUIRED", "true").lower() != "false"     # set OTP_REQUIRED=false to switch phone verification off
DEV_ECHO = os.getenv("OTP_DEV_ECHO", "false").lower() == "true"          # TESTING ONLY: puts the code in the API reply
COOLDOWN_S, MAX_PER_HOUR, MAX_ATTEMPTS = 30, 5, 5


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise HTTPException(400, "Enter a valid 10-digit Indian mobile number.")
    return digits


def _hash(phone: str, purpose: str, code: str) -> str:
    return hmac.new(SECRET_KEY.encode(), f"{phone}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()


def issue(db: Session, phone: str, purpose: str) -> dict:
    now = datetime.utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.purpose == purpose).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < COOLDOWN_S:
        wait = int(COOLDOWN_S - (now - last.created_at).total_seconds()) + 1
        raise HTTPException(429, f"Please wait {wait} seconds before asking for another OTP.")
    sent_last_hour = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.purpose == purpose,
                                              OtpCode.created_at >= now - timedelta(hours=1)).count()
    if sent_last_hour >= MAX_PER_HOUR:
        raise HTTPException(429, "Too many OTP requests for this number. Please try again after an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    row = OtpCode(phone=phone, purpose=purpose, code_hash=_hash(phone, purpose, code), expires_at=now + timedelta(minutes=sms.OTP_MINUTES))
    db.add(row); db.commit()
    try:
        sms.send_sms(phone, code)
    except Exception as e:            # never log the code itself
        print(f"[OTP] SMS sending failed: {type(e).__name__}: {e}", flush=True)
        db.delete(row); db.commit()
        raise HTTPException(502, "Could not send the SMS right now. Please try again in a minute.")
    reply = {"sent": True, "cooldown": COOLDOWN_S}
    if DEV_ECHO:
        reply["dev_otp"] = code
    return reply


def check(db: Session, phone: str, purpose: str, code: str) -> bool:
    """True only for the newest unused, unexpired code of this phone+purpose, within 5 tries. A correct code works once."""
    row = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.purpose == purpose, OtpCode.used == False,  # noqa: E712
                                   OtpCode.expires_at >= datetime.utcnow()).order_by(OtpCode.created_at.desc()).first()
    if not row or row.attempts >= MAX_ATTEMPTS:
        return False
    row.attempts += 1
    ok = hmac.compare_digest(row.code_hash, _hash(phone, purpose, code or ""))
    if ok:
        row.used = True
    db.commit()
    return ok


def make_verification_token(phone: str) -> str:
    return jwt.encode({"sub": phone, "purpose": "signup_verified", "exp": datetime.utcnow() + timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)


def valid_verification_token(token: str | None, phone: str) -> bool:
    try:
        p = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return False
    return p.get("purpose") == "signup_verified" and p.get("sub") == phone
