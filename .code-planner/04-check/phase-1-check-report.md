# Phase 1 Check Report

| Field | Value |
| --- | --- |
| Phase | 1 — CLI Foundation |
| Check verdict | `changes_requested` |
| Commit created | No |
| User functional test required | No |
| User functional test approval | N/A |
| Date | 2026-07-18 |

## Inputs

- Build execution brief: `.code-planner/03-build/phases/phase-1-execution-brief.md`
- Build evidence: `.code-planner/03-build/evidence/phase-1-build-evidence.md`
- Source planning/validation docs:
  - `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
  - `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
  - `.code-planner/02-planning/phases/01-phase-plan.md`
  - `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
  - `.code-planner/02-planning/validation/01-validation-plan.md`
  - `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`

## Diff scope inspected

The repository was initialized at this gate. There is no committed baseline yet, so the inspection target is the current working tree as a single candidate Phase 1 commit:

```text
?? .code-planner/
?? .env.sample
?? .gitignore
?? README.md
?? docs/
?? index.md
?? pyproject.toml
?? samples/
?? src/
?? tests/
```

Phase 1 in-scope deliverables present:

- `src/llm_wiki/**` — bootstrap, config, db, jobs, pipeline, schema, llm, cli
- `samples/rag.md`, `samples/short-note.md`
- `tests/test_*.py`, `tests/conftest.py`, `tests/run_phase1.py`
- `pyproject.toml`, `.gitignore`, `.env.sample`, `README.md`
- `.code-planner/03-build/phases/phase-1-execution-brief.md`
- `.code-planner/03-build/evidence/phase-1-build-evidence.md`

Phase-out-of-scope items detected:

- `docs/02_web_ui_features.md` (Phase 3)
- `docs/04_llm_schema_guide.md` (Phase 2)
- The `.env` file at repo root is gitignored and was not staged.

`git diff --stat` is empty because no content is staged yet. `git diff --check` exits 0.

## Affected flow inspection

Check inspected the candidate Phase 1 commit against the planned CLI feature matrix and against the change-scope and stability subagent reports:

| Flow | Files | Finding |
| --- | --- | --- |
| Workspace bootstrap, settings, schema, jobs | `src/llm_wiki/{workspace.py,config/settings.py,db/schema.py,jobs/records.py}` | Settings/DB/jobs are coherent; jobs created but not consistently transitioned to terminal state on failure (see issue HI-2). |
| Markdown ingest pipeline | `src/llm_wiki/pipeline/{ingest.py,normalize.py,chunk.py,embed.py}` | Ingest creates a queued normalize job that is not consumed by `wiki normalize` (see HI-3); embedder output not validated (see M-1); embedder timeout platform-dependent (see HI-1). |
| LLM connection test + route | `src/llm_wiki/llm/models.py`, `src/llm_wiki/cli/models_cmd.py` | Configured failure path can leak the API key (see BL-1); `.env.sample` contract is not honored (see B-1, M-3). |
| Operational commands | `src/llm_wiki/cli/ops_cmds.py`, `src/llm_wiki/cli/{validate_cmd,lint_cmd,fix_cmd,retry_cmd,sync_cmd,status_cmd,search_cmd,healthcheck_cmd}` | Generally consistent; lint/status/healthcheck depend on jobs reaching terminal state (HI-2 fix required). |
| Tests | `tests/**` | 29 pytest + 26 manual-runner tests pass; mock-endpoint success test exists only in the pytest path and is documented as such in the fix request. |
| Evidence | `.code-planner/03-build/evidence/phase-1-build-evidence.md` | Internally contradictory statements about the real `.env` and the manual runner (see M-4). |

## Required checks

1. Change scope: changes_requested (Phase-out-of-scope docs staged)
2. Affected flow: changes_requested (job transition, embedder validation, key leak, scope)
3. Feature completeness: changes_requested (Phase 1 command matrix covered, but flow-level guarantees missing)
4. Stability: changes_requested (timeout portability, partial-success, job terminal state)
5. Maintainability: changes_requested (evidence contradictions)
6. Security/config: changes_requested (BL-1, M-2, B-1, M-3)
7. Verification evidence: changes_requested (real `.env` E2E ran successfully, but evidence needs reconciliation)

## Convention result

- Python code is consistent with `src/llm_wiki/**` layout.
- Single argparse dispatch in `src/llm_wiki/cli/__init__.py`; command handlers imported there.
- pyproject declares `wiki` console script and dev extras.
- `.gitignore` excludes `.env`, `data/`, `vault/`, `.venv/`, caches, and `.prv/`.
- No hardcoded secrets, host URLs, localhost URLs, Tailscale IPs, ports, credentials, or user-specific paths in reusable source.

## Code stability result

`check-code-stability` reported seven findings; see the fix request for full details. Highlights:

- BL-1 (blocker) — credential leak via `Authorization` header
- BL-2 (blocker) — Phase 3 / Phase 2 docs in Phase 1 commit
- B-1 / M-3 — `.env.sample` key mapping not honored by reusable code
- HI-1 — embedder timeout relies on `SIGALRM`
- HI-2 — pipeline leaves jobs in `running` on failure
- HI-3 — duplicate normalize jobs after explicit normalize call
- M-1 — embedder output validation missing
- M-2 — artifact path containment not enforced
- M-4 — evidence wording inconsistencies

## Implementation completeness

Phase 1 command matrix from `.code-planner/02-planning/features/feature-phase1-cli-behavior.md` is implemented. However, the implementation contains:

- A blocker-level credential leak path.
- A scope leak: Phase 2 and Phase 3 docs staged.
- Several stability items that affect operational commands (`status`, `healthcheck`, `lint`).

These issues prevent Check from declaring Phase 1 `approved`.

## User functional test

`check-user-test` returned `not_required` because:

- The full Phase 1 E2E has been run against the user's real `.env` in an isolated workspace.
- All E2E plans (`E2E-01`–`E2E-10`) pass.
- The CLI is the only user surface for Phase 1, and it is fully covered by automated E2E and unit tests.
- LLM result quality judgement (which would trigger user testing) applies to Phase 2, not Phase 1.

User functional test result or approval: N/A (`not_required`).

## Git final verification

| Step | Result |
| --- | --- |
| `.gitignore` excludes `.env` | pass |
| `git status --short` shows only untracked files (no secret files) | pass |
| `git diff --stat` (no staged content) | pass, empty |
| `git diff --check` | pass |
| `compileall src tests` | pass |
| `pytest tests -q` | pass (29) |
| `pytest` did not see secret leakage | pass |
| Manual-runner (`tests/run_phase1.py`) | pass (26) |
| Risk-resolution E2E with real `.env` | pass |
| Full Phase 1 E2E with real `.env` (`/tmp/opencode/phase1-real-env-full-e2e-*`) | pass |

The repository is ready to commit **conceptually**, but the findings below block a clean commit. Therefore no commit is created at this gate.

## Findings and routing

This gate's verdict is `changes_requested`. Detailed items are in `.code-planner/04-check/fix-requests/phase-1-fix-request.md`. Brief:

| ID | Severity | Title | Suggested build agent |
| --- | --- | --- | --- |
| B-1 | medium (blocking in spirit) | Hardcoded `.env` key mapping leaked into reusable source | build-core-dev |
| BL-1 | blocker | Credential leak via `Authorization` header on configured `models test` failure | build-backend-script-dev |
| BL-2 | blocker | Phase 3 / Phase 2 docs staged in Phase 1 commit | build-core-dev |
| HI-1 | high | Embedding timeout relies on `SIGALRM` | build-backend-script-dev |
| HI-2 | high | Pipeline leaves jobs in `running` on failure | build-backend-script-dev |
| HI-3 | high | Duplicate / orphan normalize jobs after explicit normalize call | build-backend-script-dev |
| M-1 | medium | Embedder output validation missing | build-test-validation |
| M-2 | medium | Artifact path containment not enforced for `model_id` | build-backend-script-dev |
| M-3 | medium | `.env.sample` contract is not honored by reusable code | build-core-dev |
| M-4 | medium | Build evidence contradicts itself about real `.env` and test counts | build-test-validation |

## Commit hash

None. No commit was created at this gate because the verdict is `changes_requested`.

## Next step

Build owns the implementation fixes for the items in `phase-1-fix-request.md`. After Build completes, regenerate `.code-planner/03-build/evidence/phase-1-build-evidence.md` with the new validation runs, and re-run:

```text
/check phase-1
```

The next Check should also inspect `.code-planner/04-check/fix-requests/phase-1-fix-request.md` and produce a recheck report under `.code-planner/04-check/recheck/phase-1-recheck-report.md`.
