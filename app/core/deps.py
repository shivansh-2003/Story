import asyncio
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import enforce_generation_rate_limit
from app.core.security import decode_access_token
from app.database import get_db
from app.users.models import User

bearer_scheme = HTTPBearer()
logger = logging.getLogger(__name__)
AUTH_DB_ATTEMPTS = 3

DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    # Authentication is a read-only first operation in this request's session.
    # A disconnect after pool_pre_ping can still fail this lookup; invalidate
    # the failed connection before retrying. Never replay endpoint writes.
    for attempt in range(AUTH_DB_ATTEMPTS):
        try:
            user = await db.get(User, user_id)
            break
        except (DBAPIError, TimeoutError, OSError) as error:
            if isinstance(error, DBAPIError) and not error.connection_invalidated:
                raise
            await db.invalidate()
            logger.warning(
                "Authentication database connection failed (attempt %d/%d, %s)",
                attempt + 1, AUTH_DB_ATTEMPTS, type(error).__name__,
            )
            if attempt == AUTH_DB_ATTEMPTS - 1:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Database temporarily unavailable. Please try again.",
                    headers={"Retry-After": "3"},
                ) from error
            await asyncio.sleep(attempt + 1)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def rate_limited_user(current_user: CurrentUser) -> User:
    await enforce_generation_rate_limit(current_user.id)
    return current_user


RateLimitedUser = Annotated[User, Depends(rate_limited_user)]
