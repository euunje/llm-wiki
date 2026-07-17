# Phase 2-pass generation Fix Evidence

## Source fix request

`.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md` (STAB-001/002/003)

## Fixed items

- STAB-001 transactional regression
  - Lint gate moved to pre-commit. New helpers `_build_staged_lint_paths` and updated `_lint_changed_pages`-style flow now copy staged files into a temporary lint root, run lint on that view, and only allow the original `shutil.copy2` step when no lint error remains. If lint errors persist, ingest returns `IngestResult.error` and DB source status flips to `"error"` without ever copying staged files into the live wiki tree.
- STAB-002 retry safety / parse-failure behavior
  - `_generate_page_content` now performs 1 retry on JSON parse failure using the existing `PAGE_JSON_RETRY_TEMPLATE` (with a parse-error description). Persistent parse failure routes new pages to `non_categories/` review fallback and aborts ingest for merge/update pages.
  - Legacy markdown fallback now runs only after retry exhaustion. When invoked, it must still pass type/source/allowed-links validation; otherwise it is rejected and the page falls back to the review path.
- STAB-003 callback error classification
  - Stream callback errors are no longer caught by JSON-parse `except ValueError`. The stream loop now uses a dedicated helper that re-raises callback exceptions (`_StreamCallbackError`). JSON parse failures are caught explicitly and routed into the retry path above. As a result, callback exceptions surface as `IngestResult.error` instead of being silently hidden as review fallback.
- Fix-up (implementation side-effect discovered by `build-test-validation`)
  - `_build_staged_lint_paths` no longer uses `cfg.save_config`, which can be redirected through `LLM_WIKI_CONFIG` and clobber an external runtime config. It writes the lint staging config directly into the temp lint root.

## Files changed

- `src/llm_wiki/ingest_llm.py`
- `tests/test_two_pass_generation.py` (added regression tests: STAB-002 happy-path prose retry, STAB-002 fallback path, STAB-003 callback surfacing; small setup adjustments on existing tests)
- `tests/test_phase2_candidates_schema.py` (setup adjustments to stop using `LLM_WIKI_CONFIG` monkeypatch where the new lint staging interferes with the external runtime config)
- `tests/test_staged_lint_gate.py` (new — STAB-001 staged lint gate end-to-end)

## Commands run

- `./.venv/bin/python -m py_compile src/llm_wiki/ingest_llm.py` → passed
- `./.venv/bin/python -m pytest tests/test_two_pass_generation.py tests/test_phase2_candidates_schema.py tests/test_staged_lint_gate.py -k "not test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks"` → 35 passed, 1 deselected
- `./.venv/bin/python -m pytest tests/ -k "not test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks"` → 64 passed, 1 deselected

## Validation summary

- STAB-001: verified — the `tests/test_staged_lint_gate.py::test_staged_lint_gate_rejects_broken_wikilink` test confirms the staged lint gate aborts before commit, no new page reaches `entities/`, `sources/`, or `non_categories/`, and DB source status is flipped to `"error"`.
- STAB-002 happy path: verified — `test_stab002_prose_first_response_retries_and_succeeds` confirms a prose-only first response is retried via the non-stream chat() call and produces a valid entity page in `entities/`.
- STAB-002 fallback: verified — `test_stab002_both_attempts_prose_routes_to_review` confirms persistent prose-only responses land in `non_categories/` with `status: pending_review` and a parse-failure reason.
- STAB-003: verified — `test_stab003_stream_callback_exception_is_surfaced` confirms a `ValueError` from `callbacks.on_stream_chunk` propagates as `_StreamCallbackError`, is reported in `IngestResult.error`, and prevents the entity page from being committed.

## Remaining risk

- Pre-existing unrelated tests (already failing before this work, deselected by the verification command) remain unchanged: `tests/test_phase2_candidates_schema.py::test_apply_fixes_uses_configured_physical_path_for_malformed_wikilinks`.
- The fix-up side-effect (lint staging not using `cfg.save_config`) is local to `ingest_llm.py:_build_staged_lint_paths` and was added because the new staged-lint flow was previously able to clobber an external runtime config via `LLM_WIKI_CONFIG`. If a future refactor reintroduces `cfg.save_config` for lint staging, ensure the target is explicit.

## Ready for recheck

true
