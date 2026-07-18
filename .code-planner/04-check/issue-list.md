# Issue List — Phase 1 Check

Issue list compiled from this gate's `check-change-scope`, `check-code-stability`, and `check-user-test` subagent reports.

Reused source plan/validation docs:

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`

Issues are listed in the order recorded by the subagents. Issues marked **fixable** are routed to Build via the fix request; issues marked **out-of-scope** are routed to the planning backlog without an in-phase fix.

| ID | Severity | Category | Title | File(s) | Action |
| --- | --- | --- | --- | --- | --- |
| B-1 | medium (blocking in spirit) | security-config | Hardcoded `.env` key mapping leaked into reusable source | `src/llm_wiki/llm/models.py`, `src/llm_wiki/config/settings.py` | fixable (Build) — see `phase-1-fix-request.md` B-1 |
| BL-1 | blocker | security-config | Credential leak via `Authorization` header on configured `models test` failure | `src/llm_wiki/llm/models.py`, `src/llm_wiki/common.py` | fixable (Build) — see `phase-1-fix-request.md` BL-1 |
| BL-2 | blocker | scope | Phase 3 / Phase 2 docs staged in Phase 1 commit | `docs/02_web_ui_features.md`, `docs/04_llm_schema_guide.md` | fixable (Build) — see `phase-1-fix-request.md` BL-2 |
| HI-1 | high | stability | Embedding timeout relies on `SIGALRM` | `src/llm_wiki/pipeline/embed.py`, `src/llm_wiki/config/settings.py` | fixable (Build) — see `phase-1-fix-request.md` HI-1 |
| HI-2 | high | stability | Pipeline leaves jobs in `running` on failure | `src/llm_wiki/pipeline/normalize.py`, `src/llm_wiki/pipeline/chunk.py`, `src/llm_wiki/pipeline/embed.py` | fixable (Build) — see `phase-1-fix-request.md` HI-2 |
| HI-3 | high | affected-flow | Duplicate / orphan normalize jobs after explicit normalize call | `src/llm_wiki/pipeline/ingest.py`, `src/llm_wiki/pipeline/normalize.py` | fixable (Build) — see `phase-1-fix-request.md` HI-3 |
| M-1 | medium | stability | Embedder output validation missing | `src/llm_wiki/pipeline/embed.py` | fixable (Build) — see `phase-1-fix-request.md` M-1 |
| M-2 | medium | security-config | Artifact path containment not enforced for `model_id` | `src/llm_wiki/jobs/records.py`, `src/llm_wiki/llm/models.py` | fixable (Build) — see `phase-1-fix-request.md` M-2 |
| M-3 | medium | affected-flow | `.env.sample` contract is not honored by reusable code | `.env.sample`, `src/llm_wiki/config/settings.py`, `src/llm_wiki/llm/models.py`, `README.md` | fixable (Build) — see `phase-1-fix-request.md` M-3 (overlaps with B-1) |
| M-4 | medium | maintainability | Build evidence contradicts itself about real `.env` and test counts | `.code-planner/03-build/evidence/phase-1-build-evidence.md` | fixable (Build) — see `phase-1-fix-request.md` M-4 |
| L-1 | note | maintainability | Note: same evidence inconsistency also flagged here | see M-4 | fixable (Build) — see `phase-1-fix-request.md` M-4 |

## User-test results

`check-user-test` returned `not_required`. No user functional testing is required for Phase 1 because:

- Phase 1 is CLI-only and the Web UI mockup is `not_applicable`.
- The full Phase 1 E2E was already executed in a clean workspace against the user's real `.env`.
- All 10 CLI E2E plans (`.code-planner/02-planning/validation/cli-e2e-test-plan.md`) passed.
- 29 pytest + 26 manual runner tests pass.
- Sensitive-value masking is exercised by automated tests.
- Phase 2 result-quality judgement (LLM wiki quality) is out of scope for Phase 1.

## Out-of-scope concerns

- Phase 3 Web UI scope is not started and should not appear in the Phase 1 commit.
- Phase 2 LLM schema/prompt contracts are documented in `docs/04_llm_schema_guide.md` but should be planned separately and not committed as part of Phase 1.

## Summary

Verdict route:

```text
changes_requested
```

No commit was created for Phase 1. Re-run `/check phase-1` after Build addresses the items in `phase-1-fix-request.md` and updates `.code-planner/03-build/evidence/phase-1-build-evidence.md`.
