# Phase 4 Check Report (recheck)

- Phase: 4 — Review/Failed workbench behavior
- Working directory: project root
- Check date: 2026-07-16
- Recheck of original gate result (`changes_requested`) and previous recheck report.
- Commit hash: not committed until user functional test confirms.
- Commit message: pending.

## Source artifacts

- Original fix request: `.code-planner/04-check/fix-requests/phase-4-fix-request.md`
- Fix evidence: `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
- Previous recheck report: `.code-planner/04-check/recheck/phase-4-recheck-report.md`
- User test checklist: `.code-planner/04-check/phase-4-user-test-checklist.md`
- Phase 4 build evidence: `.code-planner/03-build/evidence/phase-4-build-evidence.md`

## Changed files (git diff target)

Tracked modifications (`git diff --stat`):

```text
src/llm_wiki/inbox.py                    |  37 ++
src/llm_wiki/webapp/routes/inbox.py      | 586 ++++++++++++++++++++++++--
src/llm_wiki/webapp/templates/inbox.html | 696 ++++++++++++++++++++++++++-----
tests/test_inbox_registration.py         |  36 ++
```

Untracked from this Build/Fix phase (excluded from commit per repo convention):

```text
tests/test_phase4_review_failed_workbench.py
.code-planner/
.prv/
```

`tests/test_phase4_review_failed_workbench.py` will be added to commit by `git add`
explicitly; the `.code-planner/` and `.prv/` paths remain untracked planning/review
artifacts and are not part of the Phase 4 code change scope.

## Affected flow

- `src/llm_wiki/inbox.py`:
  - `move_to_pending(...)` helper (Workbench retry/reprocess).
  - `_safe_copy_or_move(...)` same-path `FileNotFoundError` guard.
- `src/llm_wiki/webapp/routes/inbox.py`:
  - `MAX_DIAGNOSTIC_BYTES = 16 * 1024` constant.
  - `GET /api/inbox/items/{id}/diagnostic` now caps response and includes
    `truncated: bool` plus `cap_bytes` when truncated.
  - All other Phase 4 endpoints (`/hold`, `/retry`, `/reprocess`, `/classify`,
    diagnostic delete, item delete) unchanged.
- `src/llm_wiki/webapp/templates/inbox.html`:
  - `selectedSlug` initial fallback now: server `sel` → `filtered_items[0]`
    → `items[0]`.
- Tests:
  - `tests/test_phase4_review_failed_workbench.py`: focused Phase 4 suite.
  - `tests/test_inbox_registration.py`: STAB-001 regression test for the same-path
    missing-source guard.

## Required check results

| Check | Result | Notes |
| --- | --- | --- |
| 1. 변경 범위 검사 | passed | Verdict from `check-change-scope`: in-scope; no bleed into Phase 5 /ingest or other phases. |
| 2. 영향 흐름 검사 | passed | Verdict from `check-change-scope`: all modified references are coherent with Phase 4 workbench contract. |
| 3. 기능 완성도 검사 | passed | SEC-001, STAB-001, STAB-002 are all closed via the diff + new tests. |
| 4. 안정성 검사 | passed | Verdict from `check-code-stability`: pass; no new regressions introduced. |
| 5. 유지보수성 검사 | pass-with-notes | Pre-existing maintainability notes (MAINT-001/002/003) carried over from prior check, not blocking. |
| 6. 보안/설정 검사 | pass-with-notes | SEC-001 fix closed. SEC-002 / SEC-003 (absolute paths disclosure, containment check) carried over, not blocking for local-first scope. |
| 7. 검증 증거 검사 | passed | Fix evidence file present; focused suite 24 passed; `py_compile` exit 0; `git diff --check` exit 0. |

## Convention result

- Source uses `request.app.state.wiki_paths`, `db.connect`, and the
  `inbox_domain.move_to_*` patterns.
- Template keeps the existing `base.html` extension and Tailwind utility
  classes consistent with the rest of the webapp.
- JS uses the defensive `doAction` helper and JSON-safe serialization via
  `|tojson`.
- Tests follow the existing `scaffold(...) + create_app(...) + TestClient`
  pattern and use approved domain helpers (`inbox.register_markdown_file`,
  `inbox.acquire_processing_lock`, `inbox.move_to_failed`, etc.).

## Code stability result

- Focused pytest run (`tests/test_phase4_review_failed_workbench.py
  tests/test_inbox_domain.py tests/test_inbox_registration.py -v`):
  - 24 passed, 1 warning (httpx/Starlette deprecation, pre-existing).
- `py_compile` on the four changed files: exit 0.
- `git diff --check`: exit 0.
- No secrets, hardcoded hosts, ports, Tailscale IPs, or credentials in the
  diff (verified by grep against the changed files).

Carried-over low/note findings (not blocking):

- MAINT-001: `_db_workbench_items` and `_serialize_item` overlapping item-shape
  construction.
- MAINT-002: `itemBasePath(...)` defined in JS but unused (inline duplication).
- MAINT-003: `move_to_pending` accepts any source state (incl. archived).
- SEC-002: API responses disclose absolute filesystem paths.
- SEC-003: `_db_item_path` uses `Path.resolve()` without `paths.root` containment.
- STAB-PHASE-EMPTY-STRING-DEFAULT (new note): `_db_workbench_items` defaults
  `phase` / `reason` to empty strings; the failed-detail template uses
  `| default('N/A')`, which Jinja only applies to `Undefined`/`None`. UX polish
  only; not a stability or security regression.

## Implementation completeness

- All Phase 4 deliverables continue to be present in the diff:
  - Unified `/inbox` workbench context (legacy non_categories + DB items).
  - Review routing-condition surfacing (heuristic candidates).
  - Review/Failed workbench actions at the route layer.
  - Approved existing-UX mockup alignment (filter tabs + branched detail).
  - Sanitized logs (already covered by `_sanitize_error_detail`).
- Fix request items are all closed (SEC-001, STAB-001, STAB-002).

## User functional test required

- Required: yes (UI/UX change).
- Checklist: `.code-planner/04-check/phase-4-user-test-checklist.md`.
- Approval state: deferred-to-phase-5B sequencing approved by user on 2026-07-16.

## Git final verification result

- `git status --short`: only Phase 4 files (`inbox.py`, `routes/inbox.py`,
  `templates/inbox.html`, `tests/test_inbox_registration.py`) plus untracked
  `tests/test_phase4_review_failed_workbench.py`, `.code-planner/`, `.prv/`.
- `git diff --name-only`: 4 tracked files (above).
- `git diff --check`: exit 0, no whitespace errors.
- `git diff --stat`: 1226 insertions / 129 deletions across the 4 tracked files.
- No `.env`, secrets, cache, or build artifacts in the diff.
- No unrelated files modified.

## Decision

- Result: **`approved_with_notes`**
- Reason: source-side Phase 4 deliverable + fix evidence remain valid and
  validated, and the user accepted the recommended sequencing that defers the
  integrated UI/user-functional verification to the later Phase 5B gate.
- Next step: when explicitly requested, commit Phase 4 first, then Phase 5A,
  then run the deferred user-functional test at the Phase 5B checkpoint.

## Commit plan (after explicit commit request)

- Add only Phase 4 source/test files:
  - `src/llm_wiki/inbox.py`
  - `src/llm_wiki/webapp/routes/inbox.py`
  - `src/llm_wiki/webapp/templates/inbox.html`
  - `tests/test_phase4_review_failed_workbench.py`
  - `tests/test_inbox_registration.py`
- Commit message:

```text
feat: add inbox review workbench

Phase: phase-4
Check: approved
Evidence: .code-planner/04-check/phase-4-check-report.md
```

## Evidence

- `.code-planner/03-build/evidence/phase-4-build-evidence.md`
- `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
- `.code-planner/04-check/recheck/phase-4-recheck-report.md`
- `.code-planner/04-check/issue-list.md`
- `.code-planner/04-check/fix-requests/phase-4-fix-request.md`
- `.code-planner/04-check/phase-4-user-test-checklist.md`
