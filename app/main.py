import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth
from app.chapters import router as chapters
from app.characters import router as characters
from app.database import Base, engine
from app.generation import router as generation
from app.stories import router as stories

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("story_assistant")

ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:4173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # no migration tool — tables are created straight from the current models
    # on boot. Fine for a single-schema-owner project; move to Alembic if
    # this ever needs versioned migrations against a shared/prod database.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Story Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_disallowed_origins(request: Request, call_next):
    # uvicorn's own access log shows path + status but not the Origin header,
    # which is the one thing you need to diagnose a CORS rejection — surface
    # it here instead of guessing from timestamps.
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        logger.warning(
            "CORS rejected: %s %s from origin=%s (allowed: %s)",
            request.method,
            request.url.path,
            origin,
            ALLOWED_ORIGINS,
        )
    return await call_next(request)


app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(stories.router)
app.include_router(chapters.router)
app.include_router(generation.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
