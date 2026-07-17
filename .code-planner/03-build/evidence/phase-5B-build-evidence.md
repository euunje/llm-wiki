# Phase 5B Build Evidence

## Work unit
- Phase 5B — CLI/Web UI integration for Inbox-first flow
- Included work units:
  - WU-5B-002 `/ingest` Inbox pending queue alignment (`build-ui-dev`)
  - WU-5B-003 `/jobs` inbox metadata + chunk progress display (`build-core-dev`)
  - WU-5B-004 CLI Inbox-first semantics + `wiki retry` (`build-core-dev`)
- Source planning docs:
  - `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
  - `.code-planner/02-planning/features/feature-ui-cli-integration.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md` (Phase 5B section)
  - `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.{md,html}`
- Phase 5A precursor: `29e4808 feat: connect inbox items to ingest jobs`

## Phase 5B scope delivered

- `/ingest` GET context is now Inbox-first: `inbox.list_inbox_items(conn, state=InboxState.PENDING)` is the primary queue; legacy `sources.status = error` rows are merged for backward-compatible retry visibility only.
- `/ingest` template renders pending Inbox items with separate `input_type` and `status` badges per row. Section title is `Inbox 대기열`. Raw Sources button copy is `Raw Sources에서 Inbox로 가져오기`. Empty state is `Inbox 대기 항목이 없습니다.`
- JS actions (per-item, selected, all) post `inbox_item_id` to `/ingest/start`; legacy `source_id` payload is preserved as fallback for `sources` queue retry rows.
- `/jobs` and `/api/jobs` expose `inbox_item_id` via a `LEFT JOIN (SELECT source_id, MIN(id) FROM inbox_items WHERE source_id IS NOT NULL GROUP BY source_id)` derived subquery; no DB migration. Legacy jobs without inbox mapping render normally.
- `/jobs` template shows `Inbox #<id>` when linked and `phase · NN%` for chunk/progress display.
- `wiki status` shows Inbox counts (pending/processing/review/failed) and a Web hint `/inbox?state=review` when review items exist.
- `wiki retry <inbox_item_id>` moves Failed/Review items back to Pending and cleans the diagnostic sidecar using existing `inbox.move_to_pending`.
- `wiki ingest` (no args) processes pending Inbox items first through `materialize_source_for_inbox_item` then enqueues; `wiki ingest <source_id>` falls back to legacy source-id path.

## Files changed

```text
 src/llm_wiki/cli.py                         | 259 +++++++++++++++++++++++++-
 src/llm_wiki/jobs.py                        |  26 +-
 src/llm_wiki/webapp/routes/ingest.py        |  37 +-
 src/llm_wiki/webapp/templates/ingest.html   |  80 ++--
 src/llm_wiki/webapp/templates/jobs.html     |   3 +-
 tests/test_inbox_to_job_mapping.py          |  50 ++
 tests/test_web_navigation.py                | 107 +++++++++++------
 tests/test_cli_inbox.py                     | (new) focused CLI coverage
```

No modifications to:
- `src/llm_wiki/ingest_llm.py` (worker pipeline reused as-is).
- `src/llm_wiki/webapp/routes/inbox.py` and `templates/inbox.html` (Phase 4 workbench at HEAD).

> **Phase 6 follow-up footnote:** `src/llm_wiki/inbox.py` was later
> modified as part of Phase 6 (archive-finalization prerequisite) to
> unblock E2E rows B-7 / C-3 of
> `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`.
> Specifically, Phase 6 added three module-level symbols:
> `linked_inbox_item_id_for_source(paths, source_id)` (the single
> source of truth for the linked-item SQL — used by both the CLI
> `_linked_inbox_item_for_source` helper in `cli.py` and the background
> `JobManager._linked_inbox_item_id_for_source` helper in `jobs.py`),
> `_is_within_directory(path, directory)` (used by the idempotent
> archive path inside `finalize_successful_ingest`), and the new public
> `finalize_successful_ingest(paths, inbox_item_id, source_id, *,
> event_type, ...)` which centralizes the success-path archive move and
> is called from both the CLI and the `JobManager._run_job` worker.
> See `.code-planner/03-build/evidence/phase-6-build-evidence.md`
> §"Archive-finalization deliverable" for the full change set.

## Validation results

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_inbox_domain.py tests/test_inbox_registration.py tests/test_phase4_review_failed_workbench.py tests/test_cli_inbox.py -v` | **41 passed**, 1 Starlette/httpx deprecation warning, ~34s |
| `.venv/bin/python -m pytest tests/test_inbox_to_job_mapping.py tests/test_cli_inbox.py -v` | **8 passed** (Phase 5A/5B focused) |
| `.venv/bin/python -m py_compile src/llm_wiki/cli.py src/llm_wiki/jobs.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/inbox.py tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_cli_inbox.py` | exit 0 |
| `git diff --check` | exit 0 |

Latest revalidation after PRV shutdown / commit-deferral instruction:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_inbox_domain.py tests/test_inbox_registration.py tests/test_phase4_review_failed_workbench.py tests/test_cli_inbox.py -v` | **41 passed**, 1 Starlette/httpx deprecation warning, 23.41s |
| `.venv/bin/python -m py_compile src/llm_wiki/cli.py src/llm_wiki/jobs.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/inbox.py tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_cli_inbox.py` | exit 0, no output |
| `git diff --check` | exit 0, no output |

Process/port cleanup:
- No dev server, watcher, or background listener started by this work unit.
- `ss -ltnp` / `ps -ef` after validation show only pre-existing listeners (SSH, Syncthing, OpenCode, prior `python3` listener). No leftover pytest/uvicorn/`llm_wiki` process.

## Validation plan coverage (Phase 5B items)

| Phase 5B validation item | Result | Evidence |
| --- | --- | --- |
| `/ingest` registers Files/Markdown/Text into Inbox | PASS | Existing Phase 1/2 inbox registration tests + `tests/test_inbox_to_job_mapping.py` |
| `/inbox` provides Review/Failed filters/actions | PASS (out of Phase 5B scope; Phase 4 workbench) | `tests/test_phase4_review_failed_workbench.py` |
| `/jobs` shows inbox item state and chunk progress | PASS | New `test_jobs_list_and_api_expose_linked_inbox_item_id`, `test_jobs_list_preserves_null_inbox_item_id_for_legacy_jobs`, `test_jobs_page_shows_inbox_item_id_and_phase_progress` |
| CLI `add`, `ingest`, `status`, `retry` reflect Inbox-first semantics | PASS | `tests/test_cli_inbox.py` (3 tests) + existing `tests/test_phase3_fresh_start_guidance.py` |
| Web and CLI share the same DB state model | PASS | Reuses `inbox.list_inbox_items`, `materialize_source_for_inbox_item`, `move_to_pending`, `InboxState` enum |
| UX matches approved Ingest HTML mockup | PASS (string match) | Header/subheader/empty state/Raw Sources CTA per mockup |
| Raw Sources action must not regress to direct queue scan | PASS | `test_ingest_scan_registers_synced_raw_sources` confirms Inbox-only registration |
| UX testing remains blocked unless Phase 5A has passed | PASS | Phase 5A committed at `29e4808`; Phase 5B user-test checklist ready, deferred to user selection |

## Known notes (non-blocking)

- STAB-001 / STAB-002 (informational hardening): `acquire_processing_lock` is held across `ingest_llm.ingest_source(...)`; on uncaught exception the item stays in `PROCESSING`. Matches pre-Phase-5B legacy `ingest_pending` behavior. Deferred to Phase 6 polish.
- STAB-003 (informational): CLI helper functions open separate `db.connect` blocks per call within a loop. Consistent with existing patterns; micro-optimization deferred.
- STAB-004 (informational): `JobRow.inbox_item_id` is joined from `MIN(id)` of `inbox_items WHERE source_id IS NOT NULL`. Correct under Phase 5A one-source-per-inbox contract.
- STAB-005 (informational): `queue_items` merge in `ingest_page` could use a 1-line docstring.

## Out of scope (re-affirmed)

- New design system or new `/ingest` layout.
- qmd/Obsidian reset product command.
- Real-provider LLM E2E (Phase 6).
- Full CLI classification UI beyond status/count/link hint.

## Ready for `/check phase-5B`

- **true.** Scoped Phase 5B validation is green (41 passed), py_compile clean, `git diff --check` clean.
- This evidence does **not** claim a full repository test run; it claims focused Phase 5B validation plus Phase 5A/4/1/2 regression.
- Real user functional test checklist is drafted in `.code-planner/04-check/phase-5B-user-test-checklist.md` and explicitly waits for user direction.
