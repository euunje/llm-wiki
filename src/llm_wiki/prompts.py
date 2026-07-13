"""Prompt templates for the LLM ingest pipeline.

Three passes:
    1. extract — read source, return structured JSON with entities/concepts
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

2. Always use [[wikilinks]] for cross-references between wiki pages.
   Never use plain markdown links for internal pages.

3. Slugs are kebab-case lowercase ASCII (e.g. andrej-karpathy, not Karpathy.md).
   Use the canonical name. Acronyms stay together (rag, llm, not r-a-g).

4. Be factual. Never invent citations or claims not in the source.
   If unsure, mark confidence as 'medium' or 'low'.

5. Page bodies should be concise but substantive: 150-400 words is typical
   for entity pages, 200-500 words for concept pages.

6. Preserve existing content when updating a page. Add new info in new
   sections or under an '## Updates' heading. Never silently overwrite.

7. Routing rules — NEVER create normal wiki pages for operational or
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
3. A 2-3 paragraph body (150-300 words) describing this entity
4. Use [[wikilinks]] when referencing other entities or concepts from the related list above
5. End with a '## Sources' section listing [[sources/{source_slug}]]

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
3. A 2-4 paragraph body (200-400 words) explaining this concept:
   - What it is
   - Why it matters
   - How it relates to other concepts/entities (use [[wikilinks]])
4. End with a '## Sources' section listing [[sources/{source_slug}]]

Do not invent facts. Only use information from the excerpts. Return ONLY the markdown content — no preamble, no code fences.
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
2. Adding new information as either:
   - A new paragraph in the appropriate section, OR
   - A new section if the information is substantively new, OR
   - An '## Updates' section if the new info contradicts something in the existing page.
3. Updating the 'updated:' date in frontmatter to {today}.
4. Adding "sources/{source_slug}.md" to the 'sources:' list in frontmatter (keep existing entries).
5. Adding [[sources/{source_slug}]] to the '## Sources' section at the bottom.
6. Keeping any existing [[wikilinks]] intact.

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
3. A 'Summary' section with the summary paragraph
4. A 'Key Takeaways' section with the takeaways as bullets
5. A 'Related Pages' section with two subsections (Entities, Concepts), each listing [[wikilinks]] to the pages above
6. No made-up facts — only use what's provided above

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
    "new_entity": NEW_ENTITY_PAGE_TEMPLATE,
    "new_concept": NEW_CONCEPT_PAGE_TEMPLATE,
    "merge_page": MERGE_PAGE_TEMPLATE,
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
