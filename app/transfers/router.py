import uuid
from typing import Literal

from fastapi import APIRouter, UploadFile
from fastapi.responses import Response

from app.core.access import get_owned_story
from app.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.transfers import service
from app.transfers.exporters import download_filename, export_manuscript
from app.transfers.schemas import ImportCommit, ImportResult, PreviewRead

router = APIRouter(prefix="/stories/{story_id}", tags=["transfers"])


@router.post("/imports/preview", response_model=PreviewRead, status_code=201)
async def preview(
    story_id: uuid.UUID, file: UploadFile, db: DbSession, user: CurrentUser
):
    await get_owned_story(db, story_id, user)
    try:
        data = await file.read(get_settings().import_max_bytes + 1)
        return await service.create_preview(
            db, story_id, user, file.filename or "", data
        )
    finally:
        await file.close()


@router.post("/imports/commit", response_model=ImportResult, status_code=201)
async def commit(
    story_id: uuid.UUID, body: ImportCommit, db: DbSession, user: CurrentUser
):
    return await service.commit_import(db, story_id, user, body)


@router.delete("/imports/preview/{token}", status_code=204)
async def cancel(
    story_id: uuid.UUID, token: uuid.UUID, db: DbSession, user: CurrentUser
):
    await get_owned_story(db, story_id, user)
    await service.cancel_preview(db, story_id, user, token)


@router.get("/export")
async def export(
    story_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    format: Literal["txt", "md"] = "txt",
    include_archived: bool = False,
):
    title, chapters = await service.read_export(db, story_id, user, include_archived)
    return Response(
        export_manuscript(title, chapters, format),
        media_type="text/markdown" if format == "md" else "text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename(title, format)}"',
            "Cache-Control": "no-store",
        },
    )
