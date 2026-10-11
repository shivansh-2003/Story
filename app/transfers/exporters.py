import re


def export_manuscript(title: str, chapters: list[dict], format: str) -> str:
    title = " ".join(title.splitlines())
    sections = [f"# {title}" if format == "md" else f"Title: {title}"]
    for number, chapter in enumerate(chapters, 1):
        chapter_title = " ".join((chapter["title"] or f"Chapter {number}").splitlines())
        if format == "md":
            heading = f"## {chapter_title}"
        else:
            # A deterministic heading that the text importer recognizes.
            heading = f"Chapter {number}: {chapter_title}"
        sections.append(heading)
        sections.extend(chapter["paragraphs"])
    return "\n\n".join(sections) + "\n"


def download_filename(title: str, format: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-")[:80] or "manuscript"
    return f"{stem}.{format}"
