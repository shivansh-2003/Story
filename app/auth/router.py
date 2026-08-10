from fastapi import APIRouter, HTTPException, status

from app.auth.schemas import LoginRequest, SignupRequest, Token, UserRead
from app.auth.service import authenticate_user, create_user
from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=Token)
async def signup(body: SignupRequest, db: DbSession) -> Token:
    user = await create_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: DbSession) -> Token:
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> User:
    return current_user
