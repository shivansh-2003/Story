"""Bound multipart uploads before parsing/spooling, including chunked requests."""

from fastapi import HTTPException
from starlette.responses import JSONResponse

from app.config import get_settings


class ImportUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not scope["path"].endswith("/imports/preview")
        ):
            return await self.app(scope, receive, send)
        limit = get_settings().import_max_bytes + 65536  # multipart headers/boundaries
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > limit:
            return await JSONResponse(
                {"detail": "Import upload exceeds the size limit."}, status_code=413
            )(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    raise HTTPException(413, "Import upload exceeds the size limit.")
            return message

        return await self.app(scope, bounded_receive, send)
