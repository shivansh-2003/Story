import logging
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import router as auth
from app.chapters import router as chapters
from app.characters import router as characters
from app.core.logging_config import setup_logging
from app.database import engine
from app.core.schema import check_schema_revision
from app.core.llm_client import close_model_clients
from app.core.redis_client import close_redis_client
from app.core.errors import DomainError
from app.generation import router as generation
from app.stories import router as stories
from app.transfers import router as transfers
from app.planning import router as planning
from app.rewriting import router as rewriting
from app.transfers.upload_limit import ImportUploadLimit
from app.manuscript import router as manuscript
from app.jobs.worker import run_worker

setup_logging()
logger = logging.getLogger("story_assistant")

ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:4173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Never partially change an existing schema on boot. Migrate explicitly first.
    worker = None
    try:
        async with engine.connect() as conn:
            await check_schema_revision(conn)
        worker = asyncio.create_task(run_worker())
        yield
    finally:
        if worker is not None:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        try:
            await close_model_clients()
            await close_redis_client()
        finally:
            await engine.dispose()


app = FastAPI(title="Story Assistant API", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_error_response(request: Request, error: DomainError):
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ImportUploadLimit)


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


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    # End-to-end per-request timing without decorating every route function
    # individually — @log_execution covers the service layer, this covers
    # the router boundary. Method, path, status, latency only — never the
    # request/response body.
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(stories.router)
app.include_router(chapters.router)
app.include_router(generation.router)
app.include_router(manuscript.router)
app.include_router(transfers.router)
app.include_router(planning.router)
app.include_router(rewriting.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
