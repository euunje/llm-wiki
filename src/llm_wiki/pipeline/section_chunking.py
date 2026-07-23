from __future__ import annotations

from dataclasses import dataclass
import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^(```|~~~)")


@dataclass(frozen=True)
class SectionChunk:
    chunk_index: int
    heading_path: tuple[str, ...]
    text: str
    char_start: int
    char_end: int

    @property
    def title(self) -> str:
        return self.heading_path[-1] if self.heading_path else "Document"

    def locator(self, source_id: str) -> dict[str, object]:
        return {
            "source_id": source_id,
            "start_offset": self.char_start,
            "end_offset": self.char_end,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "char_count": self.char_end - self.char_start,
            "heading_path": list(self.heading_path),
        }


def _strip_numbering(value: str) -> str:
    cleaned = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", value).strip()
    return cleaned or value.strip()


def _iter_sections(text: str) -> list[tuple[tuple[str, ...], int, int, str]]:
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    sections: list[tuple[tuple[str, ...], int, int, str]] = []
    heading_stack: list[tuple[int, str]] = []
    section_start = 0
    current_heading_path: tuple[str, ...] = ()
    in_fence = False

    def flush(end_offset: int) -> None:
        nonlocal section_start, current_heading_path
        if end_offset <= section_start:
            return
        body = text[section_start:end_offset].strip()
        if not body:
            return
        sections.append((current_heading_path, section_start, end_offset, body))

    for index, line in enumerate(lines):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        heading_offset = offsets[index]
        flush(heading_offset)
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, _strip_numbering(heading_text)))
        current_heading_path = tuple(title for _, title in heading_stack)
        section_start = heading_offset

    flush(len(text))
    return sections


def _split_large_section(
    heading_path: tuple[str, ...],
    start: int,
    end: int,
    body: str,
    *,
    max_chars: int,
) -> list[SectionChunk]:
    if len(body) <= max_chars:
        return [SectionChunk(0, heading_path, body, start, end)]

    pieces: list[SectionChunk] = []
    paragraph_matches = list(re.finditer(r".*?(?:\n\n|\Z)", body, re.DOTALL))
    current_start = 0
    current_text = ""
    current_piece_start = start
    for match in paragraph_matches:
        paragraph = match.group(0)
        if not paragraph.strip():
            continue
        candidate = f"{current_text}{paragraph}"
        if current_text and len(candidate) > max_chars:
            piece_end = start + current_start + len(current_text)
            pieces.append(
                SectionChunk(len(pieces), heading_path, current_text.strip(), current_piece_start, piece_end)
            )
            current_piece_start = start + match.start()
            current_text = paragraph
            current_start = match.start()
        else:
            if not current_text:
                current_piece_start = start + match.start()
                current_start = match.start()
            current_text = candidate
    if current_text.strip():
        pieces.append(SectionChunk(len(pieces), heading_path, current_text.strip(), current_piece_start, start + len(body)))
    return pieces or [SectionChunk(0, heading_path, body, start, end)]


def chunk_markdown_by_section(text: str, *, max_chars: int = 1600) -> list[SectionChunk]:
    chunks: list[SectionChunk] = []
    for heading_path, start, end, body in _iter_sections(text):
        for piece in _split_large_section(heading_path, start, end, body, max_chars=max_chars):
            chunks.append(
                SectionChunk(
                    chunk_index=len(chunks),
                    heading_path=piece.heading_path,
                    text=piece.text,
                    char_start=piece.char_start,
                    char_end=piece.char_end,
                )
            )
    return chunks
