import logging
import time
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

connect_args = {"ssl": "require"} if settings.database_ssl_require else {}

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # Neon drops idle connections; check liveness before handing one out
    pool_recycle=300,  # proactively retire connections before Neon's idle timeout
    connect_args=connect_args,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    # duration only — never the statement or its parameters, to avoid
    # leaking data into logs. Fires unconditionally; logger.debug() is a
    # no-op unless LOG_LEVEL=DEBUG, so this is silent at the INFO default.
    start = conn.info["query_start_time"].pop()
    logger.debug("query took %.1fms", (time.perf_counter() - start) * 1000)


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


_last_release_at: float | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    global _last_release_at
    start = time.perf_counter()
    async with async_session() as session:
        wait_ms = (time.perf_counter() - start) * 1000
        if wait_ms > 50:
            # distinguishes two causes that look identical from the outside
            # (a slow request next to a fast one): a large idle_gap points at
            # Neon compute auto-suspend/cold-start; a high checked_out count
            # relative to pool_size points at concurrent-request pool
            # contention (e.g. duplicate frontend fetches) instead.
            pool = engine.sync_engine.pool
            gap_s = None if _last_release_at is None else start - _last_release_at
            logger.warning(
                "connection acquisition took %.1fms (checked_out=%s overflow=%s idle_gap=%s)",
                wait_ms,
                pool.checkedout(),
                pool.overflow(),
                f"{gap_s:.1f}s" if gap_s is not None else "n/a",
            )
        yield session
    _last_release_at = time.perf_counter()
