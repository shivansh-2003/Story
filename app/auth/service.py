from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.users.models import User


async def create_user(db: AsyncSession, email: str, password: str) -> User | None:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        return None

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.hashed_password is None or not verify_password(password, user.hashed_password):
        return None
    return user
