"""Deterministic UTF-8 text/Markdown parsing; no model calls or writes."""

import re
from pathlib import Path


from app.core.errors import DomainError
from app.config import get_settings
from app.transfers.schemas import PreviewChapter

TEXT_HEADING = re.compile(r"^Chapter\s+\d+(?:\s*[:.\-—]\s*(.*))?$", re.IGNORECASE)
MARKDOWN_HEADING = re.compile(r"^##\s+(.+?)\s*#*\s*$")


def parse_manuscript(filename: str, data: bytes) -> list[PreviewChapter]:
    settings = get_settings()
    extension = Path(filename).suffix.lower()
    if extension not in {".txt", ".md"}:
        raise DomainError(
            415, "Choose a UTF-8 .txt or .md file. DOCX is not supported yet."
        )
    if len(data) > settings.import_max_bytes:
        raise DomainError(
            413, f"File exceeds the {settings.import_max_bytes:,}-byte import limit."
        )
    try:
        content = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as error:
        raise DomainError(422, "File must be UTF-8 encoded.") from error
    if any(ord(c) < 32 and c not in "\n\t" for c in content):
        raise DomainError(422, "File contains unsupported control characters.")

    chapters: list[PreviewChapter] = []
    title = "Imported chapter"
    lines: list[str] = []
    heading_seen = False
    fence: str | None = None

    def finish() -> None:
        # Blank lines separate paragraphs; line breaks inside a paragraph remain.
        paragraphs = [
            p.strip() for p in re.split(r"\n[ \t]*\n", "\n".join(lines)) if p.strip()
        ]
        if paragraphs or heading_seen:
            chapters.append(
                PreviewChapter(
                    index=len(chapters), title=title[:200], paragraphs=paragraphs
                )
            )

    for line in content.split("\n"):
        stripped = line.strip()
        if extension == ".md" and stripped.startswith(("```", "~~~")):
            marker = stripped[0]
            fence = None if fence == marker else marker if fence is None else fence
        md_heading = (
            MARKDOWN_HEADING.fullmatch(line)
            if extension == ".md" and fence is None
            else None
        )
        txt_heading = TEXT_HEADING.fullmatch(line) if extension == ".txt" else None
        if md_heading or txt_heading:
            finish()
            title = (
                md_heading.group(1)
                if md_heading
                else txt_heading.group(1) or line.strip()
            )
            lines = []
            heading_seen = True
        elif (
            not chapters
            and not heading_seen
            and not any(s.strip() for s in lines)
            and (
                (extension == ".md" and line.startswith("# "))
                or (extension == ".txt" and line.startswith("Title: "))
            )
        ):
            # Optional manuscript title; story metadata is never overwritten.
            continue
        else:
            lines.append(line)
    finish()
    if not chapters or not any(c.paragraphs for c in chapters):
        raise DomainError(422, "The file has no manuscript paragraphs.")
    if len(chapters) > settings.import_max_chapters:
        raise DomainError(
            422, f"Import at most {settings.import_max_chapters} chapters at a time."
        )
    if sum(len(c.paragraphs) for c in chapters) > settings.import_max_paragraphs:
        raise DomainError(
            422,
            f"Import at most {settings.import_max_paragraphs} paragraphs at a time.",
        )
    if any(len(p) > 50000 for c in chapters for p in c.paragraphs):
        raise DomainError(
            422, "A paragraph exceeds 50,000 characters. Split it with a blank line."
        )
    return chapters
