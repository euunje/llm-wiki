# Phase 5A Check — Issue List

- Phase: phase-5A — Inbox-to-Job dispatch mapping (Raw Sources → Inbox import + `inbox_item_id → source_id → ingest_job` adapter)
- Date: 2026-07-16
- Working directory: project root
- Branch: feature/upgrade-plan-implementation (HEAD `865c5b1`)

## Summary

- Severity summary:
  - 0 blocking implementation bugs in Phase 5A scope.
  - 0 open test-failure blockers after Phase 5A semantic-alignment updates to `tests/test_web_navigation.py`.
  - 1 process note: stacked Phase 4 + Phase 5A commit sequencing remains to be executed, but the user has already accepted the recommended order.
  - 2 informational hardening notes (STAB-001, STAB-002) — non-blocking.
  - 2 inherited pre-existing notes from Phase 4 issue list carried over.
- Out-of-scope leak from Phase 5A: none.
- Pre-existing test failures revealed by Phase 5A's intentional semantic change: 2 in `tests/test_web_navigation.py`. Phase 5B owner (per planning).

## Resolved decision items / remaining process notes

| id | title | target | severity |
| --- | --- | --- | --- |
| RESOLVED-1 | `tests/test_web_navigation.py` Phase 5A semantic mismatch resolved by updating expectations to assert Inbox-first API contracts while leaving Phase 5B UI rendering to the later template phase | `tests/test_web_navigation.py::test_ingest_scan_registers_synced_raw_sources`, `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions` | resolved |
| NOTE-SEQ-1 | Stacked Phase 4 + Phase 5A work remains in the same worktree, but the user accepted the recommended commit order: Phase 4 first, then Phase 5A | `src/llm_wiki/webapp/routes/inbox.py`, `src/llm_wiki/webapp/templates/inbox.html`, `tests/test_inbox_registration.py`, `src/llm_wiki/inbox.py`, `src/llm_wiki/webapp/routes/ingest.py` | process note |

Decision record: `.code-planner/04-check/decision-requests/phase-5A-decision-request.md`

## Informational notes (non-blocking, hardening suggestions)

| id | title | target | severity |
| --- | --- | --- | --- |
| STAB-001 (Phase 5A) | `/ingest/start` does not catch `parsers.ParserError`; a corrupted/unreadable Inbox file raises a 500 instead of a 400. Recommended: broaden the route's exception handler to map `ParserError` → 400 (`file not parseable: …`) or convert to `ValueError` inside `materialize_source_for_inbox_item`. Pure graceful-degradation. | `src/llm_wiki/webapp/routes/ingest.py:208-211`, `src/llm_wiki/parsers/base.py:44` | note |
| STAB-002 (Phase 5A) | When `inbox_items.source_id` is set but the linked `sources` row's `relpath` no longer matches, the previously-linked source row is silently orphaned (no audit event links old → new). Recommended: emit a `source_relink` inbox event with `previous_source_id` for traceability. | `src/llm_wiki/inbox.py:598-603` (relpath-mismatch fall-through) and `src/llm_wiki/inbox.py:642-684` (relpath-reuse branch) | note |

Suggested build agent mapping:

- STAB-001 → `build-backend-script-dev`
- STAB-002 → `build-core-dev`

These can be addressed in a follow-up patch or Phase 6 polish without affecting Phase 5A's correctness.

## Inherited carry-overs from prior phases (unchanged)

| id | title | target | severity |
| --- | --- | --- | --- |
| SEC-002 (inherited) | Absolute filesystem paths disclosed in API responses (`path`, `diagnostic_path`). Local-first scope; no exit path. | `src/llm_wiki/webapp/routes/inbox.py` and routes/ingest.py | inherited note |
| SEC-003 (inherited) | `_db_item_path` uses `Path.resolve()` without `paths.root` containment check. Trust boundary comes from `relpath` being set by trusted domain code. | `src/llm_wiki/webapp/routes/inbox.py` | inherited note |
| MAINT-001 (inherited) | `_db_workbench_items` and `_serialize_item` duplicate item-shape construction. Consolidate when convenient. | `src/llm_wiki/webapp/routes/inbox.py` | inherited note |
| MAINT-002 (inherited) | `itemBasePath(it)` defined in JS but unused; inline duplication in handlers. | `src/llm_wiki/webapp/templates/inbox.html` | inherited note |
| MAINT-003 (inherited) | `move_to_pending` accepts any source state (incl. `archived`/`ingested`). Gate on allowed source states when convenient. | `src/llm_wiki/inbox.py` | inherited note |

## Phase 5A semantic-alignment follow-up

- `tests/test_web_navigation.py::test_ingest_scan_registers_synced_raw_sources` — now asserts the Phase 5A Inbox-first scan payload (`counts.added`, `pending_count`, `results[].inbox_item_id/relpath/state/source_id`) and explicitly documents that Inbox-item row rendering on `/ingest` is a Phase 5B template responsibility.
- `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions` — now asserts the Phase 5A Inbox-first upload payload (`files[].inbox_item_id/relpath/state/source_id`) and the page-level queue controls that remain visible before Phase 5B template alignment.

## Test results summary

| Suite | Result | Notes |
| --- | --- | --- |
| `tests/test_inbox_to_job_mapping.py` | 3 passed | Phase 5A focused tests (new file) |
| `tests/test_inbox_domain.py` | 4 passed | Phase 1 regression |
| `tests/test_inbox_registration.py` | 16 passed | Phase 2 + Phase 4 STAB-001 regression |
| `tests/test_phase4_review_failed_workbench.py` | 4 passed | Phase 4 workbench regression |
| `tests/test_web_navigation.py` | 8 passed | Phase 5A semantic-alignment assertions updated |

Compile and lint:

- `py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/ingest_raw.py src/llm_wiki/jobs.py tests/test_inbox_to_job_mapping.py` — exit 0
- `git diff --check` — exit 0

## Changed files scope

| File | Phase 5A attribution | Lines (insertions / deletions) |
| --- | --- | --- |
| `src/llm_wiki/inbox.py` | Phase 5A: `materialize_source_for_inbox_item`, `InboxSourceMaterializationResult`, `_update_inbox_item_source_link`, `_refresh_existing_source_row`. Phase 4 stacked: `_safe_copy_or_move` same-path guard, `move_to_pending` helper. | +262 / -0 |
| `src/llm_wiki/webapp/routes/ingest.py` | Phase 5A: `/ingest/scan` rewrite (Raw Sources → Inbox import), `/ingest/start` rewrite (`inbox_item_id` primary + `source_id` legacy), `_register_raw_source_in_inbox` helper, `db` import. | +78 / -29 |
| `src/llm_wiki/webapp/routes/inbox.py` | Phase 4 stacked only (Phase 5A does NOT modify this). | +586 / -? |
| `src/llm_wiki/webapp/templates/inbox.html` | Phase 4 stacked only (Phase 5A does NOT modify this). | +696 / -94 |
| `tests/test_inbox_to_job_mapping.py` | Phase 5A: new file, 3 focused tests. | +118 / -0 (untracked) |
| `tests/test_inbox_registration.py` | Phase 4 stacked: STAB-001 regression test. Phase 5A does NOT modify this. | +36 / -0 |
| `tests/test_phase4_review_failed_workbench.py` | Phase 4 stacked: new file, 4 tests. Phase 5A does NOT modify this. | +? / -0 (untracked) |

Files explicitly NOT modified by Phase 5A (verified by empty `git diff`):

- `src/llm_wiki/ingest_raw.py`
- `src/llm_wiki/jobs.py`
- `src/llm_wiki/ingest_llm.py` (per planning, "Reuse `jobs.enqueue(source_id)` / `ingest_llm.ingest_source(source_id)` without modification")
- `src/llm_wiki/webapp/templates/ingest.html` (Phase 5B owner)

## Evidence artifacts

- Build evidence: `.code-planner/03-build/evidence/phase-5A-build-evidence.md`
- Phase 5A execution brief: `.code-planner/03-build/phases/phase-5A-execution-brief.md`
- Phase 5A planning: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- Phase 5A feature spec: `.code-planner/02-planning/features/feature-ui-cli-integration.md`
- Phase 5A validation plan: `.code-planner/02-planning/validation/01-validation-plan.md`
- Phase 5A check report: `.code-planner/04-check/phase-5A-check-report.md`
- Phase 5A decision request: `.code-planner/04-check/decision-requests/phase-5A-decision-request.md`
- Phase 4 check report: `.code-planner/04-check/phase-4-check-report.md`
- Phase 4 fix evidence: `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
