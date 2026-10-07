"""OTP rules: 6 digits, 10 minutes, max 5 wrong tries per code, 30 s between sends, 5 sends per phone per hour."""
import hmac, hashlib, os, re, secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session
from app import mailer, sms, whatsapp
from app.auth import SECRET_KEY, ALGORITHM
from app.models.core import OtpCode

OTP_REQUIRED = os.getenv("OTP_REQUIRED", "true").lower() != "false"     # set OTP_REQUIRED=false to switch phone verification off
DEV_ECHO = os.getenv("OTP_DEV_ECHO", "false").lower() == "true"          # TESTING ONLY: puts the code in the API reply
COOLDOWN_S, MAX_PER_HOUR, MAX_ATTEMPTS = 30, 5, 5
CHANNELS = ("sms", "whatsapp", "email")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def available_channels() -> dict:
    """Which ways of getting a code really work right now (a provider other than 'console' is set), so the page only offers those."""
    def real(var): return os.getenv(var, "console").lower() != "console"
    return {"sms": DEV_ECHO or real("SMS_PROVIDER"), "whatsapp": DEV_ECHO or real("WHATSAPP_PROVIDER"), "email": DEV_ECHO or real("EMAIL_PROVIDER")}


def normalize_email(raw: str) -> str:
    e = (raw or "").strip().lower()
    if len(e) > 254 or not EMAIL_RE.match(e):
        raise HTTPException(400, "Enter a valid email address.")
    return e


def target_for(channel: str, phone: str, email: str | None) -> str:
    """Where the code goes: the phone for SMS/WhatsApp, the email address for email."""
    if channel in ("sms", "whatsapp"):
        return phone
    if channel == "email":
        return normalize_email(email)
    raise HTTPException(400, "Unknown verification method.")


def _deliver(channel: str, target: str, code: str) -> None:
    if channel == "sms": sms.send_sms(target, code)
    elif channel == "whatsapp": whatsapp.send_whatsapp(target, code)
    else: mailer.send_email(target, code)


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


def issue(db: Session, phone: str, purpose: str, channel: str = "sms") -> dict:
    now = datetime.utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.purpose == purpose).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < COOLDOWN_S:
        wait = int(COOLDOWN_S - (now - last.created_at).total_seconds()) + 1
        raise HTTPException(429, f"Please wait {wait} seconds before asking for another OTP.")
    sent_last_hour = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.purpose == purpose,
                                              OtpCode.created_at >= now - timedelta(hours=1)).count()
    if sent_last_hour >= MAX_PER_HOUR:
        raise HTTPException(429, "Too many OTP requests for this number or email. Please try again after an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    row = OtpCode(phone=phone, purpose=purpose, code_hash=_hash(phone, purpose, code), expires_at=now + timedelta(minutes=sms.OTP_MINUTES))
    db.add(row); db.commit()
    try:
        _deliver(channel, phone, code)
    except Exception as e:            # never log the code itself
        print(f"[OTP] sending by {channel} failed: {type(e).__name__}: {e}", flush=True)
        db.delete(row); db.commit()
        raise HTTPException(502, "Could not send the code right now. Please try again in a minute or use another method.")
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


def make_verification_token(phone: str, channel: str = "sms", email: str | None = None) -> str:
    return jwt.encode({"sub": phone, "purpose": "signup_verified", "channel": channel, "email": email,
                       "exp": datetime.utcnow() + timedelta(minutes=15)}, SECRET_KEY, algorithm=ALGORITHM)


def verification_claims(token: str | None, phone: str) -> dict | None:
    """The token's claims if it is a valid signup-verification token for exactly this phone, else None."""
    try:
        p = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
    return p if p.get("purpose") == "signup_verified" and p.get("sub") == phone else None
