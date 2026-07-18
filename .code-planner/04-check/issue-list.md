# Issue List — Phase 2 Check

Issue list compiled from this gate's `check-change-scope`, `check-code-stability`, and `check-user-test` subagent reports.

Reused source plan/validation docs:

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/phases/01-phase-plan.md` — Phase 2
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- `.code-planner/02-planning/decisions/ADRs.md`

Issues are listed in the order recorded by the subagents. Issues marked **fixable** are routed to Build via the fix request; issues marked **out-of-scope** are routed to the planning backlog without an in-phase fix.

| ID | Severity | Category | Title | File(s) | Action |
| --- | --- | --- | --- | --- | --- |
| STAB-001 | medium | security-config | HTML/URL ingest failure artifacts are dropped | `src/llm_wiki/pipeline/ingest.py`, `src/llm_wiki/pipeline/convert.py` | resolved — see `phase-2-fix-evidence.md` |
| STAB-002 | medium | stability | Retry path does not populate `consumed_run_id` | `src/llm_wiki/cli/ops_cmds.py`, `src/llm_wiki/schema/review.py` | resolved — see `phase-2-fix-evidence.md` |
| STAB-003 | medium | maintainability | Forbidden-key check does not recurse into nested objects | `src/llm_wiki/schema/candidates.py` | resolved — see `phase-2-fix-evidence.md` |
| STAB-004 | medium | maintainability | Module docstrings inconsistent on Phase 2 modules | new Phase 2 modules | resolved — see `phase-2-fix-evidence.md` |
| STAB-005 | low | maintainability | Legacy `validate_markdown_input` HTML guidance is contradictory | `src/llm_wiki/pipeline/hashing.py` | noted |
| STAB-006 | low | stability | `run_search` vector metadata shape is inconsistent | `src/llm_wiki/cli/ops_cmds.py`, `src/llm_wiki/search/vector.py` | noted |
| STAB-007 | low | maintainability | Cross-module private import of `_fallback_vector` | `src/llm_wiki/search/vector.py`, `src/llm_wiki/pipeline/embed.py` | noted |
| STAB-008 | low | stability | Vector model group selection uses MAX(count) heuristic | `src/llm_wiki/search/vector.py` | noted |
| STAB-009 | low | maintainability | `run_retry` error message wording for unknown target | `src/llm_wiki/cli/ops_cmds.py` | noted |
| STAB-010 | low | stability | `run_validate` does not handle malformed JSON | `src/llm_wiki/cli/ops_cmds.py` | noted |
| STAB-011 | low | stability | `extract-claims` empty-envelope fallback when raw_path exists | `src/llm_wiki/cli/phase1_placeholders.py` | noted |
| STAB-012 | note | affected-flow | Phase 2 ingest behavior matrix verified | `src/llm_wiki/pipeline/{ingest,convert,hashing}.py` | noted (acceptance) |
| STAB-013 | note | security-config | No hardcoded secret/host/dependency; masking utilities in use | all Phase 2 source | pass (acceptance) |
| STAB-014 | note | affected-flow | Manual runners pass for Phase 1 + Phase 2 | `tests/run_phase{1,2}.py` | pass (acceptance) |
| STAB-015 | note | stability | Bootstrap seeds 6 confirmed prompts idempotently | `src/llm_wiki/bootstrap.py`, `src/llm_wiki/schema/prompts.py` | pass (acceptance) |

## Scope notes

| Item | Status | Resolution |
| --- | --- | --- |
| `.code-planner/04-check/recheck/phase-1-recheck-report.md` modified pre-Phase 2 | out-of-scope (decision) | see `phase-2-decision-request.md` |
| `.code-planner/01-ideation-*`, `.code-planner/02-planning/` untracked | out-of-scope (decision) | must not be staged into runtime commit |
| `testset/` untracked user input | untracked input | must not be staged; documented in evidence |

## User-test results

`check-user-test` returned `required`. Quality judgement for Korean summary / title / mapping quality and language policy needs human review. Live LLM parsing/schema stability improved to 10/10 on synthetic broad-topic Markdown, but user quality approval is still pending. See `.code-planner/04-check/phase-2-user-test-checklist.md`.
