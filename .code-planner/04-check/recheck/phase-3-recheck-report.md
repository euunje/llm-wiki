# Phase 3 Recheck Report

## Phase

- Phase ID: `phase-3`
- Phase Name: Web Review UI (FastAPI + Jinja2 + Vanilla JS)
- Previous check: `.code-planner/04-check/phase-3-check-report.md` (`changes_requested`)
- Fix request: `.code-planner/04-check/fix-requests/phase-3-fix-request.md`
- Fix evidence: `.code-planner/03-build/evidence/phase-3-fix-evidence.md` (last section: FR-3-01..04 implementation)

## Changed files

### Tracked (modified, M) — in-scope for Phase 3 commit

| Path | Status |
|---|---|
| `.env.sample` | in-scope |
| `pyproject.toml` | in-scope |
| `src/llm_wiki/cli/__init__.py` | in-scope |
| `src/llm_wiki/config/settings.py` | in-scope |
| `src/llm_wiki/llm/models.py` | in-scope |
| `src/llm_wiki/schema/prompts.py` | in-scope |

### Tracked (modified, M) — unrelated / never-stage

| Path | Reason |
|---|---|
| `.code-planner/04-check/phase-2-check-report.md` | Post-Phase-2 commit-hash bookkeeping |
| `.code-planner/04-check/recheck/phase-1-recheck-report.md` | Post-Phase-1 bookkeeping |
| `.code-planner/04-check/issue-list.md` | Planning artifact from check-main recheck |

### Untracked (??) — in-scope for Phase 3 commit

- `src/llm_wiki/cli/web_cmd.py`
- `src/llm_wiki/fs_helpers.py`
- `src/llm_wiki/web/app.py`
- `src/llm_wiki/web/templates/*.html`
- `src/llm_wiki/web/static/js/app.js`
- `src/llm_wiki/web/static/css/style.css`
- `src/llm_wiki/web/__init__.py`
- `tests/test_web_*.py` (10 files)

### Untracked (??) — never-stage

- `.code-planner/**` (planning artifacts)
- `testset/` (pre-existing user inputs)

## Affected flow

Same as previous check. Key new additions confirmed:

- `GET /api/setup/fs/browse` → `sanitize_workspace_browse_path` + `safe_list_dir` → returns `entries`/`folders` with hidden dotfile filtering
- `GET /api/wiki/pages/{concept_id}/graph` → `concept_detail` + `graph_data` → returns 200 with `{graph:{nodes,edges}}` or 404
- `POST /api/settings/llm/concurrency` → `update_concurrency` persists `llm.concurrency` (bounded 1..3)
- JS save button `btn-save-concurrency` now POSTs and refreshes from server
- `fs_helpers.py` is now imported by `web/app.py`

## Required check results

| Check | Previous | Recheck |
|---|---|---|
| 1. Change scope | partial | partial (unrelated tracked docs still present) |
| 2. Affected flow | pass | pass |
| 3. Feature completeness | partial | pass (FR-3-01..04 implemented) |
| 4. Stability | partial | medium issues found (see below) |
| 5. Maintainability | partial | partial (orphan model helpers in `llm/models.py`) |
| 6. Security/config | pass | pass |
| 7. Verification evidence | partial | pass (50/50 + smoke + FR fix evidence) |

## Convention result

- FastAPI + Jinja2 + Vanilla JS stack unchanged
- No new dependencies introduced
- `git diff --check` clean

## Code stability result

`check-code-stability` recheck surfaced 7 medium / 1 low issues. Direct verification:

| ID | Verdict after direct inspection | Notes |
|---|---|---|
| STAB-001 303→HTML auth-failure confusion | **partial** | `require_auth` raises `HTTPException(303, headers=...)`; FastAPI converts 303 to 307. Browser fetch follows 307 to `/login` HTML; `apiFetch` checks status code 401/303, but a 200 login HTML response is treated as success. **Realistic risk for non-API routes; the concurrency POST goes through TestClient so it works there. In browser, if session expires, success toast can be wrong.** |
| STAB-002 graph empty state | **confirmed** | `/api/wiki/pages/solo/graph` returns 200 with `nodes=[center]` and `edges=[]`. JS `loadWikiGraph` checks node count, but renders only edges, so known concepts with no relations show a blank container. |
| STAB-003 duplicate concurrency listener | **needs verification** | `loadSettingsLLM()` is `await`-ed from a page-level `init`; if both page init and concurrency save re-enter the function, duplicate listeners could accumulate. |
| STAB-004 settings key split (`llm.concurrency` vs `llm.max_concurrent_requests`) | **maintainability only** | `app.py` writes `llm.concurrency`; `llm/models.py` reads/writes `llm.max_concurrent_requests`. The web route does not call the helpers, so runtime behavior is correct, but the helper is effectively orphan code. |
| STAB-005 vault tree symlink cycle | **confirmed** | `vault_tree_node` does not check `is_symlink()` or track visited paths. Symlink loops can cause infinite recursion. |
| STAB-006 `PermissionError` becomes empty list | **confirmed** | `safe_list_dir` returns `[]` on `PermissionError`; callers return success. |
| STAB-007 hidden directory enumeration via explicit path | **confirmed** | `sanitize_workspace_browse_path` does not reject dot components; `safe_list_dir` filters by entry name only, so a caller can request `.secret-folder` and see its children. |

## Implementation completeness

- All 4 fix-request items implemented
- `tests/test_web_*.py` 50/50 pass
- Endpoint smoke: `/api/setup/fs/browse` (root/child=200, traversal=422), `/api/wiki/pages/{id}/graph` (known=200, unknown=404), concurrency POST/GET persist

## User functional test

- Required: **yes**
- Approval state: **not approved**
- Checklist: `.code-planner/04-check/phase-3-user-test-checklist.md`

## Git final verification

- `git status --short`: 9 tracked modified, 27 untracked, 0 staged
- `git diff --stat`: 9 files changed, 358 insertions(+), 41 deletions(-)
- `git diff --check`: passed
- Secrets: none in diff or untracked Phase 3 sources (`.env` not in tree; `.env.sample` uses placeholders)

## Commit hash

- Not committed in this recheck

## Gate decision

**`changes_requested`**

Reasons (ordered):

1. **Hard blocker (process):** Three unrelated tracked files (`.code-planner/04-check/phase-2-check-report.md`, `.code-planner/04-check/recheck/phase-1-recheck-report.md`, `.code-planner/04-check/issue-list.md`) must be removed from the staging area via `git checkout` before any Phase 3 commit.
2. **Hard blocker (policy):** User Tailnet functional test is required and not yet approved (8 blocking questions unresolved).
3. **Medium-risk items found in recheck:** STAB-001 (auth-failure-as-success on session-expired API calls), STAB-002 (Wiki graph empty state is rendered blank), STAB-005 (vault tree symlink cycle risk), STAB-007 (hidden directory enumeration). These were introduced or surfaced by the FR-3 fix round and are **not** blocking the 4 original FR items but warrant follow-up.

The originally requested FR-3-01..04 are implemented and verified. The above items are new findings; FR-3-05 is a process cleanup, not a code defect.

## Next actions

1. Build/UI implements the 4 medium-risk items above as a new follow-up fix request (or explicitly waives them as accepted known issues with a written note in evidence).
2. User runs `.code-planner/04-check/phase-3-user-test-checklist.md` and explicitly approves.
3. `git checkout` the three unrelated tracked files.
4. Stage only the in-scope tracked + untracked files.
5. `/check phase-3` is rerun.

---

## Stability Follow-up Applied

- Evidence: `.code-planner/03-build/evidence/phase-3-fix-evidence.md` section `2026-07-19 STAB-001..007 Stability Follow-up`.
- Build work unit: `WU-P3-STAB-FIX`.

### STAB status after follow-up

| ID | Status |
|---|---|
| STAB-001 | fixed and covered: API auth failure returns 401; JS rejects redirected/login HTML/non-JSON API responses |
| STAB-002 | fixed and covered: known concepts with no graph edges render explicit empty state |
| STAB-003 | fixed and covered by JS guard: concurrency handlers no longer stack across repeated loads |
| STAB-004 | fixed and covered: canonical concurrency helper reads Web-saved `llm.concurrency` |
| STAB-005 | fixed and covered: vault tree skips symlink cycles |
| STAB-006 | fixed and covered: permission-denied listings surface HTTP 403 |
| STAB-007 | fixed and covered: hidden explicit path and hidden/outside symlink ancestry blocked |

### Validation after STAB follow-up

```text
57 passed, 1 warning in 30.46s
git diff --check: passed
smoke: unauth-api 401; hidden-browse 422; empty-graph 200 1 0; concurrency-helper 3
```

### Gate note after STAB follow-up

STAB issues are no longer an active code gate. Per user instruction, PROC cleanup remains deferred until after user testing and is not considered the current gate. Remaining gate before commit: user Tailnet/manual functional approval, then PROC cleanup/staging discipline.
