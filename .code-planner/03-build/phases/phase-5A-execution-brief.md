# Phase 5A Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/decisions/ADRs.md`
- `.code-planner/02-planning/review/raw-sources-inbox-realignment-prv-feedback.md`

## Phase goal

Connect Inbox pending items to the existing ingest job/LLM pipeline while preserving the user-facing Inbox-first model:

```text
업로드/Raw Sources에서 가져오기
-> Inbox pending
-> source/job materialization
-> existing LLM ingest pipeline
-> Wiki / Review / Failed / Raw Sources archive
```

Raw Sources must not remain the primary processing queue. Existing Raw Sources documents are imported into Inbox before processing.

## Work units

### WU-5A-001. Existing flow discovery

- Purpose: Map current `/ingest`, `inbox_items`, `sources`, `jobs`, and tests before implementation.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `routes/ingest.py`, `inbox.py`, `ingest_raw.py`, `jobs.py`, `ingest_llm.py`, `tests/`.
- Completion criteria: insertion points, duplicate risks, and affected tests identified.
- Verification: discovery report only.

### WU-5A-002. Inbox item to source/job materialization

- Purpose: Implement minimal adapter that creates/reuses a `sources` row for an Inbox item, persists `inbox_items.source_id`, and enqueues existing jobs by `source_id`.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/ingest.py`, possibly `src/llm_wiki/ingest_raw.py` if a helper is needed.
- Completion criteria:
  - `/ingest/start` or equivalent accepts `inbox_item_id` as primary input.
  - Existing `jobs.enqueue(source_id)` and `ingest_llm.ingest_source(source_id)` remain reusable.
  - `inbox_items.source_id` is persisted after materialization.
  - Existing source_id start path remains compatible if needed for old UI/tests.
- Verification: targeted route/domain tests.

### WU-5A-003. Raw Sources import-to-Inbox route

- Purpose: Change scan/import semantics so Raw Sources files become Inbox pending items, not direct `sources` queue entries.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/webapp/routes/ingest.py`, `src/llm_wiki/ingest_raw.py` if file iteration reuse is needed.
- Completion criteria:
  - `/ingest/scan` registers supported Raw Sources files into Inbox via `Inbox/Files` or `Inbox/Markdown`.
  - It does not create `sources` rows as the primary queue action.
  - Imported items appear as `inbox_items.state = pending` before processing.
- Verification: tests that inspect `inbox_items` and absence/no-growth of direct `sources` queue entries.

### WU-5A-004. Tests and validation

- Purpose: Add/update Phase 5A tests and evidence.
- Assigned agent: `build-test-validation`
- Expected files: `tests/test_inbox_to_job_mapping.py` or targeted existing tests; `.code-planner/03-build/evidence/phase-5A-build-evidence.md`.
- Completion criteria:
  - Upload/paste/imported Raw Sources -> Inbox pending -> source/job materialization tested.
  - `inbox_items.source_id` persistence tested.
  - Existing Inbox domain/registration tests remain green.
  - Any legacy `/ingest/scan` tests updated from Raw queue semantics to import-to-Inbox semantics.
- Verification: real pytest + py_compile + `git diff --check`.

## Out of scope

- Phase 5B UI/CLI polish and final `/ingest` mockup alignment.
- Full browser UX testing. It is blocked until Phase 5A passes.
- Refactoring `ingest_llm.ingest_source` to read `inbox_item_id` directly.
- New design system.
- qmd/Obsidian reset product command.

## Validation commands

- `.venv/bin/python -m pytest tests/test_inbox_to_job_mapping.py tests/test_inbox_registration.py tests/test_inbox_domain.py -v` if the new test file is created.
- `.venv/bin/python -m pytest tests/test_web_navigation.py -v` for affected `/ingest` route/template tests if updated.
- `.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/ingest_raw.py src/llm_wiki/jobs.py`
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-5A`: `feat: connect inbox items to ingest jobs`
- Stage only Phase 5A source/test files and required evidence/check report when explicitly requested.

## Risks

- Current worktree contains uncommitted Phase 4 source/test changes, including `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/inbox.py`, `src/llm_wiki/webapp/templates/inbox.html`, and `tests/test_inbox_registration.py`.
- Phase 5A must not begin source edits until Phase 4 changes are committed, stashed, or explicitly accepted as a stacked base.
- `/ingest/scan` semantic change will intentionally break/update legacy tests that expected direct `sources` registration.
- Existing `/ingest` template JS currently posts `source_id`; Phase 5A should preserve backward compatibility or coordinate with Phase 5B.
- Content hash dedupe exists in both Inbox and sources materialization; tests must cover source row reuse.
