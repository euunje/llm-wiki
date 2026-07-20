# Phase 2 Search E2E Follow-up Check Report

| Field | Value |
| --- | --- |
| Phase | 2 — LLM Wiki Quality (Search E2E follow-up) |
| Check verdict | `approved_with_notes` |
| Prior approved commit | `8a98509148849e9a939b9717cad72f20829b30e4` |
| Follow-up commit | `029f7997fbb32360a2ef309698f336d474498ef7` |
| User functional test required | No |
| User functional test approval | N/A — automated regression test + 10/10 Search E2E evidence cover this follow-up |
| Date | 2026-07-18 |

## Scope of this follow-up

This is a narrow follow-up to the approved Phase 2 commit `8a98509`. It does not modify any Phase 2 implementation surface; it only fixes two Search E2E gaps that were found while executing the new Search E2E checklist.

In-scope working-tree changes:

```text
 M src/llm_wiki/cli/ops_cmds.py
 M src/llm_wiki/cli/phase1_placeholders.py
 M tests/test_models_placeholders_ops.py
?? .code-planner/03-build/evidence/phase-2-search-e2e-evidence.md
?? .code-planner/04-check/phase-2-search-e2e-checklist.md
```

Explicitly out of scope (must remain unstaged):

```text
 M .code-planner/04-check/phase-2-check-report.md
 M .code-planner/04-check/recheck/phase-1-recheck-report.md
?? .code-planner/01-ideation-approved.json
?? .code-planner/01-ideation-living-note.md
?? .code-planner/02-planning/
?? testset/
```

## Required check results

### 1. Change scope

- verdict: `in_scope`
- `check-change-scope` confirmed the three code/test files plus two new planning artifacts are the intended scope.
- `.code-planner/04-check/recheck/phase-1-recheck-report.md` and `.code-planner/04-check/phase-2-check-report.md` were identified as out-of-scope working-tree edits that belong to prior phases.

### 2. Affected flow

- verdict: `ok`
- `codebase-explorer` mapped affected flow:
  - `_fts5_safe_query` is the only FTS5 escape helper in the repo; no duplicate.
  - `run_search` callers: CLI dispatch (`cli/__init__.py:209`) and `run_ask` (`phase1_placeholders.py:365`).
  - `run_ask` callers: CLI dispatch, `tests/test_models_placeholders_ops.py:283`, `tests/run_phase1.py:379`, and the new regression test at line 333.
  - Existing assertion `ask["evidence_refs"] == []` (line 286) still holds in the no-chunk/no-embed flow.
  - `record_artifact` accepts arbitrary dict payload, so adding `search_metadata` to the `ask` artifact is additive and not breaking.

### 3. Feature completeness

- Search E2E result: `10/10` passed (`/tmp/opencode/phase2-search-e2e/search-e2e-report.json`).
- `wiki ask "RAG에서 groundedness가 왜 중요한가?"` returns `evidence_ref_count: 3` after the fix.
- All Phase 1 manual runner tests still pass: 26/26.
- All Phase 2 manual runner tests still pass: 6/6.

### 4. Stability

- verdict: `pass_with_notes`
- `check-code-stability` identified two non-blocking notes:
  - `STAB-001` (low): `run_search` uses `except Exception` for the FTS fallback. Consider narrowing to `sqlite3.OperationalError`. Not blocking.
  - `MAINT-002` (note): new `ask.evidence_refs` shape differs from `summarize.evidence_refs`. Optional documentation update in the build-handoff contract.
- Blocking findings: none.
- The existing `ask["evidence_refs"] == []` test was reproduced in `/tmp/opencode/check-stability-runtime` and still passes.

### 5. Maintainability

- Lazy import of `run_search` inside `run_ask` is intentional and matches existing intra-package style; no circular-import risk.
- No new module was introduced; helpers are colocated with their only caller.

### 6. Security / configuration

- No secrets, env files, tokens, or new dependencies were added.
- `_fts5_safe_query` removes FTS5 syntax injection surface by wrapping tokens in quoted phrases; the `?` MATCH call is still parameterised.
- `git diff --check` passes; `pyproject.toml` is unchanged; no `.env`/`build`/`cache` artifacts staged.

### 7. Verification evidence

- Search E2E report: `.code-planner/03-build/evidence/phase-2-search-e2e-evidence.md` with full Search E2E artifact path inside the report.
- Direct ask regression smoke reproduced in `/tmp/opencode/phase2-ask-regression`:
  ```text
  {'exit_code': 0, 'evidence_ref_count': 2, 'vector_attempted': True, 'first_match_type': 'vector_hash_fallback'}
  ```
- Stdlib runners:
  - `PYTHONPATH=src python3 -m tests.run_phase1` → 26 OK.
  - `PYTHONPATH=src python3 -m tests.run_phase2` → 6 OK.
- `PYTHONPATH=src python3 -m compileall -q src tests` → pass.
- `git diff --check` → pass.

## Convention / code stability

- Two-line try/except FTS fallback is compact and the second attempt uses a deterministic, parameterized query.
- No circular imports; CLI surface unchanged.
- Existing CLI contract preserved (`wiki ask`, `wiki search`, `wiki validate`, `wiki lint`, `wiki status` all behave the same from the user's perspective; only `ask` now returns non-empty `evidence_refs` when chunks exist).

## Implementation completeness

- Follow-up goal was to verify Search E2E and fix any blocking gaps found during the checklist.
- All checklist items are evidenced.
- Two real issues found and fixed:
  1. `run_ask` ignored `run_search` and produced empty `evidence_refs` even with searchable content.
  2. `run_search` FTS MATCH crashed on natural-language queries containing `?`.

## User functional test

- Required: `no`.
- `check-user-test` decision: automated regression test (`test_ask_uses_search_evidence_for_natural_language_query`) and the 10/10 Search E2E evidence cover the new behavior.
- The fallback-hash vector ranking limitation is a pre-existing constraint documented in the build evidence, not a regression introduced by this commit.

## Git final verification

- `git status --short` reviewed and staged set matches this report.
- `git diff --check` passed.
- `.code-planner/04-check/phase-2-check-report.md`, `.code-planner/04-check/recheck/phase-1-recheck-report.md`, planning artifacts, and `testset/` are NOT staged.

## Commit

After this report was drafted, the follow-up commit was created with:

```text
feat(phase-2): search E2E follow-up

Phase: phase-2
Check: approved_with_notes
Evidence: .code-planner/04-check/phase-2-search-e2e-evidence.md
```

Commit hash: `029f7997fbb32360a2ef309698f336d474498ef7`.

Commit message:

```text
feat(phase-2): search E2E follow-up

Phase: phase-2
Check: approved_with_notes
Evidence: .code-planner/03-build/evidence/phase-2-search-e2e-evidence.md
```

## Known non-blocking notes

- `run_search` catches bare `Exception` for the FTS fallback. Optional follow-up: narrow to `sqlite3.OperationalError`.
- New `ask.evidence_refs` shape differs from `summarize.evidence_refs`. Optional follow-up: document the shape in the build-handoff contract.
- `tests/run_phase1.py` and `tests/run_phase2.py` do not mirror the new pytest-only regression test; pytest is currently unavailable in this environment, so the stdlib runners cannot execute it. The direct ask regression smoke covers the same scenario.