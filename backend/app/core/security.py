from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/verify-pin")
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/verify-pin",
    auto_error=False,
)


def hash_secret(value: str) -> str:
    return pwd_context.hash(value)


def verify_secret(plain_value: str, hashed_value: str) -> bool:
    return pwd_context.verify(plain_value, hashed_value)


def create_access_token(data: dict[str, Any]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {**data, "exp": expires_at}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc


def get_current_subject(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    return decode_access_token(token)


def get_optional_subject(
    token: str | None = Depends(optional_oauth2_scheme),
) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        return decode_access_token(token)
    except HTTPException:
        return None


def require_role(required_role: str):
    def checker(subject: dict[str, Any] = Depends(get_current_subject)) -> dict[str, Any]:
        if subject.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return subject

    return checker


require_admin = require_role("admin")
require_student = require_role("student")
