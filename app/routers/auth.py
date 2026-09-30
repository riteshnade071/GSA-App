from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import User, Profile
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(400, "This phone number is already registered. Try logging in instead.")
    # The very first account on a fresh database becomes the admin — simplest
    # possible bootstrap for a single-admin tool, with zero extra setup step.
    is_first_user = db.query(User).count() == 0
    user = User(name=payload.name, phone=payload.phone, password_hash=hash_password(payload.password),
               is_admin=is_first_user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token({"sub": user.id}),
                         user_id=user.id, name=user.name, has_profile=False, is_admin=user.is_admin)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == payload.phone).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect phone number or password.")
    has_profile = db.query(Profile).filter(Profile.user_id == user.id).first() is not None
    return TokenResponse(access_token=create_access_token({"sub": user.id}),
                         user_id=user.id, name=user.name, has_profile=has_profile, is_admin=user.is_admin)
