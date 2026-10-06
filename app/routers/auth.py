from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import User, Profile
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, OtpRequest, OtpVerify, ResetPasswordRequest
from app.auth import hash_password, verify_password, create_access_token
from app import otp

router = APIRouter(prefix="/auth", tags=["Auth"])


def _find_user(db: Session, raw_phone: str, phone: str | None):
    """Older accounts may have the phone saved exactly as typed, so look for both forms."""
    forms = [p for p in {phone, (raw_phone or "").strip()} if p]
    return db.query(User).filter(User.phone.in_(forms)).first()


@router.post("/otp/request")
def otp_request(payload: OtpRequest, db: Session = Depends(get_db)):
    """Step 1 of signup or password reset: text a 6-digit code to the phone."""
    if payload.purpose not in ("signup", "reset"):
        raise HTTPException(400, "Unknown purpose")
    phone = otp.normalize_phone(payload.phone)
    exists = _find_user(db, payload.phone, phone)
    if payload.purpose == "signup" and exists:
        raise HTTPException(400, "This phone number is already registered. Try logging in instead.")
    if payload.purpose == "reset" and not exists:
        # Same reply as a real send, so nobody can use this to find out who has an account.
        return {"sent": True, "cooldown": otp.COOLDOWN_S}
    return otp.issue(db, phone, payload.purpose)


@router.post("/otp/verify")
def otp_verify(payload: OtpVerify, db: Session = Depends(get_db)):
    """Step 2 of signup: check the code. Returns a 15-minute token that /auth/register accepts for this phone only."""
    phone = otp.normalize_phone(payload.phone)
    if not otp.check(db, phone, "signup", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired code.")
    return {"verified": True, "verification_token": otp.make_verification_token(phone)}


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    phone = otp.normalize_phone(payload.phone)
    if otp.OTP_REQUIRED and not otp.valid_verification_token(payload.verification_token, phone):
        raise HTTPException(400, "Please verify your phone number with the OTP first.")
    if _find_user(db, payload.phone, phone):
        raise HTTPException(400, "This phone number is already registered. Try logging in instead.")
    # The very first account on a fresh database becomes the admin.
    is_first_user = db.query(User).count() == 0
    user = User(name=payload.name.strip(), phone=phone, password_hash=hash_password(payload.password), is_admin=is_first_user)
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
    """Forgot password: the texted code plus a new password."""
    phone = otp.normalize_phone(payload.phone)
    user = _find_user(db, payload.phone, phone)
    if not user or not otp.check(db, phone, "reset", payload.code.strip()):
        raise HTTPException(400, "Invalid or expired code.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"reset": True}
