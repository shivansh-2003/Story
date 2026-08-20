import uuid

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter
from app.config import get_settings
from app.core.logging_utils import log_execution
from app.generation.embedder import EMBEDDING_MODEL
from app.generation.models import ChapterTurn

TOP_K = 3
# cosine distance, 0 = identical, 2 = opposite. Starting point for
# text-embedding-3-small — see README for how to calibrate against real data.
MAX_DISTANCE = 0.35


@log_execution
async def embed_query(text: str) -> list[float]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


@log_execution
async def search_relevant_turns(
    db: AsyncSession, story_id: uuid.UUID, current_chapter_id: uuid.UUID, query_vector: list[float]
) -> list[ChapterTurn]:
    """Cosine-distance search scoped to the current story, excluding the
    chapter currently being written (its own raw_tail already covers recent
    local context — this is specifically for *other* chapters). pgvector's
    <=> operator is cosine distance; ascending order is closest-first."""
    distance = ChapterTurn.embedding.cosine_distance(query_vector)
    result = await db.execute(
        select(ChapterTurn, distance.label("distance"))
        .join(Chapter, Chapter.id == ChapterTurn.chapter_id)
        .where(
            Chapter.story_id == story_id,
            ChapterTurn.chapter_id != current_chapter_id,
            ChapterTurn.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(TOP_K)
    )
    # relevance (not just "closest of what exists") matters: a story with no
    # genuinely related paragraph should return nothing, not its 3
    # least-unrelated ones.
    return [turn for turn, dist in result.all() if dist <= MAX_DISTANCE]
