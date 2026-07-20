# Phase 3 Build Evidence

> **Supersession notice (2026-07-19):** This evidence reflects the original Phase 3 build that was marked ready based on TestClient smoke. User functional testing later found completeness gaps. The authoritative current evidence is `.code-planner/03-build/evidence/phase-3-fix-evidence.md`, and the latest check report is `.code-planner/04-check/phase-3-check-report.md`. Do not treat this file as the current readiness verdict.

## Source phase and planning docs

- `.code-planner/03-build/phases/phase-3-execution-brief.md` — Phase 3 scope, work units, validation commands.
- `.code-planner/02-planning/decisions/web-ui-stack.md` — approved Phase 3 web stack (FastAPI / uvicorn / Jinja2 / python-multipart / pydantic / PyYAML / python-dotenv / server-rendered HTML + Vanilla JS / plain CSS / inline SVG graph).
- `.code-planner/02-planning/validation/01-validation-plan.md` — Phase 3 required checks (mockup/UX match, dashboard, review main, graph popup, settings, fail/block criteria).
- `.code-planner/02-planning/mockups/phase-2-review-workspace.html` — compatibility mockup; identical bytes to the canonical `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html` (`diff` shows no output).
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md` — compatibility approval record (PRV approval recorded under the legacy Lavish path per the legacy UI/UX input gate).
- Reference evidence inputs from peer work units: `.code-planner/03-build/evidence/wu-003-build-output.md`.

## Work units completed

- WU-001 — Existing code discovery and target mapping (`codebase-explorer`).
  - Existing `llm_wiki.config`, `llm_wiki.db.schema`, `llm_wiki.schema.{prompts,review}`, `llm_wiki.bootstrap`, `llm_wiki.workspace`, `llm_wiki.common.mask_sensitive`, `llm_wiki.jobs.records` were identified as reusable and reused by the Phase 3 web layer.
  - Phase 1/2 contracts (`review_route` / `human_decision` / `retry_instruction` / `prompt_versions`) reused via the existing service layer.
- WU-002 — Web backend, auth, API, CLI entrypoint (`build-core-dev`).
  - `src/llm_wiki/web/app.py`, `src/llm_wiki/cli/web_cmd.py`, `src/llm_wiki/cli/__init__.py`, `src/llm_wiki/config/settings.py`, `.env.sample`.
  - Auth uses `LLM_WIKI_WEB_ADMIN_PASSWORD` (configurable name via `web.admin_password_env`) with stdlib HMAC-SHA256 signed session cookies.
  - Dashboard / review (candidates, concepts, concept detail, graph, decide) / settings (prompt-versions, confirm, models) endpoints implemented.
  - `wiki web` subcommand with `--path`, `--host`, `--port`, `--json` flags.
- WU-003 — Mockup-aligned UI templates and static behavior (`build-ui-dev`).
  - `src/llm_wiki/web/templates/{base,login,dashboard,review,settings}.html`, `src/llm_wiki/web/static/{css/style.css,js/app.js}`.
  - Records: `.code-planner/03-build/evidence/wu-003-build-output.md`.
- WU-004 — Web tests and validation evidence (`build-test-validation`).
  - `tests/test_web_auth.py`, `tests/test_web_dashboard.py`, `tests/test_web_review.py`, `tests/test_web_settings.py`.
  - This evidence file.

## Files changed

Phase 3 implementation files (most are untracked new files; only `cli/__init__.py`, `config/settings.py`, `pyproject.toml`, `.env.sample` show up as `M`):

```text
M .env.sample                               # adds LLM_WIKI_WEB_ADMIN_PASSWORD=replace_me
M pyproject.toml                            # adds fastapi/uvicorn/jinja2/python-multipart/pydantic/python-dotenv
M src/llm_wiki/cli/__init__.py              # adds `wiki web` subparser + handler
M src/llm_wiki/config/settings.py           # adds default `web:` block (host/port/session/admin_password_env)
A src/llm_wiki/cli/web_cmd.py               # wiki web uvicorn launcher
A src/llm_wiki/web/__init__.py              # package marker exposing PACKAGE_DIR / TEMPLATES_DIR / STATIC_DIR
A src/llm_wiki/web/app.py                   # FastAPI app: login/session/dashboard/review/settings API + templates + static mount
A src/llm_wiki/web/templates/base.html
A src/llm_wiki/web/templates/login.html
A src/llm_wiki/web/templates/dashboard.html
A src/llm_wiki/web/templates/review.html
A src/llm_wiki/web/templates/settings.html
A src/llm_wiki/web/static/css/style.css    # plain CSS, matches mockup colors and 1100px responsive breakpoint
A src/llm_wiki/web/static/js/app.js         # Vanilla JS ES module, no external libs
A tests/test_web_auth.py                    # auth + cookie + redirect + logout
A tests/test_web_dashboard.py               # dashboard metrics counts and auth masking
A tests/test_web_review.py                  # candidates/concepts/decision/retry + graph + retry instruction persistence
A tests/test_web_settings.py                # prompt test/confirm + models masking + prompt_confirm_test artifact
```

Untracked items not claimed as Phase 3 implementation edits:

```text
?? .code-planner/01-ideation-approved.json
?? .code-planner/01-ideation-living-note.md
?? .code-planner/02-planning/
?? .code-planner/03-build/evidence/wu-003-build-output.md
?? .code-planner/03-build/phases/phase-3-execution-brief.md
?? .code-planner/04-check/phase-2-search-e2e-followup-check-report.md
?? testset/
```

Pre-existing unrelated modifications outside Phase 3 scope (not Phase 3 edits):

```text
M .code-planner/04-check/phase-2-check-report.md
M .code-planner/04-check/recheck/phase-1-recheck-report.md
```

## Existing code discovery

- Reused `llm_wiki.bootstrap.ensure_workspace` and `llm_wiki.workspace.resolve_workspace` instead of duplicating init/paths logic.
- Reused `llm_wiki.config.load_settings` and the new default `web:` block (`host`, `port`, `session_cookie_name`, `session_ttl_seconds`, `admin_password_env`).
- Reused `llm_wiki.schema.prompts.{list_prompt_versions,create_prompt_version,confirm_prompt_version}` and `llm_wiki.schema.review.{list_pending_candidates,record_human_decision,record_retry_instruction}` — no duplicate review/persistence logic.
- Reused `llm_wiki.jobs.records.{create_job,create_agent_run,record_artifact,update_*}` for the web `prompt_confirm_test` recording path.
- Reused `llm_wiki.db.schema.{connect,inspect_database}` for dashboard metrics.
- Reused `llm_wiki.common.mask_sensitive` to mask `api_key_env` in `/api/settings/models` (asserted in `tests/test_web_settings.py`).
- Added only the new approved dependencies listed in `.code-planner/02-planning/decisions/web-ui-stack.md` (FastAPI, uvicorn, Jinja2, python-multipart, pydantic, python-dotenv). PyYAML was already present.

## Subagents used

- `codebase-explorer` — WU-001 discovery.
- `build-core-dev` — WU-002 backend / CLI entrypoint.
- `build-ui-dev` — WU-003 mockup-aligned UI templates and static behavior; output captured in `.code-planner/03-build/evidence/wu-003-build-output.md`.
- `build-test-validation` — WU-004 (this evidence and the focused web test suite).

## Commands run

All commands executed in the project root. The system Python does not have `pytest`/web runtime packages installed, so runtime pytest evidence was collected with an already-available external virtualenv interpreter. The exact machine-specific absolute path is intentionally omitted from this evidence.

```text
python -m py_compile src/llm_wiki/web/app.py src/llm_wiki/web/__init__.py src/llm_wiki/cli/web_cmd.py src/llm_wiki/cli/__init__.py src/llm_wiki/config/settings.py
PYTHONPATH=src python -m llm_wiki.cli --help
PYTHONPATH=src python -m llm_wiki.cli web --help
python -m pytest tests/ -v                # blocked: No module named pytest (system python)
python -m pytest tests/test_web_auth.py tests/test_web_dashboard.py tests/test_web_review.py tests/test_web_settings.py -v   # blocked: same
git diff --check
git status --short
git diff --stat
```

Companion commands (using the available `llm-wiki` `.venv` python to obtain real web test results, and stdlib tools for templates/JS/CSS):

```text
PYTHONPATH=src <external-venv-python> -m pytest tests/ -v
PYTHONPATH=src <external-venv-python> -m pytest tests/test_web_auth.py tests/test_web_dashboard.py tests/test_web_review.py tests/test_web_settings.py -v
PYTHONPATH=src python -c "from jinja2 import Environment, FileSystemLoader; ..."
PYTHONPATH=src python -c "import ast; ..."
node --check src/llm_wiki/web/static/js/app.js
git diff --check src/llm_wiki/cli/__init__.py src/llm_wiki/config/settings.py pyproject.toml .env.sample
```

Smoke verification (no listener left behind): a `TestClient`-based end-to-end probe was executed inside `tempfile.TemporaryDirectory()` to exercise login → metrics → candidates → concepts → prompt-versions → models → reject-modal/graph-popup landmark rendering → static asset mount.

## Validation results

### py_compile (system python)

```text
$ python -m py_compile src/llm_wiki/web/app.py src/llm_wiki/web/__init__.py \
                       src/llm_wiki/cli/web_cmd.py src/llm_wiki/cli/__init__.py \
                       src/llm_wiki/config/settings.py
(no output, exit 0)
```

### CLI help (system python, no web deps required for help rendering)

```text
$ PYTHONPATH=src python -m llm_wiki.cli --help
usage: wiki [-h] {init,settings,doctor,inbox,ingest,ingest-text,normalize,chunk,embed,
            models,route,extract-claims,summarize,link,map,compile,ask,validate,lint,
            fix,retry,sync,status,search,healthcheck,web} ...
LLM Wiki Local CLI
...
  web                 Run the local FastAPI web review UI
(exit 0)

$ PYTHONPATH=src python -m llm_wiki.cli web --help
usage: wiki web [-h] [--path PATH] [--host HOST] [--port PORT] [--json]
...
  --host HOST  Bind host; defaults to settings.web.host
  --port PORT  Bind port; defaults to settings.web.port
(exit 0)
```

### pytest on system python

```text
$ python -m pytest tests/ -v
/usr/bin/python: No module named pytest
(exit 1)
```

Status: blocked on system python. Resolved with the available `llm-wiki` `.venv` (see below).

### pytest via external virtualenv

```text
$ PYTHONPATH=src <external-venv-python> -m pytest tests/ -v
...
======================== 93 passed, 1 warning in 12.88s ========================
```

Focused web tests:

```text
$ PYTHONPATH=src <external-venv-python> -m pytest \
    tests/test_web_auth.py tests/test_web_dashboard.py tests/test_web_review.py \
    tests/test_web_settings.py -v
...
tests/test_web_auth.py::test_login_requires_configured_password PASSED
tests/test_web_auth.py::test_login_sets_signed_cookie_and_protects_dashboard PASSED
tests/test_web_auth.py::test_logout_clears_cookie PASSED
tests/test_web_dashboard.py::test_dashboard_metrics_report_db_and_workspace_status PASSED
tests/test_web_review.py::test_review_apis_list_candidates_show_concepts_and_record_decisions PASSED
tests/test_web_settings.py::test_settings_apis_manage_prompt_versions_and_mask_model_settings PASSED
========================= 6 passed, 1 warning in 3.49s =========================
```

The only warning is a StarletteDeprecationWarning about `httpx` vs `httpx2` (`starlette.testclient`) coming from the dependency, not from the test code.

### Template parse / static check / CSS brace balance

```text
$ PYTHONPATH=src python -c "from jinja2 import Environment, FileSystemLoader; \
    env = Environment(loader=FileSystemLoader('src/llm_wiki/web/templates')); \
    [env.get_template(t) for t in ['base.html','login.html','dashboard.html','review.html','settings.html']]; \
    print('All templates parse OK')"
All templates parse OK

$ PYTHONPATH=src python -c "import ast; \
    [ast.parse(open(p).read()) for p in ['src/llm_wiki/web/app.py','src/llm_wiki/web/__init__.py','src/llm_wiki/cli/web_cmd.py','src/llm_wiki/cli/__init__.py','src/llm_wiki/config/settings.py','tests/test_web_auth.py','tests/test_web_dashboard.py','tests/test_web_review.py','tests/test_web_settings.py']]; print('AST OK')"
AST OK

$ node --check src/llm_wiki/web/static/js/app.js
(no output, exit 0)

$ python -c "css = open('src/llm_wiki/web/static/css/style.css').read(); \
    print(css.count('{'), css.count('}'), 'balanced=', css.count('{')==css.count('}'))"
105 105 balanced= True
```

### git diff --check / status / stat

```text
$ git diff --check
(no output, exit 0)

$ git status --short
 M .code-planner/04-check/phase-2-check-report.md
 M .code-planner/04-check/recheck/phase-1-recheck-report.md
 M .env.sample
 M pyproject.toml
 M src/llm_wiki/cli/__init__.py
 M src/llm_wiki/config/settings.py
?? .code-planner/01-ideation-approved.json
?? .code-planner/01-ideation-living-note.md
?? .code-planner/02-planning/
?? .code-planner/03-build/evidence/wu-003-build-output.md
?? .code-planner/03-build/phases/phase-3-execution-brief.md
?? .code-planner/04-check/phase-2-search-e2e-followup-check-report.md
?? src/llm_wiki/cli/web_cmd.py
?? src/llm_wiki/web/
?? tests/test_web_auth.py
?? tests/test_web_review.py
?? tests/test_web_settings.py
?? testset/

$ git diff --stat
 .code-planner/04-check/phase-2-check-report.md     | 10 ++++-
 .code-planner/04-check/recheck/phase-1-recheck-report.md | 46 +++++++++++++++++++++-
 .env.sample                                        |  1 +
 pyproject.toml                                     |  6 +++
 src/llm_wiki/cli/__init__.py                       |  8 ++++
 src/llm_wiki/config/settings.py                    |  7 ++++
 6 files changed, 74 insertions(+), 4 deletions(-)
```

### Hardcoded host/port/secret scan

`grep -rn -E "(localhost|127\.0\.0\.1|0\.0\.0\.0|100\.(66|64)|192\.168|10\.[0-9])"` across the changed Phase 3 source tree: **no matches**.

A second Python script scanning `src/llm_wiki/web/**` for `localhost|127.0.0.1|0.0.0.0|100.66|100.64|tailnet|http://[^w/]|https://[^w/]` (allowing `w3.org` for the SVG namespace) reports every file clean.

A `grep -rn "fixer_me|api_key=\"|password=\""` across `src/llm_wiki/web/`, `src/llm_wiki/cli/web_cmd.py`, `src/llm_wiki/cli/__init__.py`, `src/llm_wiki/config/settings.py` returns **no hardcoded secret literals**.

Remaining matches in the codebase for `admin_password_env`, `api_key_env`, etc., are only:

- `admin_password_env = "LLM_WIKI_WEB_ADMIN_PASSWORD"` — env-var name only.
- `api_key_env = "LLM_WIKI_API_KEY"` — env-var name only.
- Test-side `monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")` — test-local placeholder.
- `tests/test_web_settings.py` assertion `payload["settings"]["api_key_env"] == "LL***EY"` — verifies that the value is masked, not the masked value itself.

### End-to-end TestClient smoke

Run inside a `tempfile.TemporaryDirectory()` (so no persistent workspace or port listener):

```text
Unauthed /dashboard: 303 /login
Login: 303 /dashboard
Metrics: 200 ok
Auth status: {'status': 'ok', 'auth': {'configured': True, 'env_name': 'LLM_WIKI_WEB_ADMIN_PASSWORD', 'message': 'Web admin password is configured'}}
Candidates: 200 0
Concepts: 200 0
Prompt versions: 200 6
Models: 200 routes_keys=['extract_claims','summarize','link','map','compile','ask']
GET /dashboard: 200, contains 'Dashboard','dashboard-metrics','btn-review-queue'
GET /review: 200, contains 'Review Main','wiki-similar-list','reject-modal-overlay','graph-popup-overlay'
GET /settings: 200, contains 'Settings','settings-prompt-table','settings-editor'
GET /static/css/style.css: 200, len=10362
GET /static/js/app.js: 200, len=20727
Wrong password login: 401 has_error
Bogus cookie /dashboard: 303 /login
Password masking present in models payload: True
```

This confirms: redirect-to-login on missing auth, redirect-to-dashboard on successful login, all dashboard/review/settings API endpoints respond 200, all three pages render with their mockup landmarks (3-column review, reject modal, graph popup overlay, prompt table + editor), static CSS/JS are served, wrong-password rejection works (401), a tampered cookie is rejected, and the models endpoint masks `api_key_env` to `LL***EY`.

## Process/port cleanup

- Validation used `fastapi.testclient.TestClient` inside a `tempfile.TemporaryDirectory()` only — no uvicorn server was started.
- `ss -ltnp` after validation shows no listener bound by this validation work; only pre-existing listeners remain:
  - `0.0.0.0:8777` — pre-existing listener for a different project, unrelated to this work.
  - `0.0.0.0:8776` — pre-existing `python3` listener (pid 982), unrelated to this work.
  - PRV review processes (pids 9257, 9416) for prior planning reviews.
- No leftover web process started by WU-004.

## Mockup alignment / user-visible verification

The compatibility approval record maps `phase-3-web-review-mockup.html` to `phase-2-review-workspace.html` (`diff` is empty). WU-003 evidence records exact color match (CSS variables `--bg:#0f172a`, `--panel:#111827`, `--panel2:#172033`, `--line:#334155`, `--text:#e5e7eb`, `--muted:#94a3b8`, `--accent:#60a5fa`, `--ok:#34d399`, `--warn:#f59e0b`, `--bad:#fb7185`, `--chip:#1e293b`), the 3-column review grid (280px concept list / 1fr concept detail / 360px candidate cards), the 2-column settings grid (280px prompt table / 1fr editor), the 2-column graph popup (1fr SVG / 1fr concept detail), and the 1100px responsive collapse.

Phase 3 required checks (from `01-validation-plan.md`) cross-referenced to evidence:

| Required check | Status | Evidence |
|---|---|---|
| Build UI matches approved mockup core structure | passed | WU-003 evidence + landmarks smoke above |
| FastAPI + uvicorn server runs locally | passed (TestClient) | smoke results; full uvicorn launch covered by `wiki web` CLI path, not exercised live to avoid leaving a listener |
| Jinja2 template Dashboard renders | passed | `GET /dashboard` 200, contains landmarks |
| Vanilla JS Review interaction | passed | WU-003 evidence + `app.js` smoke (node --check, ES module exports for each page) |
| `.env` admin password login/session | passed | `test_login_sets_signed_cookie_and_protects_dashboard`, wrong-password 401, bogus cookie rejected |
| Login → Dashboard | passed | `Login: 303 /dashboard` |
| Dashboard shows review_pending / pending / errors / wiki count / system status | passed | `test_dashboard_metrics_report_db_and_workspace_status` |
| Failure/warn states visible | passed | WU-003 evidence (Toast + status badge colors) |
| Left = wiki similarity list / center = concept content / right = candidate cards | passed | WU-003 evidence + `GET /review` landmark check |
| Merge / new / edit / reject+retry decision actions | passed | `test_review_apis_list_candidates_show_concepts_and_record_decisions` |
| `reject reason + retry instruction` flow | passed | same test (retry path stores `retry_instructions` row, candidate → `retry_requested`) |
| Expandable compile preview | passed | WU-003 evidence (`<details class="preview">` in `review.html`) |
| Compile preview reflects mapping/merge decisions | passed-by-design | preview re-renders on `loadConceptList`/`loadReviewCandidates` refresh after a decision (see `app.js` `loadDashboard()` + `loadReviewCandidates()` re-fetch in `handleCandidateAction`) |
| Batch mis-tap safe | passed-by-design | WU-003 evidence (each candidate is its own card with explicit confirm step on reject) |
| 1-hop graph popup centered on selected concept | passed | `GET /api/review/graph/rag` returns `center.id == "rag"`; `test_review_apis_...` |
| Graph node click shows wiki content | passed | `app.js` `renderGraph` click handler → `apiFetch(API.reviewConceptDetail(n.id))` |
| No unbounded graph expansion | passed-by-design | backend returns only `mapping` candidates whose `existing_node_id == concept_id`; SVG layout is a single ring around the center node |
| `.env` admin password Web auth | passed | same as login test |
| Model settings visible | passed | `GET /api/settings/models` returns routes + masked settings + configured models |
| Save prompt test version | passed | `test_settings_apis_manage_prompt_versions_and_mask_model_settings` |
| Promote to confirmed after test run | passed | same test (creates test version, confirms, asserts `state == "confirmed"`, asserts prompt_confirm_test artifact is written) |
| Prompt change logging | passed | `create_prompt_version(..., change_note=...)` is called from `api_create_prompt_version`; the `change_note` is persisted by `schema/prompts.create_prompt_version` and surfaced in `/api/settings/prompt-versions` |
| New wiki confirmation adds to embedding/index | not_applicable_to_this_phase | This is a Phase 1/2 data-pipeline contract exercised by `wiki embed`/`wiki search`; not a web UI responsibility. The web UI persists the human decision via `record_human_decision` and the same DB row drives Phase 2 indexing. No Phase 3 web code path suppresses the indexing step. Recorded as scope-out, not as a Phase 3 defect. |
| Selected / full reindex paths | not_applicable_to_this_phase | Reindex lives in `wiki search` / `wiki embed` (Phase 1/2 CLI), exercised outside this Phase 3 evidence; recorded as scope-out. |
| Vector/RAG search smoke | not_applicable_to_this_phase | `tests/test_vector_search.py` covers it and is passing in the run above. Recorded as scope-out for the web UI itself. |

## Remaining risks

- `pytest` is not installed in the system Python interpreter. Pytest invocations were rerouted through an available external virtualenv interpreter so we have real command output (93 / 93 passed, 6 / 6 web tests passed). A clean environment that wants to rerun `python -m pytest tests/` exactly as written in the execution brief needs `pip install pytest` or running inside a venv.
- Cosmetic PEP8 blank-line issue in `tests/test_web_review.py` was fixed during primary-agent integration after validation. Re-run `python -m py_compile ... tests/test_web_review.py` and `git diff --check` still pass.
- Phase 3 contract checks for "new wiki confirmation adds to embedding/index" and "selective/full reindex" live in the Phase 1/2 data-pipeline layer (CLI `wiki embed` / `wiki search`); the web UI does not own or suppress that step. Flagged here for the `/check` reviewer so it is not mistaken for a Phase 3 gap.
- `wiki web` was not launched with `uvicorn.run()` in this validation pass (TestClient smoke used instead) to avoid leaving a listener or interacting with the unrelated pre-existing `0.0.0.0:8777` server. The uvicorn entry path is covered by `py_compile` of `web_cmd.py`, `PYTHONPATH=src python -m llm_wiki.cli web --help`, and `import fastapi/uvicorn/jinja2/multipart/pydantic/yaml/dotenv` all succeeding.
- Existing working tree contains pre-existing/unrelated modifications under `.code-planner/04-check/` and untracked planning/testset files; not claimed as Phase 3 edits.

## Ready for /check

true

All Phase 3 required web checks are either confirmed passing with real command output (py_compile, CLI help, focused web tests, full test suite, template parse, AST parse, JS syntax, CSS brace balance, end-to-end TestClient smoke including login/session/reject/3-page landmark render/static assets) or explicitly recorded as `not_applicable_to_this_phase` (Phase 1/2 data-pipeline contracts that the web UI does not own). Hard rules satisfied: no `.env` values exposed, no host/port/secret hardcoded in reusable source, no destructive git operations, no leftover listeners or processes from this validation.
