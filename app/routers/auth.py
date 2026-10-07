from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import User, Profile
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, OtpRequest, OtpVerify, ResetPasswordRequest
from app.auth import hash_password, verify_password, create_access_token
from app import otp

router = APIRouter(prefix="/auth", tags=["Auth"])
GENERIC_SENT = {"sent": True, "cooldown": otp.COOLDOWN_S}


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


@router.get("/config")
def auth_config():
    """Tells the page that OTP is required (it always is; the code always goes by email)."""
    return {"otp_required": otp.OTP_REQUIRED}


@router.post("/otp/request")
def otp_request(payload: OtpRequest, db: Session = Depends(get_db)):
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
    return otp.issue(db, target, payload.purpose)


@router.post("/otp/verify")
def otp_verify(payload: OtpVerify, db: Session = Depends(get_db)):
    """Step 2 of signup: check the code. Returns a 15-minute token that /auth/register accepts for this phone only."""
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
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        phone = otp.normalize_phone(payload.phone)
    except HTTPException:
        phone = None
    user = _find_user(db, payload.phone, phone)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect phone number or password.")
    has_profile = db.query(Profile).filter(Profile.user_id == user.id).first() is not None
    return TokenResponse(access_token=create_access_token({"sub": user.id}),
                         user_id=user.id, name=user.name, has_profile=has_profile, is_admin=user.is_admin)


@router.post("/password/reset")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Forgot password: the code you received plus a new password."""
    phone = otp.normalize_phone(payload.phone)
    user = _find_user(db, payload.phone, phone)
    target = _reset_target(user, payload.email)
    if target is None or not otp.check(db, target, "reset", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired verification code.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"reset": True}
