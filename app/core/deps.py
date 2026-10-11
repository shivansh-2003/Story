import asyncio
import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter
from app.characters.models import Character
from app.core.rate_limit import enforce_generation_rate_limit
from app.core.security import decode_access_token
from app.database import get_db
from app.stories.models import Story
from app.users.models import User

bearer_scheme = HTTPBearer()
logger = logging.getLogger(__name__)
AUTH_DB_ATTEMPTS = 3

DbSession = Annotated[AsyncSession, Depends(get_db)]


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


async def get_owned_story(db: AsyncSession, story_id: uuid.UUID, user: User, *, for_update: bool = False) -> Story:
    if for_update:
        story = await db.scalar(select(Story).where(Story.id == story_id).with_for_update()
                                .execution_options(populate_existing=True))
    else:
        story = await db.get(Story, story_id)
    if story is None or story.is_archived or story.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Story not found")
    return story


async def get_owned_character(db: AsyncSession, character_id: uuid.UUID, user: User) -> Character:
    character = await db.get(Character, character_id)
    if character is None or character.is_archived or character.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


async def get_owned_chapter(db: AsyncSession, story_id: uuid.UUID, chapter_id: uuid.UUID, user: User) -> Chapter:
    # single joined query instead of a separate story-ownership round trip
    # followed by a chapter fetch — same checks, one Neon round trip.
    result = await db.execute(
        select(Chapter)
        .join(Story, Story.id == Chapter.story_id)
        .where(
            Chapter.id == chapter_id,
            Chapter.story_id == story_id,
            Chapter.is_archived.is_(False),
            Story.user_id == user.id,
            Story.is_archived.is_(False),
        )
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return chapter
