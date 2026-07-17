# 02 Detailed Phase Tasks

## Phase 1 — Inbox domain model and path/state foundation

- Define `inbox_items`/events/candidates or equivalent schema.
- Add idempotent migration while preserving existing sources/jobs/runs.
- Define state enum: `pending`, `processing`, `failed`, `review`, `archived`, `ingested`.
- Define path semantics for Inbox root, `_Failed`, `_Review`, Raw Sources archive.
- Ensure `processing` is DB state/lock only.
- Confirm default and Ja vault layout compatibility.

## Phase 2 — Inbox registration and file movement

- Register three input types: document file, Markdown/Obsidian scrape, pasted text.
- Use recommended input conventions: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- Store pasted text metadata/tags/source_url in generated `.md` frontmatter.
- Implement move flow: pending -> processing DB state -> Raw archive / `_Failed` / `_Review`.
- Create diagnostic report for failures.
- Handle duplicate hash/path collisions.
- Record move failure evidence: source path, target path, DB state, retry capability.

## Phase 3 — Chunked extraction map-reduce

- Preserve small-document single extraction path.
- Use `ParsedDocument.chunks` for large documents.
- Detect context overflow 400 and fall back to chunked extraction.
- Extract per-chunk summaries/candidates/key takeaways/provenance.
- Aggregate and dedupe chunk results.
- Emit chunk extraction progress to jobs/events.
- Route chunk failures to retry/failed/review as appropriate.

## Phase 4 — Review/Failed workbench behavior

- Implement Review routing conditions:
  - fuzzy duplicate/merge ambiguity
  - multiple exact/near matches
  - low/ambiguous/pending confidence
  - entity/concept classification ambiguity
  - guide/runbook/map/MOC content not directly canonical
  - JSON validation failed after retry
  - allowed_links or links_used mismatch
  - source reference missing/unclear
  - source/canonical slug conflict
  - chunk extraction conflict
  - human-approved merge/update required
- Show similar Wiki candidates and previews.
- Support merge into existing page, create new entity/concept, tag/classify, reprocess, hold/reject.
- Show Failed diagnostics and support retry/open source/hold/archive/delete/log delete.

## Phase 5A — Inbox-to-Job dispatch mapping

- Implement `inbox_item_id -> source_id -> ingest_job` mapping.
- At processing start, create or reuse a `sources` row for the Inbox item.
- Persist `inbox_items.source_id` after materialization.
- Update `/ingest/start` or equivalent API to accept `inbox_item_id` as the primary input.
- Keep existing `jobs.enqueue(source_id)` and `ingest_llm.ingest_source(source_id)` pipeline unless a targeted adapter is needed.
- Change `/ingest/scan` semantics from Raw queue registration to “Raw Sources에서 Inbox로 가져오기”.
- Ensure imported Raw Sources files appear as `inbox_items.state = pending` before any LLM processing starts.
- Add tests for upload/paste/imported Raw Sources -> Inbox pending -> job enqueue.
- Do not start UX approval until this phase passes.

## Phase 5B — CLI/Web UI integration

- Update `/ingest` to display Inbox pending items, not legacy `sources.status = pending` as the primary queue.
- Express Raw Sources action as “Raw Sources에서 Inbox로 가져오기”, not normal scan queue.
- Update `/inbox` for Review/Failed filters and actions.
- Update `/jobs` to show inbox item metadata and chunk progress.
- Update CLI:
  - `wiki add`: Inbox registration
  - `wiki ingest`: process pending Inbox
  - `wiki status`: counts and review Web hint
  - `wiki retry <inbox_item_id>`: retry Failed item
- Compare implementation against approved HTML mockups after Phase 5A passes.

## Phase 6 — Test reset guide and E2E validation

- Document one-time qmd/Obsidian reset as test setup only.
- Document moving existing Raw material into Inbox for testing.
- Validate E2E matrix:
  - document file
  - markdown scrape
  - pasted text
  - large document chunked extraction
  - failed route
  - review route
  - archive move
  - existing `vault/10.Raw Sources` document import into Inbox before processing
- Capture evidence under `.code-planner/03-build/evidence/phase-*`.
