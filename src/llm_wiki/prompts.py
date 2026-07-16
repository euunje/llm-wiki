"""Prompt templates for the LLM ingest pipeline.

Three passes:
    1. extract — read source, return structured JSON with candidates
    2. draft_page — generate a single entity/concept/source page
    3. merge_page — update an existing page with new information

Each template returns a list of ChatMessage ready for the Ollama client.
"""

from __future__ import annotations

from .llm import ChatMessage


# ---------------------------------------------------------------------------
# System prompt — shared across all passes
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the LLM agent that maintains an LLM-Wiki knowledge base.

You follow these conventions strictly:

1. Wiki pages use YAML frontmatter with these fields:
   - title: "Page Title"
   - type: source | entity | concept | synthesis
   - pageKind: source | entity | concept | synthesis | review  (pageKind is optional; type is the primary classifier)
   - tags: [tag1, tag2]
   - created: YYYY-MM-DD
   - updated: YYYY-MM-DD
   - sources: ["sources/source-slug.md"]
   - confidence: high | medium | low

2. Write generated summaries, wiki page bodies, review explanations, query/synthesis answers,
   and learning artifacts in Korean by default. Keep proper nouns, technical terms,
   commands, file paths, APIs, model names, and code identifiers in English.

3. Always use [[wikilinks]] for cross-references between wiki pages.
   Never use plain markdown links for internal pages.

4. Slugs are kebab-case lowercase ASCII (e.g. andrej-karpathy, not Karpathy.md).
   Use the canonical name. Acronyms stay together (rag, llm, not r-a-g).

5. Be factual. Never invent citations or claims not in the source.
   If unsure, mark confidence as 'medium' or 'low'.

6. Page bodies should be concise but substantive: 150-400 words is typical
   for entity pages, 200-500 words for concept pages.

7. Preserve existing content when updating a page. Add new info in new
   sections or under an '## Updates' heading. Never silently overwrite.

8. Routing rules — NEVER create normal wiki pages for operational or
   navigational content:
   - Guide-like content (runbooks, tutorials, how-tos, cheatsheets, configs)
     -> emit as candidates with pageKind: review, suggestedExternalOwner: 8000-web-config
   - Map/MOC content (graph navigation, hub pages, index pages, relationship docs)
     -> emit as candidates with pageKind: review, suggestedExternalOwner: mcp-map
   - Low-confidence items or items whose category is unclear
     -> emit as candidates with pageKind: review, suggestedExternalOwner: (leave blank)
   - Normal entities and concepts -> use pageKind: entity or concept
"""


# ---------------------------------------------------------------------------
# Pass 1 — Extraction
# ---------------------------------------------------------------------------

EXTRACTION_INSTRUCTIONS = """Read the source document below and extract a structured summary.

Return ONLY a valid JSON object matching this exact schema:

{
  "title": "A clear, specific title for this source (max 80 chars)",
  "source_slug": "kebab-case-slug-for-this-source",
  "summary": "A 2-3 sentence paragraph summarizing the source",
  "key_takeaways": [
    "Bullet 1 — a substantive takeaway (1-2 sentences)",
    "Bullet 2",
    "Bullet 3"
  ],
  "candidates": [
    {
      "name": "Canonical name as it would appear in a wiki",
      "slug": "kebab-case-slug",
      "pageKind": "entity | concept | review",
      "description": "1-2 sentences describing this item based on the source",
      "confidence": "high | medium | low",
      "suggestedExternalOwner": "8000-web-config | mcp-map | (optional, used for review items only)",
      "reason": "Why this was routed to this pageKind (optional, helpful for review items)"
    }
  ],
  "entities": [
    {
      "name": "Canonical name as it would appear in a wiki",
      "slug": "kebab-case-slug",
      "type": "person | organization | model | product | place",
      "description": "1-2 sentences describing this entity based on the source"
    }
  ],
  "concepts": [
    {
      "name": "Canonical name",
      "slug": "kebab-case-slug",
      "type": "concept",
      "description": "1-2 sentences describing this concept based on the source"
    }
  ],
  "tags": ["tag1", "tag2", "tag3"]
}

Rules:
- Extract 3-8 key takeaways, each substantive.
- Write source summary, key_takeaways, candidate descriptions, entity descriptions,
  and concept descriptions in Korean by default. Keep proper nouns, technical terms,
  commands, file paths, APIs, model names, and code identifiers in English.
- Extract 2-10 candidates total (entities + concepts + any review items).
- Slugs must be kebab-case ASCII. For people use last name if unambiguous
  (karpathy, not andrej-karpathy). For concepts use the shortest canonical
  form (rag, not retrieval-augmented-generation — but use the full form in 'name').
- Tags should be 3-5 broad topic labels for the whole source.
- Do NOT extract trivial mentions — only things substantive enough to deserve
  their own wiki page.
- Routing: use pageKind=entity for people/orgs/models/products/places,
  pageKind=concept for techniques/ideas/topics,
  pageKind=review for operational guides, maps/MOCs, low-confidence items,
  or items that should not become normal wiki pages.
- For review items, set suggestedExternalOwner=8000-web-config (guide-like)
  or mcp-map (map/MOC-like) or leave blank.
- The legacy "entities" and "concepts" arrays are still accepted; prefer
  populating "candidates" instead when possible.
- Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
"""


CHUNK_EXTRACTION_INSTRUCTIONS = """Read ONE chunk from a larger source document and extract structured findings for that chunk only.

Return ONLY a valid JSON object matching this exact schema:

{
  "chunk_index": 0,
  "chunk_summary": "A 1-2 sentence summary of this chunk",
  "key_takeaways": [
    "Substantive takeaway 1",
    "Substantive takeaway 2"
  ],
  "candidates": [
    {
      "name": "Canonical name as it would appear in a wiki",
      "slug": "kebab-case-slug",
      "pageKind": "entity | concept | review",
      "description": "1-2 sentences describing this item based on this chunk",
      "confidence": "high | medium | low",
      "suggestedExternalOwner": "8000-web-config | mcp-map | (optional, used for review items only)",
      "reason": "Why this was routed to this pageKind (optional, helpful for review items)"
    }
  ],
  "entities": [],
  "concepts": [],
  "tags": ["tag1", "tag2"],
  "confidence": "high | medium | low"
}

Rules:
- Focus only on information present in this chunk. Do not assume missing context.
- Prefer extracting chunk-specific candidates that are substantive enough for a wiki page.
- Keep chunk_summary, key_takeaways, and candidate descriptions in Korean by default. Keep proper nouns, technical terms,
  commands, file paths, APIs, model names, and code identifiers in English.
- Slugs must be kebab-case ASCII.
- Use pageKind=entity for people/orgs/models/products/places, pageKind=concept for techniques/ideas/topics,
  pageKind=review for operational guides, maps/MOCs, low-confidence items, or unclear routing.
- For review items, set suggestedExternalOwner=8000-web-config (guide-like) or mcp-map (map/MOC-like) or leave blank.
- entities/concepts arrays are optional legacy compatibility fields; prefer populating candidates.
- Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
"""


def build_extraction_messages(source_title: str, source_text: str, db_path: Path | None = None, use_draft: bool = False) -> list[ChatMessage]:
    """Pass 1 — extract structured information from a source document."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    extract_instr = get_prompt("extract", db_path, use_draft)
    user_content = (
        f"{extract_instr}\n\n"
        f"---SOURCE TITLE---\n{source_title}\n\n"
        f"---SOURCE TEXT---\n{source_text}\n"
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


def build_extraction_retry_messages(
    source_title: str, source_text: str, bad_response: str, db_path: Path | None = None, use_draft: bool = False
) -> list[ChatMessage]:
    """Retry prompt after a JSON parse failure."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    extract_instr = get_prompt("extract", db_path, use_draft)
    user_content = (
        f"Your previous response was not valid JSON. Return ONLY a valid JSON "
        f"object matching the schema — no markdown fences, no preamble.\n\n"
        f"{extract_instr}\n\n"
        f"---SOURCE TITLE---\n{source_title}\n\n"
        f"---SOURCE TEXT---\n{source_text}\n"
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
        ChatMessage(role="assistant", content=bad_response[:2000]),
        ChatMessage(
            role="user",
            content="That was not valid JSON. Try again. Return ONLY the JSON object.",
        ),
    ]


def build_chunk_extraction_messages(
    source_title: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Pass 1b — extract structured information from a single source chunk."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    extract_instr = get_prompt("chunk_extract", db_path, use_draft)
    user_content = (
        f"{extract_instr}\n\n"
        f"---SOURCE TITLE---\n{source_title}\n\n"
        f"---CHUNK INDEX---\n{chunk_index}\n\n"
        f"---TOTAL CHUNKS---\n{total_chunks}\n\n"
        f"---CHUNK TEXT---\n{chunk_text}\n"
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


def build_chunk_extraction_retry_messages(
    source_title: str,
    chunk_text: str,
    chunk_index: int,
    total_chunks: int,
    bad_response: str,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Retry prompt after a chunk JSON parse failure."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    extract_instr = get_prompt("chunk_extract", db_path, use_draft)
    user_content = (
        "Your previous response was not valid JSON. Return ONLY a valid JSON object matching the chunk schema — no markdown fences, no preamble.\n\n"
        f"{extract_instr}\n\n"
        f"---SOURCE TITLE---\n{source_title}\n\n"
        f"---CHUNK INDEX---\n{chunk_index}\n\n"
        f"---TOTAL CHUNKS---\n{total_chunks}\n\n"
        f"---CHUNK TEXT---\n{chunk_text}\n"
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
        ChatMessage(role="assistant", content=bad_response[:2000]),
        ChatMessage(
            role="user",
            content="That was not valid JSON. Try again. Return ONLY the JSON object.",
        ),
    ]


# ---------------------------------------------------------------------------
# Pass 2 — Draft a new entity or concept page
# ---------------------------------------------------------------------------

NEW_ENTITY_PAGE_TEMPLATE = """Draft a wiki entity page for '{name}'.

This entity was extracted from the source: '{source_title}' (sources/{source_slug}.md)

The source describes it as:
{description}

Here are some relevant excerpts from the source:
{excerpts}

Related entities and concepts also mentioned in this source (use [[wikilinks]] to connect to them):
{related}

Write a complete markdown page with:
1. YAML frontmatter (title, type: entity, tags, created: {today}, updated: {today}, sources: ["sources/{source_slug}.md"], confidence)
2. An H1 heading matching the title
3. Korean section/body text; keep proper nouns, technical terms, commands, file paths, APIs, model names, and code identifiers in English
4. A 2-3 paragraph body (150-300 words) describing this entity
5. Use [[wikilinks]] when referencing other entities or concepts from the related list above
6. End with a Korean sources section heading such as '## 출처' listing [[sources/{source_slug}]]

Do not invent facts. Only use information from the excerpts. Return ONLY the markdown content — no preamble, no code fences.
"""


NEW_CONCEPT_PAGE_TEMPLATE = """Draft a wiki concept page for '{name}'.

This concept was extracted from the source: '{source_title}' (sources/{source_slug}.md)

The source describes it as:
{description}

Here are some relevant excerpts from the source:
{excerpts}

Related entities and concepts also mentioned in this source (use [[wikilinks]] to connect to them):
{related}

Write a complete markdown page with:
1. YAML frontmatter (title, type: concept, tags, created: {today}, updated: {today}, sources: ["sources/{source_slug}.md"], confidence)
2. An H1 heading matching the title
3. Korean section/body text; keep proper nouns, technical terms, commands, file paths, APIs, model names, and code identifiers in English
4. A 2-4 paragraph body (200-400 words) explaining this concept:
   - What it is
   - Why it matters
   - How it relates to other concepts/entities (use [[wikilinks]])
5. End with a Korean sources section heading such as '## 출처' listing [[sources/{source_slug}]]

Do not invent facts. Only use information from the excerpts. Return ONLY the markdown content — no preamble, no code fences.
"""


NEW_ENTITY_PAGE_JSON_TEMPLATE = """다음 정보를 바탕으로 새 entity 위키 페이지의 본문을 JSON으로 작성하세요.

대상 페이지:
- title: {name}
- slug: {slug}
- type: entity
- source: sources/{source_slug}.md

소스 제목: {source_title}

설명:
{description}

관련 발췌:
{excerpts}

허용된 내부 링크(정확히 이 값만 사용 가능):
{allowed_links}

반드시 아래 JSON 객체만 반환하세요:
{{
  "slug": "{slug}",
  "type": "entity",
  "body_markdown": "# {name}\n\n...",
  "links_used": ["entities/foo", "concepts/bar", "sources/{source_slug}"],
  "sources": ["sources/{source_slug}.md"]
}}

규칙:
- body_markdown 안의 본문과 섹션 설명은 기본적으로 한국어로 작성하세요. 고유명사, technical terms, commands, file paths, APIs, model names, code identifiers는 English 유지.
- body_markdown은 완성된 markdown 본문이어야 하며 YAML frontmatter는 포함하지 마세요.
- 첫 줄은 반드시 `# {name}` 이어야 합니다.
- 내부 참조는 반드시 [[wikilinks]] 만 사용하세요.
- body_markdown 안에 실제로 등장한 모든 wikilink target을 links_used에 정확히 한 번씩 나열하세요.
- links_used에는 위 허용 목록에 있는 링크만 포함하세요.
- sources에는 반드시 "sources/{source_slug}.md" 를 포함하세요.
- 마지막에는 한국어 출처 섹션(예: `## 출처`)을 두고 [[sources/{source_slug}]] 를 포함하세요.
- 사실을 꾸며내지 말고 발췌 내용만 사용하세요.
- 설명, 서론, 코드펜스 없이 JSON 객체만 반환하세요.
"""


NEW_CONCEPT_PAGE_JSON_TEMPLATE = """다음 정보를 바탕으로 새 concept 위키 페이지의 본문을 JSON으로 작성하세요.

대상 페이지:
- title: {name}
- slug: {slug}
- type: concept
- source: sources/{source_slug}.md

소스 제목: {source_title}

설명:
{description}

관련 발췌:
{excerpts}

허용된 내부 링크(정확히 이 값만 사용 가능):
{allowed_links}

반드시 아래 JSON 객체만 반환하세요:
{{
  "slug": "{slug}",
  "type": "concept",
  "body_markdown": "# {name}\n\n...",
  "links_used": ["entities/foo", "concepts/bar", "sources/{source_slug}"],
  "sources": ["sources/{source_slug}.md"]
}}

규칙:
- body_markdown 안의 본문과 섹션 설명은 기본적으로 한국어로 작성하세요. 고유명사, technical terms, commands, file paths, APIs, model names, code identifiers는 English 유지.
- body_markdown은 완성된 markdown 본문이어야 하며 YAML frontmatter는 포함하지 마세요.
- 첫 줄은 반드시 `# {name}` 이어야 합니다.
- 내부 참조는 반드시 [[wikilinks]] 만 사용하세요.
- body_markdown 안에 실제로 등장한 모든 wikilink target을 links_used에 정확히 한 번씩 나열하세요.
- links_used에는 위 허용 목록에 있는 링크만 포함하세요.
- sources에는 반드시 "sources/{source_slug}.md" 를 포함하세요.
- 마지막에는 한국어 출처 섹션(예: `## 출처`)을 두고 [[sources/{source_slug}]] 를 포함하세요.
- 본문은 개념의 의미, 중요성, 관련 entity/concept와의 연결을 한국어로 설명하세요.
- 사실을 꾸며내지 말고 발췌 내용만 사용하세요.
- 설명, 코드펜스 없이 JSON 객체만 반환하세요.
"""


MERGE_PAGE_JSON_TEMPLATE = """기존 위키 페이지를 새로운 source 정보로 보강하세요. 반드시 JSON 객체만 반환하세요.

대상 페이지:
- title: {name}
- slug: {slug}
- type: {kind}
- source: sources/{source_slug}.md

기존 페이지 전체 markdown:
---EXISTING PAGE---
{existing_content}
---END EXISTING PAGE---

새 source 제목: {source_title}

새 설명:
{description}

관련 발췌:
{excerpts}

허용된 내부 링크(정확히 이 값만 사용 가능):
{allowed_links}

반드시 아래 JSON 객체만 반환하세요:
{{
  "slug": "{slug}",
  "type": "{kind}",
  "body_markdown": "# {name}\n\n...",
  "links_used": ["entities/foo", "concepts/bar", "sources/{source_slug}"],
  "sources": ["sources/old-source.md", "sources/{source_slug}.md"]
}}

규칙:
- 기존 페이지의 사실과 구조를 보존하고, 새 정보만 자연스럽게 추가하세요.
- body_markdown에는 YAML frontmatter를 넣지 마세요.
- body_markdown은 최종 전체 본문이어야 합니다.
- 첫 줄은 반드시 `# {name}` 이어야 합니다.
- 본문과 섹션 설명은 기본적으로 한국어로 작성하세요. 고유명사, technical terms, commands, file paths, APIs, model names, code identifiers는 English 유지.
- 내부 참조는 반드시 [[wikilinks]] 만 사용하세요.
- body_markdown 안에 실제로 등장한 모든 wikilink target을 links_used에 정확히 한 번씩 나열하세요.
- links_used에는 허용된 링크만 포함하세요.
- sources에는 기존 source들을 유지하고 반드시 "sources/{source_slug}.md" 를 포함하세요.
- 마지막에는 한국어 출처 섹션을 두고 [[sources/{source_slug}]] 를 포함하세요.
- 사실을 꾸며내지 말고 제공된 정보만 사용하세요.
- 설명, 코드펜스 없이 JSON 객체만 반환하세요.
"""


PAGE_JSON_RETRY_TEMPLATE = """이전 응답은 페이지 JSON 계약을 만족하지 못했습니다.

반드시 JSON 객체만 다시 반환하세요. markdown code fence, 설명, 서문은 금지입니다.

필수 조건:
- slug 는 정확히 `{slug}`
- type 는 정확히 `{kind}`
- body_markdown 안의 모든 [[wikilinks]] 대상과 links_used가 정확히 일치
- links_used의 모든 값은 허용 목록 안에 있어야 함
- sources에는 반드시 `sources/{source_slug}.md` 포함

허용 링크:
{allowed_links}

검증 오류:
{validation_errors}
"""


def build_draft_page_messages(
    kind: str,
    name: str,
    source_title: str,
    source_slug: str,
    description: str,
    excerpts: str,
    related: list[str],
    today: str,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Pass 2 — draft a single new entity or concept page."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    template_key = "new_entity" if kind == "entity" else "new_concept"
    template = get_prompt(template_key, db_path, use_draft)
    related_str = "\n".join(f"  - [[{r}]]" for r in related) if related else "  (none)"
    user_content = template.format(
        name=name,
        source_title=source_title,
        source_slug=source_slug,
        description=description,
        excerpts=excerpts,
        related=related_str,
        today=today,
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


def build_structured_page_messages(
    *,
    kind: str,
    name: str,
    slug: str,
    source_title: str,
    source_slug: str,
    description: str,
    excerpts: str,
    allowed_links: list[str],
    existing_content: str | None = None,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Pass 2 — draft/merge an entity or concept page as validated JSON."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    allowed_links_str = "\n".join(f"- {link}" for link in allowed_links) if allowed_links else "- sources/{source_slug}"
    if existing_content is None:
        template_key = "new_entity_json" if kind == "entity" else "new_concept_json"
        template = get_prompt(template_key, db_path, use_draft)
        user_content = template.format(
            kind=kind,
            name=name,
            slug=slug,
            source_title=source_title,
            source_slug=source_slug,
            description=description,
            excerpts=excerpts,
            allowed_links=allowed_links_str,
        )
    else:
        template = get_prompt("merge_page_json", db_path, use_draft)
        user_content = template.format(
            kind=kind,
            name=name,
            slug=slug,
            existing_content=existing_content,
            source_title=source_title,
            source_slug=source_slug,
            description=description,
            excerpts=excerpts,
            allowed_links=allowed_links_str,
        )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


def build_structured_page_retry_messages(
    *,
    kind: str,
    slug: str,
    source_slug: str,
    allowed_links: list[str],
    bad_response: str,
    validation_errors: list[str],
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Retry prompt for structured page JSON validation failures."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    template = get_prompt("page_json_retry", db_path, use_draft)
    allowed_links_str = "\n".join(f"- {link}" for link in allowed_links) if allowed_links else f"- sources/{source_slug}"
    user_content = template.format(
        kind=kind,
        slug=slug,
        source_slug=source_slug,
        allowed_links=allowed_links_str,
        validation_errors="\n".join(f"- {err}" for err in validation_errors),
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="assistant", content=bad_response[:4000]),
        ChatMessage(role="user", content=user_content),
    ]


# ---------------------------------------------------------------------------
# Pass 2b — Merge new info into an existing page
# ---------------------------------------------------------------------------

MERGE_PAGE_TEMPLATE = """Update the following existing wiki page with new information from a new source.

---EXISTING PAGE---
{existing_content}
---END EXISTING PAGE---

---NEW SOURCE---
Title: {source_title}
Source slug: {source_slug}

The source describes '{name}' as:
{description}

Relevant excerpts from the new source:
{excerpts}
---END NEW SOURCE---

Update the page by:
1. Preserving ALL existing content — do not delete or rewrite existing paragraphs.
2. Adding new information in Korean as either:
   - A new paragraph in the appropriate section, OR
   - A new section if the information is substantively new, OR
   - An '## 업데이트' section if the new info contradicts something in the existing page.
3. Keeping proper nouns, technical terms, commands, file paths, APIs, model names, and code identifiers in English.
4. Updating the 'updated:' date in frontmatter to {today}.
5. Adding "sources/{source_slug}.md" to the 'sources:' list in frontmatter (keep existing entries).
6. Adding [[sources/{source_slug}]] to the sources section at the bottom.
7. Keeping any existing [[wikilinks]] intact.

Return ONLY the complete updated markdown page — no preamble, no code fences.
"""


def build_merge_page_messages(
    name: str,
    existing_content: str,
    source_title: str,
    source_slug: str,
    description: str,
    excerpts: str,
    today: str,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Pass 2b — merge new information into an existing page."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    template = get_prompt("merge_page", db_path, use_draft)
    user_content = template.format(
        name=name,
        existing_content=existing_content,
        source_title=source_title,
        source_slug=source_slug,
        description=description,
        excerpts=excerpts,
        today=today,
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


# ---------------------------------------------------------------------------
# Pass 3 — Source summary page
# ---------------------------------------------------------------------------

SOURCE_PAGE_TEMPLATE = """Draft a source summary page for the ingested document.

Source details:
- Title: {source_title}
- Slug: {source_slug}
- File path: {file_path}
- File type: {file_type}
- Ingested: {today}

Summary: {summary}

Key takeaways:
{key_takeaways}

Tags: {tags}

Entity pages created/updated from this source:
{entity_links}

Concept pages created/updated from this source:
{concept_links}

Write a complete markdown page with:
1. YAML frontmatter: title, type: source, tags, created: {today}, updated: {today}, file_path, file_type
2. An H1 heading matching the title
3. Korean section/body text; keep proper nouns, technical terms, commands, file paths, APIs, model names, and code identifiers in English
4. A '요약' section with the summary paragraph
5. A '핵심 내용' section with the takeaways as bullets
6. A '관련 페이지' section with two subsections (Entities, Concepts), each listing [[wikilinks]] to the pages above
7. No made-up facts — only use what's provided above

Return ONLY the markdown content — no preamble, no code fences.
"""


def build_source_page_messages(
    source_title: str,
    source_slug: str,
    file_path: str,
    file_type: str,
    summary: str,
    key_takeaways: list[str],
    tags: list[str],
    entity_slugs: list[str],
    concept_slugs: list[str],
    today: str,
    db_path: Path | None = None,
    use_draft: bool = False,
) -> list[ChatMessage]:
    """Pass 3 — draft the sources/<slug>.md summary page."""
    sys_prompt = get_prompt("system", db_path, use_draft)
    template = get_prompt("source_page", db_path, use_draft)
    takeaways_str = "\n".join(f"- {t}" for t in key_takeaways)
    entity_links = (
        "\n".join(f"- [[entities/{s}]]" for s in entity_slugs)
        if entity_slugs
        else "  (none)"
    )
    concept_links = (
        "\n".join(f"- [[concepts/{s}]]" for s in concept_slugs)
        if concept_slugs
        else "  (none)"
    )
    user_content = template.format(
        source_title=source_title,
        source_slug=source_slug,
        file_path=file_path,
        file_type=file_type,
        summary=summary,
        key_takeaways=takeaways_str,
        tags=", ".join(tags),
        entity_links=entity_links,
        concept_links=concept_links,
        today=today,
    )
    return [
        ChatMessage(role="system", content=sys_prompt),
        ChatMessage(role="user", content=user_content),
    ]


# ---------------------------------------------------------------------------
# Stage 5 — Contradiction detection (used by `wiki lint --deep`)
# ---------------------------------------------------------------------------

CONTRADICTION_DETECTION_PROMPT = """You are reviewing two wiki pages for potential contradictions.

Page A: {path_a}
---
{content_a}
---

Page B: {path_b}
---
{content_b}
---

Compare the factual claims made in these two pages. If you find a clear
contradiction between them, describe it concisely in 1-3 sentences, naming
the specific conflicting claims.

Only flag REAL contradictions — direct factual disagreements, not stylistic
differences or different levels of detail. If a claim in one page simply
elaborates on a claim in the other, that's NOT a contradiction.

If there is no contradiction, respond with exactly the word: NONE

Otherwise, respond with a brief description of the contradiction. Do not
include preamble like "I found" — just state the conflict directly.
"""

import sqlite3
from pathlib import Path

DEFAULT_PROMPTS = {
    "system": SYSTEM_PROMPT,
    "extract": EXTRACTION_INSTRUCTIONS,
    "chunk_extract": CHUNK_EXTRACTION_INSTRUCTIONS,
    "new_entity": NEW_ENTITY_PAGE_TEMPLATE,
    "new_concept": NEW_CONCEPT_PAGE_TEMPLATE,
    "new_entity_json": NEW_ENTITY_PAGE_JSON_TEMPLATE,
    "new_concept_json": NEW_CONCEPT_PAGE_JSON_TEMPLATE,
    "merge_page": MERGE_PAGE_TEMPLATE,
    "merge_page_json": MERGE_PAGE_JSON_TEMPLATE,
    "page_json_retry": PAGE_JSON_RETRY_TEMPLATE,
    "source_page": SOURCE_PAGE_TEMPLATE,
}

def get_prompt(prompt_key: str, db_path: Path | None = None, use_draft: bool = False) -> str:
    if db_path is None or not db_path.exists():
        return DEFAULT_PROMPTS.get(prompt_key, "")
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            if use_draft:
                cur = conn.execute(
                    "SELECT content FROM prompt_versions WHERE prompt_key = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
                    (prompt_key,)
                )
                row = cur.fetchone()
                if row:
                    return row["content"]
            
            cur = conn.execute(
                "SELECT content FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
                (prompt_key,)
            )
            row = cur.fetchone()
            if row:
                return row["content"]
    except Exception:
        pass
    
    return DEFAULT_PROMPTS.get(prompt_key, "")
