from __future__ import annotations

import re

from llm_wiki.common import new_id
from llm_wiki.pipeline.section_chunking import SectionChunk
from llm_wiki.schema.wiki_page_candidate import EvidenceClaim, SourceSectionRef, WikiPageCandidate


STOPWORDS = {"the", "and", "for", "with", "from", "into", "that", "this", "section"}

# Section chunks are reading units, not page units.  Keep only reusable
# knowledge-node titles as standalone pages; fold procedural/example/tiny
# subsections into their nearest durable concept page.
KEY_STANDALONE_TITLES = {
    "frontmatter",
    "bundle structure",
    "concept documents",
    "cross-linking",
    "citations",
    "conformance",
    "versioning",
    "terminology",
    "index files",
    "log files",
}
DEMOTE_PREFIXES = (
    "example",
    "appendix",
    "optional",
    "before ",
    "step ",
    "part ",
    "multiplier ",
)
DEMOTE_TITLES = {
    "source metadata",
    "metadata",
    "topics",
    "readme / content",
    "readme content",
    "windows",
    "macos / linux",
    "macos linux",
    "homebrew",
    "macports",
    "quick install",
    "documentation",
    "results",
    "method",
}


def build_chunk_prompt_text(chunks: list[dict[str, object]], *, max_chars: int = 2500) -> str:
    parts: list[str] = []
    size = 0
    for chunk in chunks:
        locator = chunk.get("locator") or {}
        heading_path = locator.get("heading_path") or []
        heading = " > ".join(str(item) for item in heading_path) or "Document"
        block = f"## {heading}\n{str(chunk.get('text') or '').strip()}\n"
        if parts and size + len(block) > max_chars:
            break
        parts.append(block)
        size += len(block)
    return "\n".join(parts)


def extract_wiki_page_candidates(
    source_id: str,
    source_title: str,
    chunks: list[SectionChunk],
) -> tuple[list[WikiPageCandidate], list[dict[str, object]]]:
    candidates: list[WikiPageCandidate] = []
    claims_log: list[dict[str, object]] = []
    for chunk in chunks:
        title = _candidate_title(chunk, source_title)
        if not title:
            continue
        summary = _summary_from_chunk(chunk.text, title)
        keywords = _keywords_from_chunk(chunk.heading_path, chunk.text)
        chunk_id = f"chunk_{source_id}_{chunk.chunk_index:03d}"
        section_ref = SourceSectionRef(
            chunk_id=chunk_id,
            heading_path=chunk.heading_path,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        claim = EvidenceClaim(
            claim_id=new_id("claim"),
            statement=summary,
            source_id=source_id,
            chunk_id=chunk_id,
            quote=_quote_from_chunk(chunk.text),
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        claims_log.append(
            {
                "claim_id": claim.claim_id,
                "source_id": source_id,
                "chunk_id": chunk_id,
                "heading_path": list(chunk.heading_path),
                "statement": claim.statement,
                "quote": claim.quote,
                "char_start": claim.char_start,
                "char_end": claim.char_end,
            }
        )
        body = _build_body(title, summary, chunk.text, source_id, chunk.heading_path)
        candidates.append(
            WikiPageCandidate(
                candidate_key=new_id("page"),
                node_type="concept",
                title=title,
                summary=summary,
                source_id=source_id,
                aliases=[],
                keywords=keywords,
                tags=keywords[:5],
                proposed_frontmatter={},
                body_outline=["Definition", "Source evidence"],
                draft_body=body,
                evidence_claims=[claim],
                source_section_refs=[section_ref],
            )
        )
    if not candidates and chunks:
        chunk = chunks[0]
        title = source_title.strip() or "Source Notes"
        summary = _summary_from_chunk(chunk.text, title)
        keywords = _keywords_from_chunk((title,), chunk.text) or ["source", "notes"]
        chunk_id = f"chunk_{source_id}_{chunk.chunk_index:03d}"
        section_ref = SourceSectionRef(
            chunk_id=chunk_id,
            heading_path=chunk.heading_path or (title,),
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        claim = EvidenceClaim(
            claim_id=new_id("claim"),
            statement=summary,
            source_id=source_id,
            chunk_id=chunk_id,
            quote=_quote_from_chunk(chunk.text),
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        claims_log.append(
            {
                "claim_id": claim.claim_id,
                "source_id": source_id,
                "chunk_id": chunk_id,
                "heading_path": list(section_ref.heading_path),
                "statement": claim.statement,
                "quote": claim.quote,
                "char_start": claim.char_start,
                "char_end": claim.char_end,
                "fallback": "source_title_page",
            }
        )
        candidates.append(
            WikiPageCandidate(
                candidate_key=new_id("page"),
                node_type="concept",
                title=title,
                summary=summary,
                source_id=source_id,
                keywords=keywords,
                tags=keywords[:5],
                body_outline=["Definition", "Source evidence"],
                draft_body=_build_body(title, summary, chunk.text, source_id, section_ref.heading_path),
                evidence_claims=[claim],
                source_section_refs=[section_ref],
            )
        )
    return candidates, claims_log


def _candidate_title(chunk: SectionChunk, source_title: str) -> str:
    path = tuple(item.strip() for item in chunk.heading_path if item and item.strip())
    if not path:
        return ""

    # The document title and source-metadata headings are source metadata unless
    # they are the only useful heading. Source/article-title pages cause poor
    # reusable wiki nodes.
    if len(path) == 1:
        title = path[0]
        if _should_demote_title(title):
            return ""
        return "" if _looks_like_source_title(title, source_title) else title

    # Use the actual markdown heading level from the chunk text.  Some dataset
    # files start at H2 without an H1, so path indexes alone cannot identify
    # the durable parent concept.
    leaf_title = path[-1]
    leaf_level = _leaf_heading_level(chunk.text)
    leaf_key = _title_key(leaf_title)

    if leaf_key in KEY_STANDALONE_TITLES:
        return leaf_title

    if leaf_level <= 2:
        if _should_demote_title(leaf_title) or _looks_like_source_title(leaf_title, source_title):
            return ""
        return leaf_title

    parent_title = _nearest_durable_parent(path[:-1], source_title)
    if _should_demote_title(leaf_title) or len(path) > 1:
        return parent_title
    return "" if _looks_like_source_title(leaf_title, source_title) else leaf_title


def _leaf_heading_level(text: str) -> int:
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+", line.strip())
        if match:
            return len(match.group(1))
    return 1


def _nearest_durable_parent(path: tuple[str, ...], source_title: str) -> str:
    for title in reversed(path):
        if _should_demote_title(title) or _looks_like_source_title(title, source_title):
            continue
        return title
    return ""


def _title_key(title: str) -> str:
    return re.sub(r"\s+", " ", title.replace("—", "-").strip().casefold())


def _should_demote_title(title: str) -> bool:
    key = _title_key(title)
    return key in DEMOTE_TITLES or any(key.startswith(prefix) for prefix in DEMOTE_PREFIXES)


def _looks_like_source_title(title: str, source_title: str) -> bool:
    key = _title_key(title)
    source_key = _title_key(source_title)
    if not key:
        return True
    if key == source_key:
        return True
    # Article headlines and filename-like headings make poor reusable nodes.
    if len(title) > 72:
        return True
    if " vs " in key or " versus " in key:
        return True
    filenameish = source_key.replace("-", " ")
    return bool(filenameish and filenameish in key)


def _summary_from_chunk(text: str, title: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return f"Source-backed notes for {title}."
    first = re.split(r"(?<=[.!?])\s+|\n", clean, maxsplit=1)[0].strip()
    return first[:280] if first else f"Source-backed notes for {title}."


def _quote_from_chunk(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:240]


def _keywords_from_chunk(heading_path: tuple[str, ...], text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", " ".join(heading_path) + " " + text)
    seen: list[str] = []
    for token in tokens:
        normalized = token.lower()
        if normalized in STOPWORDS or normalized in seen:
            continue
        seen.append(normalized)
        if len(seen) >= 8:
            break
    return seen


def _build_body(title: str, summary: str, text: str, source_id: str, heading_path: tuple[str, ...]) -> str:
    heading_label = " > ".join(heading_path) if heading_path else title
    source_excerpt = text.strip()
    return (
        f"# {title}\n\n"
        f"## Definition\n\n{summary}\n\n"
        f"## Source evidence\n\n"
        f"Derived from `{source_id}` section `{heading_label}`.\n\n"
        f"{source_excerpt}\n"
    )
