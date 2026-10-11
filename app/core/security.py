import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from anyio import CapacityLimiter, to_thread

from app.config import get_settings

settings = get_settings()
_password_limiter = CapacityLimiter(4)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


async def hash_password_async(password: str) -> str:
    return await to_thread.run_sync(hash_password, password, limiter=_password_limiter)


async def verify_password_async(password: str, hashed_password: str) -> bool:
    return await to_thread.run_sync(
        verify_password, password, hashed_password, limiter=_password_limiter
    )


def create_access_token(user_id: uuid.UUID) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
