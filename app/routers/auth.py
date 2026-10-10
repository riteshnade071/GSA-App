import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import User, Profile
from app.schemas.schemas import (RegisterRequest, LoginRequest, TokenResponse, OtpRequest, OtpVerify, ResetPasswordRequest,
                                 AddEmailRequest, AddEmailVerify)
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app import mailer, otp, ratelimit

router = APIRouter(prefix="/auth", tags=["Auth"])
GENERIC_SENT = {"sent": True, "cooldown": otp.COOLDOWN_S}
OTP_IP_LIMIT = int(os.getenv("OTP_IP_LIMIT", "10"))            # code emails per IP per hour
VERIFY_IP_LIMIT = int(os.getenv("VERIFY_IP_LIMIT", "40"))      # code checks per IP per hour
LOGIN_FAIL_LIMIT = int(os.getenv("LOGIN_FAIL_LIMIT", "8"))     # wrong passwords per IP+phone per 15 minutes


def _find_user(db: Session, raw_phone: str, phone: str | None):
    """Older accounts may have the phone saved exactly as typed, so look for both forms."""
    forms = [p for p in {phone, (raw_phone or "").strip()} if p]
    return db.query(User).filter(User.phone.in_(forms)).first()


def _reset_target(user: User | None, email: str) -> str | None:
    """Where a reset code may go. None = nothing to send (unknown account, or the email is not the one on file)."""
    if not user:
        return None
    em = otp.normalize_email(email)
    return em if user.email and user.email == em else None


def _mask(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return name[:1] + "***@" + domain


def _limit_email_sends(request: Request) -> None:
    ratelimit.hit(f"otp:{ratelimit.client_ip(request)}", OTP_IP_LIMIT, 3600, "Too many code requests from this network. Please try again later.")


def _limit_checks(request: Request) -> None:
    ratelimit.hit(f"verify:{ratelimit.client_ip(request)}", VERIFY_IP_LIMIT, 3600, "Too many attempts from this network. Please try again later.")


@router.get("/config")
def auth_config():
    """Tells the page that OTP is required (it always is; the code always goes by email)."""
    return {"otp_required": otp.OTP_REQUIRED}


@router.get("/email-status")
def email_status(user: User = Depends(get_current_user)):
    """Admin only: is email sending set up properly, and will Gmail accept it?"""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return mailer.status()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"name": user.name, "phone": user.phone, "is_admin": user.is_admin, "has_email": bool(user.email), "email_hint": _mask(user.email)}


@router.post("/otp/request")
def otp_request(payload: OtpRequest, request: Request, db: Session = Depends(get_db)):
    """Step 1 of signup or password reset: send a 6-digit code to the email address."""
    if payload.purpose not in ("signup", "reset"):
        raise HTTPException(400, "Unknown purpose")
    phone = otp.normalize_phone(payload.phone)
    user = _find_user(db, payload.phone, phone)
    if payload.purpose == "signup":
        if user:
            raise HTTPException(400, "This phone number is already registered. Try logging in instead.")
        target = otp.normalize_email(payload.email)
        if db.query(User).filter(User.email == target).first():
            raise HTTPException(400, "This email is already registered. Try logging in instead.")
    else:
        target = _reset_target(user, payload.email)
        if target is None:
            return GENERIC_SENT          # identical reply, so nobody can use this to find out who has an account
    _limit_email_sends(request)
    return otp.issue(db, target, payload.purpose)


@router.post("/otp/verify")
def otp_verify(payload: OtpVerify, request: Request, db: Session = Depends(get_db)):
    """Step 2 of signup: check the code. Returns a 15-minute token that /auth/register accepts for this phone only."""
    _limit_checks(request)
    phone = otp.normalize_phone(payload.phone)
    email = otp.normalize_email(payload.email)
    if not otp.check(db, email, "signup", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired verification code.")
    return {"verified": True, "verification_token": otp.make_verification_token(phone, email)}


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    phone = otp.normalize_phone(payload.phone)
    claims = otp.verification_claims(payload.verification_token, phone)
    if not claims:
        raise HTTPException(400, "Please verify your email with the OTP first.")
    if _find_user(db, payload.phone, phone):
        raise HTTPException(400, "This phone number is already registered. Try logging in instead.")
    email = claims["email"]
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "This email is already registered. Try logging in instead.")
    # The very first account on a fresh database becomes the admin.
    is_first_user = db.query(User).count() == 0
    user = User(name=payload.name.strip(), phone=phone, password_hash=hash_password(payload.password), is_admin=is_first_user,
                email=email, verified_via="email")
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token({"sub": user.id}),
                         user_id=user.id, name=user.name, has_profile=False, is_admin=user.is_admin)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        phone = otp.normalize_phone(payload.phone)
    except HTTPException:
        phone = None
    key = f"login:{ratelimit.client_ip(request)}:{phone or (payload.phone or '').strip()}"
    if ratelimit.failures(key, 900) >= LOGIN_FAIL_LIMIT:
        raise HTTPException(429, "Too many wrong attempts. Please wait 15 minutes, or use Forgot password.")
    user = _find_user(db, payload.phone, phone)
    if not user or not verify_password(payload.password, user.password_hash):
        ratelimit.record(key)
        raise HTTPException(401, "Incorrect phone number or password.")
    ratelimit.clear(key)
    has_profile = db.query(Profile).filter(Profile.user_id == user.id).first() is not None
    return TokenResponse(access_token=create_access_token({"sub": user.id}),
                         user_id=user.id, name=user.name, has_profile=has_profile, is_admin=user.is_admin)


@router.post("/password/reset")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Forgot password: the code you received plus a new password. Every login from before the reset stops working."""
    _limit_checks(request)
    phone = otp.normalize_phone(payload.phone)
    user = _find_user(db, payload.phone, phone)
    target = _reset_target(user, payload.email)
    if target is None or not otp.check(db, target, "reset", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired verification code.")
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.utcnow()
    db.commit()
    return {"reset": True}


# ---- accounts that have no email yet (created before email verification existed) ----
@router.post("/email/request")
def email_request(payload: AddEmailRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.email:
        raise HTTPException(400, "Your account already has a verified email.")
    email = otp.normalize_email(payload.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "This email is already used by another account.")
    _limit_email_sends(request)
    return otp.issue(db, email, "add_email")


@router.post("/email/verify")
def email_verify(payload: AddEmailVerify, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.email:
        raise HTTPException(400, "Your account already has a verified email.")
    _limit_checks(request)
    email = otp.normalize_email(payload.email)
    if not otp.check(db, email, "add_email", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired verification code.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "This email is already used by another account.")
    user.email, user.verified_via = email, "email"
    db.commit()
    return {"email_added": True, "email_hint": _mask(email)}
