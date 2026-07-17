# 01 Validation Plan — Build-facing Copy

This file is the Build-facing standard-path copy of `.code-planner/02-planning/validation/validation-plan.md`.

## Required phase checks

### Phase 1

- DB migration is idempotent.
- Existing sources/jobs/runs are preserved.
- Inbox state enum matches docs and code.
- Default and Ja path layouts pass.
- Existing `non_categories`-based tests are compatible or have a clear migration path.
- `processing` works as DB state/lock, not a physical `_Processing` folder.

### Phase 2

- Document file, Markdown file, and pasted text create Inbox items.
- `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text` conventions match docs and implementation.
- Success moves original to Raw Sources archive.
- Failure moves original to `Inbox/_Failed` and creates diagnostic report.
- Review moves original/candidate to `Inbox/_Review`.
- File name collision and duplicate hash handling work.
- Move failure evidence records source path, target path, DB state, and retry capability.

### Phase 3

- Small documents can use single extraction.
- Large documents use `ParsedDocument.chunks`.
- Context overflow 400 triggers chunked fallback.
- Per-chunk candidates/summaries/key_takeaways are collected.
- Chunk extraction progress is recorded in jobs/events.
- Aggregation/dedupe connects to existing resolution flow.
- Late-document entities/concepts are not dropped.

### Phase 4

- All documented Review routing conditions are tested.
- Similar Wiki candidates are displayed.
- Existing-page merge, new entity/concept, and tag/classify actions work.
- Failed diagnostics, retry, delete, and log delete work.
- UX matches approved Review/Failed HTML mockup.

### Phase 5A

- Raw Sources import registers files as Inbox pending items, not direct `sources` queue entries.
- `/ingest/start` or equivalent accepts `inbox_item_id` and resolves/materializes `source_id` internally.
- A job can be enqueued from an Inbox pending item.
- `inbox_items.source_id` is persisted after materialization.
- The existing LLM ingest pipeline still receives a valid `source_id` and can create/update Wiki pages.
- UX/user testing is blocked until this phase passes.

### Phase 5B

- `/ingest` registers Files/Markdown/Text into Inbox.
- `/inbox` provides Review/Failed filters/actions.
- `/jobs` shows inbox item state and chunk progress.
- CLI `add`, `ingest`, `status`, `retry` reflect Inbox-first semantics.
- Web and CLI share the same DB state model.
- UX matches approved Ingest HTML mockup.
- Raw Sources action must not regress to direct queue scan.
- UX testing remains blocked unless Phase 5A has passed.

### Phase 6

- qmd/Obsidian reset is documented as one-time test setup only.
- Raw-to-Inbox test preparation is documented.
- E2E validates document file, markdown scrape, pasted text, large document, failed route, review route, archive move.
- Successful ingest verifies both Wiki page create/update and Raw archive movement.

## Evidence path

- `.code-planner/03-build/evidence/phase-1-*`
- `.code-planner/03-build/evidence/phase-2-*`
- `.code-planner/03-build/evidence/phase-3-*`
- `.code-planner/03-build/evidence/phase-4-*`
- `.code-planner/03-build/evidence/phase-5-*`
- `.code-planner/03-build/evidence/phase-6-*`
