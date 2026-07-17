# Phase 4 Fix Evidence

## Source fix request

- `.code-planner/04-check/fix-requests/phase-4-fix-request.md`
- Original gate result: `changes_requested`
- Recheck report before this fix: `.code-planner/04-check/recheck/phase-4-recheck-report.md`

## Fixed items

### SEC-001 — Failed diagnostic API response size cap

- Status: fixed
- Changed file: `src/llm_wiki/webapp/routes/inbox.py`
- Added `MAX_DIAGNOSTIC_BYTES = 16 * 1024`.
- `GET /api/inbox/items/{item_id}/diagnostic` now caps returned diagnostic content to 16 KiB.
- Response now includes `truncated: bool`; when truncated, it also includes `cap_bytes`.
- Changed test: `tests/test_phase4_review_failed_workbench.py`
- Added `test_diagnostic_response_respects_size_cap`.
- Fixed the prior failed test fixture by making `_make_failed_item(...)` content unique per filename so inbox content-hash dedupe does not reuse the earlier item.

### STAB-002 — Initial filtered tab selection mismatch

- Status: fixed
- Changed file: `src/llm_wiki/webapp/templates/inbox.html`
- Initial `selectedSlug` now falls back to `filtered_items[0].slug` before `items[0].slug`.
- Changed test: `tests/test_phase4_review_failed_workbench.py`
- Extended the route test to call `/inbox?state=failed` without `selected` and assert the selected item matches the first filtered workbench item.

### STAB-001 — Same-path missing source guard

- Status: fixed
- Changed file: `src/llm_wiki/inbox.py`
- `_safe_copy_or_move(...)` now checks `source_path.is_file()` before returning on the same-path short-circuit.
- Missing same-path sources now raise `FileNotFoundError`, allowing `_move_item_file(...)` to record the configured failure event and return `moved=False`.
- Changed test: `tests/test_inbox_registration.py`
- Added `test_move_to_pending_missing_source_file_returns_moved_false_and_records_event`.

## Files changed

- `src/llm_wiki/inbox.py`
- `src/llm_wiki/webapp/routes/inbox.py`
- `src/llm_wiki/webapp/templates/inbox.html`
- `tests/test_phase4_review_failed_workbench.py`
- `tests/test_inbox_registration.py`
- `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
- `.code-planner/04-check/fix-requests/phase-4-fix-request.md`

## Commands run

```text
.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v
```

Result:

```text
24 passed, 1 warning in 7.45s
```

```text
.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py tests/test_phase4_review_failed_workbench.py tests/test_inbox_registration.py
```

Result:

```text
PASS — exit 0, no output
```

```text
git diff --check
```

Result:

```text
PASS — exit 0, no output
```

## Validation summary

- SEC-001 validation passes: bounded diagnostic response test now covers both non-truncated and truncated responses.
- STAB-002 validation passes: `/inbox?state=failed` without explicit `selected` selects the filtered failed item.
- STAB-001 validation passes: missing same-path source produces `moved=False` and records a `pending_move_failed` event.
- Phase 1/2 inbox regression suite remains green.

## Remaining risk

- Full repository pytest was not run.
- Browser-side JS execution is still not covered by TestClient; user functional test remains required before final commit.
- Known unrelated `/ingest` web navigation failure remains out of scope for Phase 4 and is owned by Phase 5.

## Ready for recheck

true
