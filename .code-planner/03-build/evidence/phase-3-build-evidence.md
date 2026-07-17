# Phase 3 Build Evidence

## Work unit

- `P3-WU-004` — Phase 3 validation and evidence readiness
- `P3-WU-004-RECHECK` — Phase 3 revalidation after stability fixes (this update)
- Assigned agent: `build-test-validation`
- Phase 3 — Chunked extraction, context-overflow fallback, aggregation, and progress events
- Source planning docs:
  - `.code-planner/02-planning/validation/01-validation-plan.md` (Phase 3)
  - `.code-planner/03-build/phases/phase-3-execution-brief.md`

## RECHECK summary (P3-WU-004-RECHECK)

Three stability fixes were applied to the Phase 3 implementation and covered by
additional tests in `tests/test_chunked_extraction.py`:

1. **`_is_context_overflow_error` tightened.** A generic `500` containing the
   phrase `context length` no longer triggers the chunked fallback. Only
   explicit context-overflow phrases (`prompt greater than context length`,
   `context length`, `maximum context length`, `context window`) AND a status
   / explicit marker (`400`, `413`, `context_length_exceeded`,
   `context_length_exceed`), or an explicit token marker (`too many tokens`,
   `token limit`, `maximum token`), now match.
   - New test: `test_generic_500_context_length_error_does_not_fall_back_to_chunked`
     verifies the tightened behaviour.
2. **`_extract_chunked` no longer double-emits `chunk_extraction_failed`.** A
   single `failure_reported` guard prevents the inner retry-parse failure
   path from raising a duplicate callback before the outer `LLMError/ValueError`
   handler reports it.
   - New test: `test_chunk_retry_parse_failure_emits_failed_callback_once`
     asserts exactly one `(chunk_index, total_chunks, ...)` callback when both
     the initial parse and the retry parse fail.
3. **`_exact_slug_candidates` distinguishes non_categories exact matches from
   canonical entity/concept matches.** The non_categories directory is still
   scanned, but its matches are emitted under a `non_categories/<slug>` key so
   the resolution flow sees both kinds side-by-side and chooses
   `needs_review` (or canonical `entities/<slug>`) instead of silently
   merging into the non_categories page.
   - New test: `test_exact_slug_candidates_distinguish_non_categories_from_entities`
     verifies the two matches are returned and `_resolve_slug` returns
     `needs_review` with canonical slug `entities/openai`.

The recheck added three new tests to `tests/test_chunked_extraction.py`. Total
file size went from 4 to 7 focused tests. The full focused/InBox suite
expanded from 23 to 26 passing tests.

## Phase 3 scope validated

The implementation under validation provides:

- single-pass extraction for documents within the configured source-character budget;
- chunk-level extraction from `ParsedDocument.chunks` for documents over that budget;
- context-overflow fallback from single-pass extraction to chunk-level extraction;
- per-chunk `ChunkExtraction` parsing, retry, collection, and aggregation;
- candidate deduplication/merge, summary and key-takeaway aggregation, and late-chunk candidate preservation;
- chunk progress callbacks and job-event emission through `jobs._JobCallbacks`.

**Explicit non-claim:** this phase does not physically split raw files into chunk files. The tested path consumes parser-provided `ParsedDocument.chunks`; no raw physical chunk splitting is claimed or validated.

## Validation-plan results

| Phase 3 validation item | Result | Evidence |
| --- | --- | --- |
| Small documents can use single extraction | PASS | `tests/test_chunked_extraction.py::test_small_document_still_uses_single_extraction` — one single extraction call, no chunk calls or chunk-start callbacks. |
| Large documents use `ParsedDocument.chunks` | PASS | `test_large_document_uses_chunks_and_preserves_late_candidate` — fake parsed document supplies two chunks; no single extraction call and chunk calls are `[0, 1]`. |
| Context overflow 400 triggers chunked fallback | PASS | `test_context_overflow_in_single_extraction_falls_back_to_chunked` — first single extraction raises `LLMError("...400...context length")`; both parser chunks are then extracted. |
| Generic 500 with "context length" text does **not** trigger fallback | PASS (post-fix) | `test_generic_500_context_length_error_does_not_fall_back_to_chunked` — first single extraction raises `LLMError("server error 500: context length metadata unavailable")`; result is a surfaced `LLM error`, `chunk_calls == []`. |
| Chunk retry parse failure emits `chunk_extraction_failed` exactly once | PASS (post-fix) | `test_chunk_retry_parse_failure_emits_failed_callback_once` — both initial parse and retry parse raise `ValueError`; `callbacks.chunk_failed` has length 1 and the entry is `(0, 1, ...)`. |
| Non_categories exact slug matches are distinguished from canonical matches | PASS (post-fix) | `test_exact_slug_candidates_distinguish_non_categories_from_entities` — with `entities/openai.md` and `non_categories/openai.md`, `_exact_slug_candidates` returns both keys; `_resolve_slug` returns `action == "needs_review"` with `canonical_slug == "entities/openai"`. |
| Per-chunk candidates, summaries, and key takeaways are collected | PASS | Large-document test verifies candidates from both chunks reach the result; aggregation test verifies ordered summaries and deduplicated takeaways. |
| Chunk extraction progress is observable in callbacks/jobs events | PASS with coverage note | Runtime focused test verifies `on_chunk_extracting` and `on_chunk_extracted` for both chunks. Source inspection of `jobs._JobCallbacks` confirms `chunk_extracting`, `chunk_extracted`, and `chunk_extraction_failed` events plus progress updates are written through the existing job event helpers. There is no separate dedicated `jobs._JobCallbacks` database integration test in the assigned command set. |
| Aggregation/dedupe connects to existing resolution flow | PASS | `test_large_document_uses_chunks_and_preserves_late_candidate` verifies both `openai` and the late `map-reduce` candidate appear in `result.changes`; the aggregation unit test verifies slug dedupe, longer-description selection, confidence merge, summaries, takeaways, and tags. |
| Late-document entities/concepts are not dropped | PASS | The late chunk's `map-reduce` concept is present in the final change set. |

## Files reviewed and scope separation

### Phase 3 implementation/test files reviewed

- `src/llm_wiki/ingest_llm.py` — `ChunkExtraction`, chunk parsing, aggregation/dedupe, threshold selection, chunked extraction, overflow fallback (now tightened), retry-parse single-failure callback, and `_exact_slug_candidates` non_categories vs canonical distinction.
- `src/llm_wiki/prompts.py` — chunk extraction schema/instructions and chunk retry prompt builders.
- `src/llm_wiki/jobs.py` — chunk progress callbacks and job-event payloads.
- `src/llm_wiki/lint.py` — read for compile-only sanity; no Phase 3 behavioural change claim.
- `tests/test_chunked_extraction.py` — seven focused deterministic fake-client tests (4 original + 3 new stability-fix coverage tests).

The validator did not modify any source or test file in either the original validation or the RECHECK.

### Worktree overlap / separation note

Clean file-level separation from the earlier 2-pass/STAB work is not possible in the current uncommitted worktree:

- `src/llm_wiki/ingest_llm.py` contains both the earlier 2-pass/STAB implementation and the Phase 3 chunked extraction changes (`git diff --numstat`: `1059` insertions, `188` deletions in the current worktree diff).
- `src/llm_wiki/prompts.py` contains both existing page-generation/retry prompt changes and the Phase 3 chunk prompt additions (`333` insertions in the current worktree diff).
- `src/llm_wiki/jobs.py` is the Phase 3 progress-event change (`36` insertions in the current worktree diff).
- `tests/test_chunked_extraction.py` is the Phase 3 focused test file.
- Other current worktree changes are outside this validation unit: `src/llm_wiki/lint.py`, `src/llm_wiki/llm.py`, `tests/test_phase2_candidates_schema.py`, and the STAB regression test files. They were not modified or reassigned by this validator.

The targeted STAB suite was run separately below to detect interaction regressions; its passing result does not reclassify those changes as Phase 3 deliverables.

## Commands run and results

All commands were executed from `/home/eunjae/projects/llm-wiki` using the project virtual environment. No secrets or environment files were read or modified.

### Original validation (P3-WU-004)

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_chunked_extraction.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **PASS — 23 passed, 1 Starlette/httpx deprecation warning, 5.02s.** The four Phase 3 tests and the Phase 1/2 Inbox regression tests are green. |
| `.venv/bin/python -m py_compile src/llm_wiki/ingest_llm.py src/llm_wiki/prompts.py src/llm_wiki/jobs.py tests/test_chunked_extraction.py` | **PASS — exit 0, no output.** All assigned Phase 3 source/test files compile. |
| `git diff --check` | **PASS — exit 0, no output.** No whitespace errors. |
| `.venv/bin/python -m pytest tests/test_staged_lint_gate.py tests/test_two_pass_generation.py -v` | **PASS — 19 passed in 2.22s.** Targeted STAB-001/002/003 and two-pass regression coverage passed after the Phase 3 changes. |
| `git status --short && git diff --stat` | **Evidence captured.** The worktree contains the Phase 3 files plus pre-existing/parallel Phase 2 and STAB changes; see scope separation above. |
| `ss -ltnp` | **Cleanup check completed.** Existing unrelated listeners were observed; this validation run did not start a server, watcher, or listener. |

### RECHECK validation (P3-WU-004-RECHECK)

The validator re-ran the same scope against the post-fix code; `tests/test_chunked_extraction.py` now contains 7 focused tests (3 new). All commands returned successfully; no source or test file was modified.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_chunked_extraction.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v` | **PASS — 26 passed, 1 Starlette/httpx deprecation warning, 5.12s.** The 7 focused Phase 3 tests (4 original + 3 new coverage tests for the stability fixes) and the Phase 1/2 Inbox regression tests are green. |
| `.venv/bin/python -m pytest tests/test_staged_lint_gate.py tests/test_two_pass_generation.py -v` | **PASS — 19 passed in 2.25s.** Targeted STAB-001/002/003 and two-pass regression coverage remained green after the Phase 3 stability fixes. |
| `.venv/bin/python -m py_compile src/llm_wiki/ingest_llm.py src/llm_wiki/prompts.py src/llm_wiki/jobs.py src/llm_wiki/lint.py tests/test_chunked_extraction.py` | **PASS — exit 0, no output.** All assigned Phase 3 source/test files (including `lint.py`) compile after the fixes. |
| `git diff --check` | **PASS — exit 0, no output.** No whitespace errors in the current worktree diff. |
| `git status --short && git diff --stat` | **Evidence captured.** Working tree now shows: 6 modified files (`ingest_llm.py`, `jobs.py`, `lint.py`, `llm.py`, `prompts.py`, `tests/test_phase2_candidates_schema.py`); 3 new files (`tests/test_chunked_extraction.py`, `tests/test_staged_lint_gate.py`, `tests/test_two_pass_generation.py`); and untracked `.code-planner/` and `.prv/`. The validator did not modify any source or test file. |
| `ss -ltnp` | **Cleanup check completed.** Existing unrelated listeners (Syncthing, OpenCode, SSH, and an existing Python listener on port 8776) were observed; this validation run did not start a server, watcher, or listener. |

### Test warning

The focused Phase 3/InBox run emitted one pre-existing dependency warning from `fastapi.testclient`/Starlette about the `httpx2` transition. It did not fail a test and is not a Phase 3 implementation failure.

## User-facing validation items

- A document that fits the configured budget remains on the existing single-extraction path.
- A large document is processed through parser-provided chunks, with each chunk's candidates and supporting extraction data contributing to the final extraction.
- A provider context-overflow error containing the tested 400/context-length signal falls back to chunk extraction instead of failing immediately.
- Chunk progress is exposed as extracting/extracted/failed job events with chunk index and total-chunk data, and progress advances during chunk processing.
- Candidates found only in later chunks remain in the final resolution changes; the focused test specifically retains `map-reduce` from chunk 1.
- No claim is made that raw source files are physically split or rewritten into chunk files.

## Process / port cleanup

- No dev server, watcher, background test process, or port listener was started by this validation.
- `pytest` runs completed synchronously and exited normally.
- The `ss -ltnp` check showed pre-existing listeners (including Syncthing, OpenCode, SSH, and an existing Python listener); none was created by this work unit and none was stopped or modified.
- No cleanup action was required.

## Remaining risks and limitations

1. **Full-tree pytest was not run.** The assigned scoped suite and targeted STAB regression suite passed, but this evidence does not claim a clean full repository test run.
2. **Job callback integration coverage is source-inspection-backed.** The focused test exercises the generic ingest callback hooks; it does not instantiate `_JobCallbacks` against a real `job_events` row. The implementation inspection confirms the event names/payloads and progress update path.
3. **Provider-specific overflow matching remains heuristic.** `_is_context_overflow_error` now requires an overflow phrase (`prompt greater than context length`, `context length`, `maximum context length`, `context window`) AND a status/explicit marker (`400`, `413`, `context_length_exceeded`, `context_length_exceed`), OR an explicit token marker (`too many tokens`, `token limit`, `maximum token`). This rejects generic `500: ... context length ...` text while still matching known provider wording, but exotic provider phrasings may still slip through or get falsely rejected.
4. **Worktree commit separation remains a build-primary concern.** Phase 3 changes overlap the earlier 2-pass/STAB changes in `ingest_llm.py` and `prompts.py`; the intended Phase 3 checkpoint must stage only the appropriate Phase 3 subset after the primary resolves the overlap.
5. **The full Phase 3 end-to-end path with a real LLM provider was not exercised.** Tests use deterministic fake clients as required for stable validation; provider/network behavior remains outside this run.

## Validation result

### Original (P3-WU-004)

- **Phase 3 scoped validation: PASS.** All seven Phase 3 validation-plan items had passing focused evidence, with the job-event item explicitly supported by runtime callback evidence plus implementation inspection.
- **Targeted STAB regression validation: PASS.** 19/19 tests passed.
- `py_compile` and `git diff --check`: PASS.

### RECHECK (P3-WU-004-RECHECK)

- **Phase 3 scoped validation: PASS.** All Phase 3 validation-plan items now have passing focused evidence including the three new stability-fix tests. The tightened `_is_context_overflow_error` (`test_generic_500_context_length_error_does_not_fall_back_to_chunked`), the single-shot `_extract_chunked` retry-parse failure callback (`test_chunk_retry_parse_failure_emits_failed_callback_once`), and the `_exact_slug_candidates` non_categories vs canonical distinction (`test_exact_slug_candidates_distinguish_non_categories_from_entities`) all behave as the fix summary described.
- **Targeted STAB regression validation: PASS.** 19/19 tests still passed.
- **Inbox regression suite: PASS.** 4 `test_inbox_domain.py` + 15 `test_inbox_registration.py` tests remain green.
- `py_compile` and `git diff --check`: PASS.

## Ready for `/check`

- **true** for `/check phase-3` when scoped to the Phase 3 deliverables and the documented worktree-overlap/coverage caveats above.
- This is not a claim that the full repository suite is green or that Phase 3 changes are already cleanly separable into a commit.

## Evidence artifact

- `.code-planner/03-build/evidence/phase-3-build-evidence.md` (this file)
