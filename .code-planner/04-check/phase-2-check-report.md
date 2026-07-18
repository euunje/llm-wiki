# Phase 2 Check Report

| Field | Value |
| --- | --- |
| Phase | 2 — LLM Wiki Quality |
| Check verdict | `approved_with_user_test_pending` |
| Commit created | No |
| User functional test required | Yes |
| User functional test approval | Approved by user after repeated 10-topic LLM/schema test review |
| Date | 2026-07-18 |

## Inputs

- Build execution brief: `.code-planner/03-build/phases/phase-2-execution-brief.md`
- Build evidence: `.code-planner/03-build/evidence/phase-2-build-evidence.md`
- Source planning/validation docs:
  - `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
  - `.code-planner/02-planning/phases/01-phase-plan.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md`
  - `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
  - `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
  - `.code-planner/02-planning/decisions/ADRs.md`

## Diff scope inspected

```text
 M src/llm_wiki/bootstrap.py                          |   7 +
 M src/llm_wiki/cli/ops_cmds.py                       |  93 +++++-
 M src/llm_wiki/cli/phase1_placeholders.py            | 235 +++++++++++++++++--
 M src/llm_wiki/pipeline/__init__.py                  |  18 +
 M src/llm_wiki/pipeline/hashing.py                   |  19 +-
 M src/llm_wiki/pipeline/ingest.py                    | 117 ++++++---
 M src/llm_wiki/schema/__init__.py                    |  16 +-
 M src/llm_wiki/schema/candidates.py                  | 176 +++++++++++++
 ?? src/llm_wiki/pipeline/convert.py
 ?? src/llm_wiki/quality.py
 ?? src/llm_wiki/schema/prompts.py
 ?? src/llm_wiki/schema/review.py
 ?? src/llm_wiki/search/__init__.py
 ?? src/llm_wiki/search/vector.py
 ?? tests/run_phase2.py
 ?? tests/test_converter_adapter.py
 ?? tests/test_phase2_schema_quality.py
 ?? tests/test_vector_search.py
 ?? .code-planner/03-build/phases/phase-2-execution-brief.md
 ?? .code-planner/03-build/evidence/phase-2-build-evidence.md
 ?? .code-planner/01-ideation-approved.json
 ?? .code-planner/01-ideation-living-note.md
 ?? .code-planner/02-planning/
 ?? testset/
 M .code-planner/04-check/recheck/phase-1-recheck-report.md
```

Pre-existing/unrelated items observed at the start of the Phase 2 worktree:

- `.code-planner/04-check/recheck/phase-1-recheck-report.md` modified before Phase 2 work began.
- `.code-planner/01-ideation-*`, `.code-planner/02-planning/` untracked planning artifacts.
- `testset/` untracked user-provided validation inputs.

In-scope Phase 2 implementation files match the execution brief WU-002 through WU-008. No `testset/` files were modified.

## Affected flow inspection

| Flow | Files | Finding |
| --- | --- | --- |
| LLM candidate schema validation | `src/llm_wiki/schema/candidates.py`, `src/llm_wiki/schema/__init__.py` | Validator now enforces per-type required fields and rejects `tags`/forbidden metadata; deep recursive scan for forbidden keys is partial (STAB-003). |
| Review persistence | `src/llm_wiki/schema/review.py`, `src/llm_wiki/cli/ops_cmds.py`, `src/llm_wiki/cli/phase1_placeholders.py` | Insert/retry/supersede flow works; `consumed_run_id` is not populated when retrying a candidate (STAB-002). |
| Prompt versioning | `src/llm_wiki/schema/prompts.py`, `src/llm_wiki/bootstrap.py` | Default confirmed prompts are seeded into DB and on-disk at init; idempotent. |
| Quality evaluation | `src/llm_wiki/quality.py`, `src/llm_wiki/cli/phase1_placeholders.py` | Rubric-based scoring works; `gold_available: false` is reported; live LLM prompt execution is not yet wired. |
| CLI quality commands | `src/llm_wiki/cli/phase1_placeholders.py`, `src/llm_wiki/cli/ops_cmds.py` | `extract-claims`, `map`, `summarize`, `ask`, `compile`, candidate `retry` upgraded; placeholder contract preserved when source has no chunks. |
| Non-Markdown conversion | `src/llm_wiki/pipeline/convert.py`, `src/llm_wiki/pipeline/ingest.py`, `src/llm_wiki/pipeline/hashing.py` | HTML→Markdown via stdlib; PDF/Office/URL raise `UnsupportedInputError`; failure artifact trail is incomplete (STAB-001). |
| Vector/RAG search | `src/llm_wiki/search/vector.py`, `src/llm_wiki/cli/ops_cmds.py` | Cosine similarity over `embeddings.vector_json`; model group selection uses MAX(count) heuristic (STAB-008); search metadata shape is inconsistent (STAB-006). |
| Tests | `tests/run_phase1.py`, `tests/run_phase2.py`, `tests/test_*.py` | Phase 1 `26 passed`; Phase 2 `4 passed`. Pytest unavailable in env; stdlib runners used. |

## Required checks

1. Change scope: `changes_requested` (pre-existing Phase 1 recheck report modification and untracked planning artifacts remain; flagged for explicit decision).
2. Affected flow: `changes_requested` (medium stability issues found by `check-code-stability`).
3. Feature completeness: `changes_requested` (Phase 2 schema/prompt/review/quality scaffold is implemented; live LLM prompt execution is not fully wired into every task; PDF/Office real conversion is intentionally deferred per "no new mandatory dependency" rule).
4. Stability: `changes_requested` (STAB-001, STAB-002, STAB-003, STAB-004 are medium).
5. Maintainability: `changes_requested` (STAB-004 docstring inconsistency plus several low-severity cleanups).
6. Security/config: pass. No hardcoded secret/host/key; no new mandatory dependency; `jsonschema` was already declared in `pyproject.toml`; sensitive-data masking utilities continue to be used.
7. Verification evidence: pass. Phase 1 runner 26 OK, Phase 2 runner 4 OK, HTML+testset Markdown smoke pass, PDF/Office explicit unsupported, `git diff --check` clean.

## Convention result

- Python code is consistent with `src/llm_wiki/**` layout.
- Single argparse dispatch in `src/llm_wiki/cli/__init__.py`; command handlers imported there.
- New modules are exported via `src/llm_wiki/schema/__init__.py`, `src/llm_wiki/pipeline/__init__.py`, and `src/llm_wiki/search/__init__.py`.
- `.gitignore` excludes `.env`, `data/`, `vault/`, `.venv/`, caches, `.prv/`.
- No hardcoded secrets, host URLs, localhost URLs, Tailscale IPs, ports, credentials, or user-specific paths in reusable source.
- `testset/` is recorded as untracked input and not claimed as build output.

## Code stability result

`check-code-stability` returned `changes_requested`. Summary:

| ID | Severity | Status |
| --- | --- | --- |
| STAB-001 | medium (security-config) | changes_requested |
| STAB-002 | medium (stability) | changes_requested |
| STAB-003 | medium (maintainability) | changes_requested |
| STAB-004 | medium (maintainability) | changes_requested |
| STAB-005 | low | noted |
| STAB-006 | low | noted |
| STAB-007 | low | noted |
| STAB-008 | low | noted |
| STAB-009 | low | noted |
| STAB-010 | low | noted |
| STAB-011 | low | noted |
| STAB-012 | note | noted |
| STAB-013 | note (security-config) | pass |
| STAB-014 | note | pass |
| STAB-015 | note | pass |

Fix requests are filed for STAB-001 through STAB-004.

## Implementation completeness

Phase 2 schema/prompt/review/quality scaffold and CLI quality upgrade are implemented end-to-end. Live LLM prompt execution into every task and full PDF/Office conversion remain partial; live LLM execution is out of the current deterministic scaffold and full PDF/Office conversion is intentionally deferred under the no-new-mandatory-dependency policy.

## User functional test

`check-user-test` returned `required` because:

- Result quality for Korean summary, title/wiki mapping, and language policy is heuristic-based without gold labels.
- Quality judgement of Korean explanation coherence and English technical-term preservation requires human review.
- Live LLM endpoint is configured but not yet fully wired, so users currently see deterministic placeholder output that still needs quality review.

A user approval is required before commit. See `.code-planner/04-check/phase-2-user-test-checklist.md` for the checklist.

## Git final verification

| Step | Result |
| --- | --- |
| `.gitignore` excludes `.env` | pass |
| `git status --short` | pass (no staged content yet) |
| `git diff --stat` (no staged content yet) | pass, all changes are unstaged/modified |
| `git diff --check` | pass |
| `compileall src tests` | pass |
| `PYTHONPATH=src python3 -m tests.run_phase1` | pass, `26 passed` |
| `PYTHONPATH=src python3 -m tests.run_phase2` | pass, `4 passed` |
| `testset/` Markdown smoke | pass (3 markdown files processed) |
| `testset/` PDF/Office | explicit `UnsupportedInputError`, exit 2 |
| No `.env`/secret files in diff | pass |
| No committed `testset/` PDFs | pass (untracked only) |

## Decision request

The pre-existing Phase 1 recheck report modification and untracked planning artifacts are not strictly fixable inside Build. They are recorded here as a decision request:

- `.code-planner/04-check/recheck/phase-1-recheck-report.md` was modified before Phase 2 work began. The Phase 1 commit `9d155a1` is the canonical Phase 1 record. The worktree-local modification adds commit details that are already in `9d155a1`. Reverting the worktree file matches the canonical commit; keeping it requires a documented rationale.
- `.code-planner/01-ideation-approved.json`, `.code-planner/01-ideation-living-note.md`, `.code-planner/02-planning/` are planning artifacts consumed by the code-planner workflow, not by `wiki` runtime. They must not be staged into a runtime phase commit.

See `.code-planner/04-check/decision-requests/phase-2-decision-request.md` for the structured record.

## Fix requests

- `.code-planner/04-check/fix-requests/phase-2-fix-request.md`

## Notes

- STAB-005..STAB-011 are low-severity cleanups that can be addressed in the same fix pass or the next Phase 2 recheck.
- `pytest` is unavailable in this environment; stdlib runners are the validated harness.

## Commit

No commit was created. Verdict `changes_requested` blocks commit until STAB-001..STAB-004 fixes land, the worktree pre-existing Phase 1 recheck modification is reconciled, and user functional test approval is captured.

---

## Recheck update after Phase 2 fix evidence

Date: 2026-07-18

Inputs added:

- Fix evidence: `.code-planner/03-build/evidence/phase-2-fix-evidence.md`
- Live LLM repeated checks:
  - short sample: 3/3 parsed and schema-valid
  - long testset Markdown: final 3/3 parsed and schema-valid
  - synthetic 10-topic Markdown set: 10/10 parsed and schema-valid

Direct check was performed by the primary agent because the requested minimax3 validation path was unavailable/unstable in this session. The prior subagent findings were rechecked manually against changed files and validation commands.

### Rechecked stability result

| ID | Previous | Recheck status | Evidence |
| --- | --- | --- | --- |
| STAB-001 | medium | resolved | URL/HTML conversion failure now records `ingest_conversion_error` artifact before raising; `tests.run_phase2` covers URL artifact. |
| STAB-002 | medium | resolved | Candidate retry creates follow-up `agent_runs` row and stores `retry_instructions.consumed_run_id`; `tests.run_phase2` asserts it. |
| STAB-003 | medium | resolved | Recursive forbidden-key scan added; nested `subject_ref.human_decision` rejection covered. |
| STAB-004 | medium | resolved | New Phase 2 module docstrings added; `llm_wiki.search.__doc__` explicitly verified after moving docstring to first statement. |

### Direct validation commands

```text
PYTHONPATH=src python3 -c "import llm_wiki.search; assert llm_wiki.search.__doc__"
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m tests.run_phase1
PYTHONPATH=src python3 -m tests.run_phase2
git diff --check
```

Results:

- `compileall`: pass.
- `tests.run_phase1`: pass — `26 tests OK`.
- `tests.run_phase2`: pass — `6 tests OK`.
- `git diff --check`: pass.
- Real LLM parsing/schema stability: pass for documented repeated checks.

### Current gate verdict

`approved_with_notes`

Reason:

- Phase 2 code/stability/security checks now pass.
- The remaining quality judgement was user-approved after the additional 10-topic real LLM parse/schema test summary.
- `check-user-test` remains conceptually required for future quality changes, but the current phase has explicit user approval.

### Commit status

Commit will be created after final staging excludes planning artifacts, `testset/`, `.env`, and the out-of-scope Phase 1 recheck report modification.
