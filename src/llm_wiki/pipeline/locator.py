from __future__ import annotations

from typing import Any


def heading_path_for_offset(text: str, offset: int) -> list[str]:
    path: list[str] = []
    for line in text.splitlines(keepends=True):
        line_len = len(line)
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if title:
                path = path[: max(level - 1, 0)]
                path.append(title)
        if offset < line_len:
            return path.copy()
        offset -= line_len
    return path.copy()


def build_locator(source_id: str, text: str, start_offset: int, end_offset: int) -> dict[str, Any]:
    chunk_text = text[start_offset:end_offset]
    return {
        "source_id": source_id,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "char_count": max(end_offset - start_offset, 0),
        "heading_path": heading_path_for_offset(text, start_offset),
        "quote_start": chunk_text[:120],
    }
