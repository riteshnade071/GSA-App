from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import Profile, User
from app.schemas.schemas import ProfileIn, ProfileOut
from app.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=ProfileOut | None)
def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Profile).filter(Profile.user_id == current_user.id).first()


@router.post("", response_model=ProfileOut)
def save_profile(payload: ProfileIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create or update — onboarding and 'edit my details' hit the same endpoint."""
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    else:
        profile = Profile(user_id=current_user.id, **payload.model_dump())
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
