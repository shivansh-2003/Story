import uuid

from openai import AsyncOpenAI
from sqlalchemy import update

from app.config import get_settings
from app.core.logging_utils import log_execution
from app.database import async_session
from app.generation.models import ChapterTurn

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


@log_execution
async def embed_turn(turn_id: uuid.UUID, expected_version: int | None = None) -> bool:
    """Background job, same shape as generation/summarizer.py's triggers —
    re-fetches fresh since this runs after the request's own db session has
    closed. Best-effort: a failed embedding leaves the column NULL, which
    semantic_search.py simply excludes — a missing embedding degrades
    recall for that one paragraph, it doesn't break anything downstream."""
    settings = get_settings()
    async with async_session() as db:
        turn = await db.get(ChapterTurn, turn_id)
        if turn is None or (expected_version is not None and turn.version != expected_version):
            return False
        content, version = turn.content, turn.version
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=content)
    async with async_session() as db:
        result = await db.execute(update(ChapterTurn).where(ChapterTurn.id == turn_id, ChapterTurn.version == version).values(embedding=response.data[0].embedding, embedding_version=version))
        await db.commit()
        return result.rowcount == 1
