import uuid

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.logging_utils import log_execution
from app.database import async_session
from app.generation.models import ChapterTurn

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


@log_execution
async def embed_turn(turn_id: uuid.UUID) -> None:
    """Background job, same shape as generation/summarizer.py's triggers —
    re-fetches fresh since this runs after the request's own db session has
    closed. Best-effort: a failed embedding leaves the column NULL, which
    semantic_search.py simply excludes — a missing embedding degrades
    recall for that one paragraph, it doesn't break anything downstream."""
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with async_session() as db:
        turn = await db.get(ChapterTurn, turn_id)
        if turn is None:
            return  # discarded/deleted between scheduling and running — nothing to do

        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=turn.content)
        turn.embedding = response.data[0].embedding
        await db.commit()
