import os, time
from datetime import datetime, timedelta, timezone
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.core import User

SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS), "iat": int(time.time())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials. Please log in again.",
                        headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise exc
    except JWTError:
        raise exc
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise exc
    if user.password_changed_at:      # password was reset: logins from before that are no longer valid
        changed = int(user.password_changed_at.replace(tzinfo=timezone.utc).timestamp())
        if payload.get("iat") is None or payload["iat"] < changed:
            raise exc
    return user
