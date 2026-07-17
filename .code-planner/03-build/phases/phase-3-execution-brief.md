# Phase 3 Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-3-chunked-extraction.md`
- `.code-planner/02-planning/features/feature-chunked-extraction.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`

## Phase goal

큰 문서를 `parsed.text` truncate가 아니라 `ParsedDocument.chunks` 기반 chunk-level extraction map-reduce로 처리하여 context overflow를 방지하고, 뒤쪽 chunk의 entity/concept 후보를 보존한다.

## Work units

### WU-001. Existing extraction flow and worktree conflict discovery

- Purpose: 현재 `ingest_llm.py`, prompts, parser chunks, callbacks/jobs progress, tests, 그리고 남아 있는 2-pass/STAB worktree 변경의 Phase 3 재사용/충돌 가능성을 파악한다.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `src/llm_wiki/ingest_llm.py`, `src/llm_wiki/prompts.py`, `src/llm_wiki/parsers/base.py`, `src/llm_wiki/jobs.py`, tests.
- Completion criteria: target functions, current extraction schema, chunk availability, provider/context-overflow handling, conflict risks summarized.
- Verification: N/A read-only.

### WU-002. Chunk-level extraction and aggregation

- Purpose: chunk extraction prompt/schema, per-chunk result collection, aggregation/dedupe helper를 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/ingest_llm.py`, `src/llm_wiki/prompts.py`, focused tests.
- Completion criteria: large documents use `ParsedDocument.chunks`; candidates/summaries/key_takeaways collected; late chunk candidates preserved.
- Verification: targeted pytest with fake LLM client.

### WU-003. Context overflow fallback and progress events

- Purpose: context overflow 400 또는 length threshold에 따라 chunked fallback을 실행하고 chunk progress를 callbacks/jobs event에 기록한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/ingest_llm.py`, `src/llm_wiki/jobs.py` only if safe/minimal, tests.
- Completion criteria: small documents can remain single extraction; context overflow triggers chunked mode; chunk progress observable.
- Verification: targeted pytest simulating overflow.

### WU-004. Phase 3 validation and evidence readiness

- Purpose: Phase 3 validation plan에 맞춰 tests/commands를 실행하고 evidence를 작성한다.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-3-build-evidence.md`, tests if needed.
- Completion criteria: command output, validation result, scope notes, ready-for-check flag documented.
- Verification: real validation commands executed after implementation.

## Out of scope

- Raw file physical chunk split.
- Review workbench detailed UI/actions.
- `/ingest` template redesign.
- Full Inbox item → job source mapping if not already safe.
- qmd/Obsidian reset feature.

## Validation commands

- `.venv/bin/python -m pytest tests/test_chunked_extraction.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v`
- Existing focused tests discovered by WU-001.
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-3`: `feat: add chunked extraction`
- Current worktree already contains uncommitted 2-pass/STAB changes in `ingest_llm.py`, `prompts.py`, `llm.py`, and related tests. Phase 3 must either formally absorb the relevant subset into this phase with evidence, or stop before commit if safe separation is impossible.

## Risks

- `ingest_llm.py` already has large uncommitted changes; Phase 3 implementation may overlap and make clean commit separation difficult.
- LLM context overflow behavior is provider-specific; tests must use deterministic fake clients.
- Aggregation must not silently drop late-chunk candidates.
- Prompt/schema changes may interact with existing 2-pass generation and STAB tests.
