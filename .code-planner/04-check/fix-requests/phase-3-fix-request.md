# Phase 3 Fix Request

## Problem target

| ID | Target | Reason | Improvement spec | Suggested build agent | Validation required | Acceptance criteria |
|---|---|---|---|---|---|---|
| FR-3-01 | `src/llm_wiki/web/app.py` (add route) and `src/llm_wiki/web/static/js/app.js` (call site already exists at line 478) | Onboarding wizard vault-step file browser calls `/api/setup/fs/browse?path=...` but no FastAPI route is registered; verified via TestClient smoke probe returning `404`. Result: the Onboarding file browser always shows empty results and breaks the user-approved UX. | Add a FastAPI GET endpoint `/api/setup/fs/browse` that returns folder entries for a workspace-relative path, using the same path-safety helper used by `/api/vault/folder`. Response shape: `{ "status": "ok", "path": "...", "entries": [{"name","kind","path"}, ...] }`. The handler must reject absolute paths and `..` segments with HTTP 422 and must filter hidden dotfiles. | `build-core-dev` | Re-run `tests/test_web_phase3_approved_contracts.py` (extend or add a focused test asserting 200 with valid relative path and 422 for `..`/absolute), then `TestClient` smoke probe calling `/api/setup/fs/browse` against a temporary workspace. | Endpoint returns 200 with valid relative path; returns 422 for `..` and absolute paths; hidden folders excluded; Onboarding wizard file browser shows the listed entries. |
| FR-3-02 | `src/llm_wiki/web/app.py` (add route) and `src/llm_wiki/web/static/js/app.js` (call site already exists at line 1213) | Wiki page graph section calls `/api/wiki/pages/{concept_id}/graph` but no FastAPI route is registered; verified via TestClient smoke probe returning `404`. Result: the Wiki graph area always shows the "연결된 관계가 아직 없습니다." fallback even when relations exist. | Add a FastAPI GET endpoint `/api/wiki/pages/{concept_id}/graph` that returns `{ "status": "ok", "graph": { "nodes": [...], "edges": [...] } }`. Reuse the existing `graph_data()` helper from `llm_wiki.review` if available; otherwise compute from `relations` rows scoped to the concept. Return empty nodes/edges list when the concept has no relations (and 404 only when concept_id is unknown). | `build-core-dev` | Add a focused test in `tests/test_web_phase3_approved_contracts.py` or a new test asserting the response shape with at least one seeded relation; run full Web suite; manual Wiki page inspection in browser. | Endpoint returns 200 with nodes/edges when concept exists; returns 404 only for unknown concept_id; Wiki graph renders edges (not the empty fallback) for seeded relations. |
| FR-3-03 | `src/llm_wiki/web/static/js/app.js` line 1542 | Settings LLM concurrency save button handler shows a toast but does not POST to `/api/settings/llm/concurrency`; verified by reading the handler. Result: changing the radio button and clicking Save does not persist the chosen concurrency. | Update the click handler to send `POST /api/settings/llm/concurrency` with `{ "value": <int> }`, refresh the concurrency payload after success, and surface server errors via toast. Reuse the existing `LlmConcurrencyUpdateRequest` schema and `api_settings_llm_concurrency_update` route. | `build-core-dev` | Add a focused test asserting that the JS handler includes a `POST /api/settings/llm/concurrency` call with the radio value (string check); full Web suite; manual Settings save flow. | Concurrency radio value persists in workspace settings and is reflected in `/api/settings/llm/concurrency` after save. |
| FR-3-04 | `src/llm_wiki/fs_helpers.py` | Module is unreferenced anywhere in the codebase; web app implements path safety inline. | Either: (a) wire `safe_list_dir` and `is_path_under_directory` into `/api/setup/fs/browse` (FR-3-01) and `/api/vault/*` handlers and remove inline duplicates, or (b) delete the file. Recommended: integrate for vault path safety to remove duplicate logic. | `build-core-dev` | After fix, no `?? fs_helpers.py` orphan; full Web suite still passes; manual Vault browser test still safe for path traversal. | Module is imported by web routes, or removed; vault path-safety tests still pass. |
| FR-3-05 | Working tree | `git status` shows two tracked files modified outside Phase 3 scope: `.code-planner/04-check/phase-2-check-report.md` and `.code-planner/04-check/recheck/phase-1-recheck-report.md`. They record post-Phase-1/2 commit hashes and must NOT be in the Phase 3 commit. | Before staging the Phase 3 commit, run `git checkout -- .code-planner/04-check/phase-2-check-report.md .code-planner/04-check/recheck/phase-1-recheck-report.md`. | `build-test-validation` or primary agent | `git status --short` shows those two files no longer as `M`. | Only Phase 3 in-scope files appear in `M` after checkout. |

## Source-doc note

This fix request is the authoritative input for the next Build pass. The previous fix requests in this directory (phase-3-fix-request.md, phase-3-web-ui-ab-wireframes.md, phase-3-user-ui-test-revision-plan.md) remain historical and may continue to inform the agent.

## Acceptance criteria summary

After Build applies FR-3-01..FR-3-05:

1. `PYTHONPATH="src:/tmp/opencode/llm-wiki-local-web-runtime/lib/python3.13/site-packages" /tmp/opencode/llm-wiki-local-venv/bin/pytest tests/test_web_*.py` passes.
2. `git diff --check` passes.
3. `git status --short` shows only Phase 3 in-scope files (no Phase 1/2 bookkeeping).
4. TestClient smoke confirms `/api/setup/fs/browse` and `/api/wiki/pages/{concept_id}/graph` return 200; `/api/settings/llm/concurrency` POST persists.
5. User runs `.code-planner/04-check/phase-3-user-test-checklist.md` and explicitly approves.

## Recheck follow-up

After FR-3-01..04 were implemented, recheck surfaced additional medium-risk items. Add the following to a follow-up fix request if any are blockers:

| ID | Target | Severity |
|---|---|---|
| FR-3-06 | `src/llm_wiki/web/static/js/app.js` `apiFetch` and `require_auth` | medium — Auth failure should not be reported as success when session expires mid-API call |
| FR-3-07 | `src/llm_wiki/web/static/js/app.js` `loadWikiGraph` | medium — Empty graph for known concept shows blank; should show explicit "no relations" state |
| FR-3-08 | `src/llm_wiki/web/app.py` `vault_tree_node` | medium — Skip symlink directories to avoid recursion loops |
| FR-3-09 | `src/llm_wiki/web/app.py` `sanitize_workspace_browse_path` + `safe_list_dir` | low/medium — Reject explicit hidden path components and filter hidden components in resolved ancestry |
