import uuid

from sqlalchemy import update

from app.core.llm_client import embed_text
from app.core.logging_utils import log_execution
from app.database import async_session
from app.generation.models import ChapterTurn

@log_execution
async def embed_turn(turn_id: uuid.UUID, expected_version: int | None = None) -> bool:
    """Persist a derived embedding only if its source paragraph is still current.

    Inference runs without a database connection. Missing embeddings degrade
    retrieval while durable jobs retain retry state.
    """
    async with async_session() as db:
        turn = await db.get(ChapterTurn, turn_id)
        if turn is None or (expected_version is not None and turn.version != expected_version):
            return False
        content, version = turn.content, turn.version
    embedding = await embed_text(content)
    async with async_session() as db:
        result = await db.execute(update(ChapterTurn).where(ChapterTurn.id == turn_id, ChapterTurn.version == version).values(embedding=embedding, embedding_version=version))
        await db.commit()
        return result.rowcount == 1
