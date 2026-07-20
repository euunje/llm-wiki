# Phase 3 Check Report

## Phase

- Phase ID: `phase-3`
- Phase Name: Web Review UI (FastAPI + Jinja2 + Vanilla JS)
- Approved UX lock: `.code-planner/02-planning/review/phase-3-ux-mockup-approval.md`
- Execution brief: `.code-planner/03-build/phases/phase-3-execution-brief.md`
- Build evidence: `.code-planner/03-build/evidence/phase-3-fix-evidence.md`

## Changed files

### Tracked (modified, M)

| Path | Classification |
|---|---|
| `.env.sample` | in-scope (added `LLM_WIKI_WEB_ADMIN_PASSWORD` placeholder) |
| `pyproject.toml` | in-scope (added fastapi, uvicorn, jinja2, python-multipart, pydantic, python-dotenv) |
| `src/llm_wiki/cli/__init__.py` | in-scope (`web` subcommand registered) |
| `src/llm_wiki/config/settings.py` | in-scope (added `web.*` settings block) |
| `src/llm_wiki/llm/models.py` | in-scope (route labels, concurrency helpers) |
| `src/llm_wiki/schema/prompts.py` | in-scope (`rollback_prompt_version`, Phase 2 default helpers) |
| `.code-planner/04-check/phase-2-check-report.md` | **unrelated-to-phase-3** — post-Phase-2 bookkeeping, must NOT be staged |
| `.code-planner/04-check/recheck/phase-1-recheck-report.md` | **unrelated-to-phase-3** — post-Phase-1 bookkeeping, must NOT be staged |

### Untracked (new, ??)

In-scope Phase 3 source/test files (must be staged in this commit):

- `src/llm_wiki/cli/web_cmd.py`
- `src/llm_wiki/web/app.py`
- `src/llm_wiki/web/templates/*.html`
- `src/llm_wiki/web/static/js/app.js`
- `src/llm_wiki/web/static/css/style.css`
- `src/llm_wiki/web/__init__.py`
- `tests/test_web_*.py` (10 files)

Out-of-scope / never-stage:

- `.code-planner/**` (planning artifacts)
- `testset/` (pre-existing user inputs)

## Affected flow

- CLI entry: `llm_wiki.cli.web_cmd:run_web_server` → `uvicorn.run(create_app(workspace.root))`
- App factory: `llm_wiki.web.app.create_app`
- Routes mounted (verified by `codebase-explorer`): 12 page routes, 50+ API routes covering Onboarding, Dashboard, Inbox, Mapping, Vault, Wiki, Settings, Auth, Review (legacy)
- Mapping decide chain:
  - Confirm → `/api/mapping/decide` → `api_review_decide` with action in `{approve, merge, create_new, edit}` and `metadata.step=relationship_validate`
  - Reject+instruction → `/api/mapping/candidates/{id}/retry` → `api_review_decide` with `retry_with_instruction` (requires `reason` + `instruction`)
- API key persistence: `persist_workspace_secret(env_name, value, remove_names=...)` writes to `workspace.env_file`, sets `os.environ`, never returns secret
- Vault path safety: `sanitize_vault_relative_path` + `is_visible_vault_path` block `..`, absolute paths, hidden folders
- Prompt rollback: `rollback_prompt_version` archives current confirmed and inserts a new confirmed copy with `rollback_from:<id>` marker
- Concurrency: `get_concurrency_config` / `set_concurrency_config` with default `1`, max `3`, provider-scoped overrides

## Required check results

| Check | Verdict | Note |
|---|---|---|
| 1. Change scope | **partial** | 6 tracked source files in-scope; 2 tracked doc files are post-Phase bookkeeping and must NOT be staged; many planning artifacts untracked |
| 2. Affected flow | **pass** | No broken imports; mapping action chain matches supported set; api_key persistence verified |
| 3. Feature completeness | **partial** | 3 dead endpoints / no-ops found; user-test not approved |
| 4. Stability | **partial** | No critical security issues; 4 functional gaps (see Issue List) |
| 5. Maintainability | **partial** | `fs_helpers.py` orphan module; `review.html` legacy coexists with `mapping.html` |
| 6. Security/config | **pass** | `.env.sample` uses placeholders; `.env` not in working tree; secret never returned by API |
| 7. Verification evidence | **partial** | 48/48 TestClient pass; Playwright pass; but user-tailnet approval missing and 3 endpoint no-ops reproduce |

## Convention result

- FastAPI app, Jinja2 templates, Vanilla JS — matches approved stack
- No React / Vite / Tailwind / Next additions detected
- All new deps justified by FastAPI + Inbox upload + Jinja2 templates
- `git diff --check` passes

## Code stability result

Identified by `codebase-explorer` and confirmed by smoke probe (`TestClient` returns `404`):

1. `/api/setup/fs/browse` → `404` (Onboarding file browser silently fails)
2. `/api/wiki/pages/{concept_id}/graph` → `404` (Wiki graph section always shows fallback)
3. Settings concurrency `btn-save-concurrency` click handler only shows a toast — does **not** POST to `/api/settings/llm/concurrency`
4. `src/llm_wiki/fs_helpers.py` (`safe_list_dir`, `is_path_under_directory`) is unreferenced; web app implements path safety inline

## Implementation completeness

- Approved contracts: 18/18 pass (`tests/test_web_phase3_approved_contracts.py`)
- Full Web suite: 48/48 pass
- Browser access audit: 31/31 page/control checks pass
- 4 endpoint/JS gaps remain (see Issue List)

## User functional test

- Required: **yes**
- Approval state: **not approved**
- Checklist: `.code-planner/04-check/phase-3-user-test-checklist.md`
- Blocking questions are unresolved

## Git final verification

- `git status --short`: 8 tracked modified, 27 untracked, 0 staged
- `git diff --stat`: 8 files changed, 337 insertions(+), 4 deletions(-)
- `git diff --check`: passed (no whitespace errors)
- `git log --oneline -3`:
  - `029f799 feat(phase-2): search E2E follow-up`
  - `8a98509 feat(phase-2): LLM wiki quality`
  - `9d155a1 feat(phase-1): CLI foundation`
- Secrets: not present in any tracked diff or untracked Phase 3 source files (`.env` not in working tree; `.env.sample` uses placeholders)
- Unrelated tracked modifications: `.code-planner/04-check/phase-2-check-report.md`, `.code-planner/04-check/recheck/phase-1-recheck-report.md`

## Commit hash

- Not committed in this check

## Gate decision (initial)

**`changes_requested`** (issued in this report).

Reasons:

1. Three functional/UX gaps exist between approved JS behavior and current backend (`/api/setup/fs/browse`, `/api/wiki/pages/{id}/graph`, settings concurrency save).
2. `fs_helpers.py` is unreferenced and should either be wired or removed.
3. User-tailnet functional test has not been approved.
4. Two tracked files (Phase 1/2 check reports) carry unrelated bookkeeping and must NOT be included in the Phase 3 commit — they need `git checkout` before staging.

Not approved. Returned to Build with `phase-3-fix-request.md`.

## Recheck (2026-07-19)

- Recheck report: `.code-planner/04-check/recheck/phase-3-recheck-report.md`
- Build applied FR-3-01..04; tests 50/50 pass; endpoint smoke confirms the three dead endpoints are now wired.
- New recheck surfaced additional medium-risk items: STAB-001 (auth-failure-on-API), STAB-002 (Wiki graph empty state), STAB-005 (vault symlink cycle), STAB-007 (hidden directory enumeration).
- Recheck gate: **`changes_requested`** (process blockers: unrelated tracked docs, user-test approval).

## Next actions

1. Build implements the four fix-request items.
2. User runs the Tailnet checklist and approves (or reports new gaps).
3. `git checkout` the two Phase 1/2 check report modifications.
4. `/check phase-3` is rerun.
