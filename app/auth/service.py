from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.logging_utils import log_execution
from app.core.security import hash_password_async, verify_password_async
from app.users.models import User


@log_execution
async def create_user(db: AsyncSession, email: str, password: str) -> User | None:
    existing = await db.scalar(select(User.id).where(User.email == email))
    await db.rollback()  # Release the read connection before expensive hashing.
    if existing is not None:
        return None

    user = User(email=email, hashed_password=await hash_password_async(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Another signup may have inserted this email after the first lookup.
        if await db.scalar(select(User.id).where(User.email == email)) is not None:
            return None
        raise
    await db.refresh(user)
    return user


@log_execution
async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        db.expunge(user)  # Preserve loaded fields across rollback without a connection.
    await db.rollback()
    if user is None or user.hashed_password is None or not await verify_password_async(password, user.hashed_password):
        return None
    return user
