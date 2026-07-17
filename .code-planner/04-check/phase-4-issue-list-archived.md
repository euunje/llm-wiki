# Phase 4 Check — Issue List (archived)

- Phase: 4 — Review/Failed workbench behavior
- Date: 2026-07-16
- Working directory: project root

This file is the **archived** Phase 4 issue list, captured here for the historical
record. The active `.code-planner/04-check/issue-list.md` was updated to Phase 5A
in 2026-07-16; the Phase 4 content is reproduced below verbatim from the prior
working version.

## Summary

- Severity summary: 2 fixable (SEC-001 medium, STAB-002 low), 1 inherited low (STAB-001), 4 notes (SEC-002, SEC-003, MAINT-001, MAINT-002, MAINT-003).
- Out-of-scope leak: none.
- Pre-existing unrelated failure: `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions` (confirmed pre-existing via `git stash` reproduction; Phase 5 owner).

## Fixable issues (changes_requested)

| id | title | target | severity |
| --- | --- | --- | --- |
| SEC-001 | Failed diagnostic API returns full sidecar with no length cap | `src/llm_wiki/webapp/routes/inbox.py`, `GET /api/inbox/items/{id}/diagnostic` | medium |
| STAB-002 | Initial `selectedSlug` falls back to unified `items[0]` instead of `filtered_items[0]`, causing detail/sidebar mismatch on non-"all" tabs | `src/llm_wiki/webapp/templates/inbox.html`, line 289 | low |
| STAB-001 (inherited) | `_safe_copy_or_move` same-path shortcut can mask missing source files; affects `move_to_pending` only in a contrived scenario | `src/llm_wiki/inbox.py`, `_safe_copy_or_move` | low |

Fix request: `.code-planner/04-check/fix-requests/phase-4-fix-request.md`

## Notes (non-blocking)

- SEC-002: absolute filesystem paths disclosed in API responses (`path`, `diagnostic_path`). Local-first scope; no exit path.
- SEC-003: `_db_item_path` uses `Path.resolve()` without `paths.root` containment check. Trust boundary comes from `relpath` being set by trusted domain code.
- MAINT-001: `_db_workbench_items` and `_serialize_item` duplicate item-shape construction. Consolidate into one helper when convenient.
- MAINT-002: `itemBasePath(it)` defined but unused; JS handlers inline `var base = it.item_id ? ...`. Use or remove.
- MAINT-003: `move_to_pending` accepts any source state (incl. `archived`/`ingested`). Gate on allowed source states when convenient.

## Pre-existing unrelated failures

- `tests/test_web_navigation.py::test_ingest_pending_sources_render_batch_queue_actions`. Reproduction confirmed via `git stash` on a clean pre-Phase-4 commit. Phase 5 owner.

## Verification evidence

- Phase 4 focused tests: 3 passed in 3.85s.
- Phase 1/2 inbox regression: 19 passed.
- `py_compile`: exit 0.
- `git diff --check`: exit 0.

See: `.code-planner/03-build/evidence/phase-4-build-evidence.md`.
