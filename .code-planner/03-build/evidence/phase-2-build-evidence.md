# Phase 2 Build Evidence

## Source phase and planning docs

- `.code-planner/03-build/phases/phase-2-execution-brief.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/phases/01-phase-plan.md` — Phase 2
- `.code-planner/02-planning/validation/01-validation-plan.md` — Phase 2 checks
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`

## Work units completed

- WU-001: existing code discovery and duplicate-risk scan.
- WU-002: candidate schema validator + review persistence.
- WU-003: default prompt versioning and Phase 2 language policy.
- WU-004: CLI quality command upgrade for `extract-claims`, `map`, `summarize`, `ask`, `compile`, candidate retry flow.
- WU-006: non-Markdown converter adapter without new mandatory dependency.
- WU-007: deterministic vector/RAG search over stored `embeddings.vector_json`.
- WU-008: `testset/` quality smoke via `tests/run_phase2.py`.

## Files changed

Phase 2 implementation/evidence files:

```text
.code-planner/03-build/phases/phase-2-execution-brief.md
.code-planner/03-build/evidence/phase-2-build-evidence.md
src/llm_wiki/bootstrap.py
src/llm_wiki/cli/ops_cmds.py
src/llm_wiki/cli/phase1_placeholders.py
src/llm_wiki/pipeline/__init__.py
src/llm_wiki/pipeline/convert.py
src/llm_wiki/pipeline/hashing.py
src/llm_wiki/pipeline/ingest.py
src/llm_wiki/quality.py
src/llm_wiki/schema/__init__.py
src/llm_wiki/schema/candidates.py
src/llm_wiki/schema/prompts.py
src/llm_wiki/schema/review.py
src/llm_wiki/search/__init__.py
src/llm_wiki/search/vector.py
tests/run_phase2.py
tests/test_converter_adapter.py
tests/test_phase2_schema_quality.py
tests/test_vector_search.py
```

Pre-existing/unrelated working tree items observed before Phase 2 code edits:

```text
M .code-planner/04-check/recheck/phase-1-recheck-report.md
?? .code-planner/01-ideation-approved.json
?? .code-planner/01-ideation-living-note.md
?? .code-planner/02-planning/
?? testset/
```

These are not claimed as Phase 2 implementation edits, except `testset/` is used as user-provided validation input.

## Existing code discovery

- Reused `jobs.record_artifact`, `create_job`, `create_agent_run`, `update_*` instead of creating duplicate job/artifact writers.
- Reused `db.schema.connect` and existing Phase 1 tables: `review_candidates`, `human_decisions`, `retry_instructions`, `prompt_versions`, `embeddings`.
- Reused `workspace.resolve_workspace`, `common.new_id`, `utc_now`, `relative_to`.
- Reused existing CLI command surfaces rather than adding duplicate commands.
- No new mandatory dependency was added.

## Subagents used

- `codebase-explorer`: Phase 2 target/discovery scan.
- `build-backend-script-dev`: WU-006 converter adapter.
- `build-core-dev`: WU-007 vector/RAG search.

Core quality policy, schema validator, prompt defaults, review persistence, and quality evaluator were directly integrated by the primary build agent per user request.

## Commands run

```text
git status --short && git log --oneline -5
git switch -c phase-2-llm-wiki-quality
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m tests.run_phase1
PYTHONPATH=src python3 - <<'PY' ... Phase 2 CLI smoke ... PY
PYTHONPATH=src python3 - <<'PY' ... HTML converter smoke ... PY
PYTHONPATH=src python3 - <<'PY' ... testset Markdown/PDF smoke ... PY
PYTHONPATH=src python3 -m tests.run_phase2
PYTHONPATH=src python3 -m tests.run_phase1 && PYTHONPATH=src python3 -m tests.run_phase2 && git diff --check && git status --short && git diff --stat
```

`pytest` was attempted for `tests/test_phase2_schema_quality.py`, but the environment returned `No module named pytest`. Phase 2 therefore adds `tests/run_phase2.py`, matching the Phase 1 stdlib validation pattern.

## Validation results

- `PYTHONPATH=src python3 -m compileall -q src tests`: pass.
- `PYTHONPATH=src python3 -m tests.run_phase1`: pass — `Ran 26 tests ... OK`.
- `PYTHONPATH=src python3 -m tests.run_phase2`: pass — `Ran 4 tests ... OK`.
- Phase 2 CLI smoke:
  - `init → ingest samples/rag.md → normalize → chunk → extract-claims → map → retry candidate → summarize → compile`: pass.
  - Extract validation: `validation.ok = true`, `candidate_count = 2`, quality overall score observed `0.7`.
  - Map validation: `validation.ok = true`, `mapping_quality = 1.0`.
  - Retry: target kind `candidate`, old candidate marked `superseded`, `superseded_by` populated.
- HTML conversion smoke: `.html` ingest succeeded as `converted_markdown`, normalize succeeded.
- `testset/` Markdown smoke:
  - `testset/AlexsJones-Ilmfit.md`: extract validation true, overall quality score observed `0.7`, mapping quality `1.0`.
  - `testset/OKF SPEC.md`: extract validation true, overall quality score observed `0.7`, mapping quality `1.0`.
  - `testset/systima-claude-code-vs-opencode-token-overhead.md`: extract validation true, overall quality score observed `0.8`, mapping quality `1.0`.
- `testset/` PDF smoke:
  - `testset/spacex.pdf`: exit `2`, explicit unsupported optional dependency message.
  - `testset/SpaceX 서플라이 체인 산업분석.pdf`: exit `2`, explicit unsupported optional dependency message.
  - `testset/palantir-vs-classic-ontology.pdf`: exit `2`, explicit unsupported optional dependency message.
- `git diff --check`: pass.

## Process/port cleanup

- No persistent server/process was started by the primary build validation.
- Subagent vector/converter tests used no persistent process.

## Mockup alignment / user-visible verification

- Phase 2 is not a Web UI/mockup phase.
- User-visible CLI behavior now includes schema-bound candidate output, Korean-centered summaries/reasons with English technical/proper nouns preserved, and candidate retry superseding.

## Quality policy evidence

- Language policy implemented in `src/llm_wiki/schema/prompts.py` and checked in `src/llm_wiki/quality.py`.
- `tags` are explicitly rejected by `validate_candidate_envelope`; title/wiki mapping must use `node_candidates` and `mapping_candidates` within `candidate.v1`.
- Gold labels were not found under `testset/`; quality smoke is rubric-based and records `gold_available: false`.

## Remaining risks

- PDF/Office conversion is not fully implemented because no new mandatory dependency was approved. Current behavior is explicit failure with artifact/CLI guidance.
- LLM quality is deterministic/local heuristic in this pass; live model prompt execution is not yet fully wired into every task.
- `pytest` is unavailable in the current environment; stdlib runners pass.
- Existing working tree includes pre-existing/unrelated `.code-planner/04-check/recheck/phase-1-recheck-report.md` modification and untracked planning/testset files.

## Ready for /check

false

Reason: Phase 2 core quality/schema/testset scaffold is implemented and validated, but live LLM prompt execution and full PDF/Office conversion remain partial/blocked by dependency policy. A follow-up Phase 2 build pass should wire live LLM JSON task execution before final `/check phase-2`.
