# Phase 4 Fix Request

Phase: 4 — Review/Failed workbench behavior
Severity: medium (SEC-001) + low (STAB-002, STAB-001 inherited)

This request contains three issues. Each issue must be addressed in the same
Build/Fix pass before `/check phase-4` again.

## Fix status metadata

- status: fixed
- assignedAgent: fix-main
- fixedBy: fix-main
- fixedAt: 2026-07-16T05:23:34Z
- buildEvidence: `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
- recheckRequired: `/check phase-4`

---

## Issue A (medium) — Failed diagnostic API has no size cap

- id: SEC-001
- short title: Cap /diagnostic response or document full-content intent
- problem target:
  - File: `src/llm_wiki/webapp/routes/inbox.py`
  - Endpoint: `GET /api/inbox/items/{item_id}/diagnostic`
  - Lines: response body built from `_safe_read_text(diagnostic_path)` without size cap.
- reason:
  - The workbench context caps `log_preview` to 4000 chars for safety and UX, but the same diagnostic content served through the API endpoint returns the full sidecar with no limit. `_create_report_text` is the only writer and already sanitizes the `error` field, so injection is constrained, but inconsistent sizing between the workbench preview and the API endpoint makes future writers risky.
  - There is no test asserting a size bound.
- improvement spec:
  - Apply a length cap (16 KiB or a `MAX_DIAGNOSTIC_BYTES` constant) to the response body and include a `truncated: bool` field so callers can detect cuts.
  - OR add a clear route comment documenting that `_create_report_text` is the only writer and that the endpoint intentionally returns full content; in that case add a test pinning the current behavior.
  - The chosen approach must be reflected in tests.
- suggested build agent: build-backend-script-dev
- validation required:
  - Add a test that asserts the response is bounded (if capping) OR that asserts the current full-content behavior with a known-size fixture (if documenting).
  - Re-run `.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py -v`.
  - Re-run `py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py`.
  - Re-run `git diff --check`.
- acceptance criteria:
  - One of (a) capped response with `truncated` flag and a new test, or (b) explicit route comment + new pinning test.
  - No change to existing APIs.
  - No change to `_create_report_text`.

---

## Issue B (low) — Initial detail/sidebar mismatch on non-"all" tabs

- id: STAB-002
- short title: Use `filtered_items[0]` for initial `selectedSlug`
- problem target:
  - File: `src/llm_wiki/webapp/templates/inbox.html`
  - Line: `var selectedSlug = {{ (sel.slug if sel else (items[0].slug if items else '')) | tojson }};`
- reason:
  - `items[0]` is the unified list. When viewing `/inbox?state=failed` without `?selected=`, the detail panel may show an item that is not in the visible sidebar list, because the sidebar renders `display_items` (server-filtered list).
  - The current behavior is fine on `?state=all` but inconsistent on filtered tabs.
- improvement spec:
  - Replace `items[0]` with `filtered_items[0] || items[0]` (or rely on the server-side `selected_item` already determined by `_selected_item(filtered_items, selected)`).
  - Make sure the JS re-evaluate path at `renderDetail` already falls back to `filtered[0]` when `itemsData[selectedSlug]` is undefined, so the only remaining fix is the initial value.
- suggested build agent: build-ui-dev
- validation required:
  - Add or extend a test that asserts `selected_detail.key` matches `filtered_items[0].key` when `?state=review` or `?state=failed` is set without `selected`.
  - Re-run Phase 4 focused tests.
  - Re-run `py_compile` (template parse via `jinja2.Environment.parse` is acceptable if pytest is locked).
- acceptance criteria:
  - The initial detail panel shows an item present in the server-filtered sidebar list for any non-"all" tab.
  - No regression in the `?selected=` flow.

---

## Issue C (low, inherited) — `_safe_copy_or_move` same-path shortcut can mask missing files

- id: STAB-001
- short title: Verify source exists before same-path short-circuit
- problem target:
  - File: `src/llm_wiki/inbox.py`
  - Function: `_safe_copy_or_move`
- reason:
  - The shortcut at `_safe_copy_or_move` returns success when `source.resolve() == dest.resolve()` without checking `source.is_file()`. `move_to_pending` can be called on a pending item whose file is missing; the function then returns `moved=True` and emits a `moved_to_pending` event for a non-existent file. The normal Phase 4 retry flow (source in `inbox_failed/` or `inbox_review/`, dest is the input-type folder) is unaffected.
- improvement spec:
  - Add a `source_path.is_file()` check before the shortcut. If the source does not exist, append a `move_source_missing` event and return `moved=False` with a clear message.
  - Keep behavior unchanged for the existing happy paths.
- suggested build agent: build-backend-script-dev
- validation required:
  - Add a unit test covering `move_to_pending` on a pending item whose file is missing (path matches dest but file deleted); assert `moved=False` and an event with type containing `pending_move_failed`.
  - Confirm `tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py` still pass.
- acceptance criteria:
  - Missing-file same-path retries are surfaced as failures rather than silent successes.
  - No regression in the existing happy-path tests.

---

## Suggested build agent

| Issue | Agent |
| --- | --- |
| A (SEC-001) | build-backend-script-dev |
| B (STAB-002) | build-ui-dev |
| C (STAB-001) | build-backend-script-dev |

All three can be addressed in one Fix Build pass.

---

## Recheck note 2026-07-16

An attempted `/fix phase-4` left partial changes in the worktree, but no
`.code-planner/03-build/evidence/phase-4-fix-evidence.md` was produced and the
focused validation still fails:

```text
.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v
=> 1 failed, 23 passed
```

Failing test:

```text
tests/test_phase4_review_failed_workbench.py::test_diagnostic_response_respects_size_cap
assert payload_large["truncated"] is True
E assert False is True
```

Observed likely cause:

- The SEC-001 test creates `small-diag.md` and `large-diag.md` with identical
  content through `_make_failed_item(...)`.
- Inbox registration deduplication can return/reuse the existing item for the
  second registration, so the test may overwrite `large-diag.md.diagnostic.md`
  while the endpoint still reads the small item's diagnostic sidecar.
- A manual minimal reproduction using a single unique item and writing the
  returned `result.report_path` shows the route cap itself can return
  `truncated=True` and content length `16384`.

Additional acceptance requirement for the next Fix Build:

- Make the SEC-001 test fixture dedupe-safe by using unique content per item or
  by writing the large diagnostic to the exact `result.report_path` returned by
  `inbox.move_to_failed(...)`.
- Produce `.code-planner/03-build/evidence/phase-4-fix-evidence.md` with the
  actual fix validation commands and results.
