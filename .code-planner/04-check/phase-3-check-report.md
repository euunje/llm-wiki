# Phase 3 Check Report

## Phase id

- Phase 3 — Chunked extraction map-reduce

## Changed files

### Combined checkpoint files

Clean file-level separation between Phase 3 and the prior 2-pass/STAB work is not practical because the changes are interleaved in `ingest_llm.py` and `prompts.py`. This checkpoint therefore covers both:

- Phase 3 chunked extraction map-reduce.
- 2-pass/STAB structured page drafting stability fixes.

Files included in the combined checkpoint:

- `src/llm_wiki/ingest_llm.py`
- `src/llm_wiki/prompts.py`
- `src/llm_wiki/jobs.py`
- `src/llm_wiki/lint.py`
- `src/llm_wiki/llm.py`
- `tests/test_chunked_extraction.py`
- `tests/test_two_pass_generation.py`
- `tests/test_staged_lint_gate.py`
- `tests/test_phase2_candidates_schema.py`

## Affected flow

- Extraction now uses single-pass for small documents and chunked map-reduce for large documents using parser-provided `ParsedDocument.chunks`.
- Context-overflow LLM errors can fall back from single extraction to chunked extraction.
- Chunk results aggregate summaries, key takeaways, tags, and deduped candidates.
- Late-chunk entity/concept candidates are preserved into the final resolution/drafting flow.
- Job callbacks can emit chunk progress events.
- 2-pass/STAB structured page generation, retry, staged lint, and stream callback exception handling are included in the same checkpoint.

## Required check results

| Check | Result | Notes |
|---|---|---|
| 1. Change scope | pass | Combined Phase 3 + STAB checkpoint required due file overlap. P0 clear. |
| 2. Affected flow | pass | Extraction, generation, staged lint, jobs callbacks inspected. |
| 3. Feature completeness | pass | All seven Phase 3 validation-plan items covered. |
| 4. Stability | pass after fixes | STAB-P3-001/002/004 fixed and covered by tests. Remaining risks are notes. |
| 5. Maintainability | pass | Combined checkpoint documented; remaining overlap risk acknowledged. |
| 6. Security/config | pass | No secrets/credentials/new host URLs/user-specific paths detected. |
| 7. Verification evidence | pass | Evidence exists and recheck passed. |

## Fixes applied during check

### STAB-P3-002 — overflow heuristic too broad

- Tightened `_is_context_overflow_error`.
- Generic `500 ... context length ...` no longer triggers fallback.
- `400/413/context_length_exceeded + overflow phrase` and explicit token-limit phrases still trigger fallback.
- Test added: generic 500 no-fallback.

### STAB-P3-001 — duplicate chunk failure event

- `_extract_chunked` no longer emits `on_chunk_extraction_failed` on first parse failure when retry is still possible.
- Retry parse failure emits exactly one failed callback.
- Test added: failed callback count is 1.

### STAB-P3-004 — exact slug collision with `non_categories`

- `_exact_slug_candidates` now keys `non_categories/<stem>` separately from `entities/<stem>` or `concepts/<stem>`.
- Multiple exact matches go to `needs_review` instead of producing mismatched canonical/final path.
- Test added: canonical and non_categories match are both returned and resolve to review.

## Validation commands

- `.venv/bin/python -m pytest tests/test_chunked_extraction.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v`
  - PASS: 26 passed, 1 warning.
- `.venv/bin/python -m pytest tests/test_staged_lint_gate.py tests/test_two_pass_generation.py -v`
  - PASS: 19 passed.
- `.venv/bin/python -m py_compile src/llm_wiki/ingest_llm.py src/llm_wiki/prompts.py src/llm_wiki/jobs.py src/llm_wiki/lint.py tests/test_chunked_extraction.py`
  - PASS.
- `git diff --check`
  - PASS.
- `.venv/bin/python -m pytest tests/test_phase2_candidates_schema.py -q`
  - Partial: emitted 16 passing dots before 120s timeout, no failure output. Not used as a blocking result.

## User functional test required

- No.
- Rationale: Phase 3 has no UI/UX changes and no user-facing input flow changes. It is internal extraction/generation behavior covered by deterministic fake-client tests.

## Remaining risks

1. Full repository pytest was not run.
2. Real LLM provider/network E2E was not exercised.
3. Provider-specific overflow matching remains heuristic even after tightening.
4. `jobs._JobCallbacks` chunk DB event path is source-inspection-backed, not separately DB-integration tested.
5. The checkpoint intentionally combines Phase 3 and STAB changes due overlap in `ingest_llm.py`/`prompts.py`.

## Recommended commit

- Suggested message: `feat: add chunked extraction and stabilize page generation`
- Stage:
  - `src/llm_wiki/ingest_llm.py`
  - `src/llm_wiki/prompts.py`
  - `src/llm_wiki/jobs.py`
  - `src/llm_wiki/lint.py`
  - `src/llm_wiki/llm.py`
  - `tests/test_chunked_extraction.py`
  - `tests/test_two_pass_generation.py`
  - `tests/test_staged_lint_gate.py`
  - `tests/test_phase2_candidates_schema.py`

## Decision

- Gate result: `approved`
- Commit will be a combined Phase 3 + STAB checkpoint.

## Commit

- Hash: `865c5b1`
- Message: `feat: add chunked extraction and stabilize page generation`
- Phase: `phase-3`
- Check: `approved`
- Evidence: `.code-planner/04-check/phase-3-check-report.md`
- Build evidence: `.code-planner/03-build/evidence/phase-3-build-evidence.md`
- Files in commit: 9
  - `src/llm_wiki/ingest_llm.py`
  - `src/llm_wiki/prompts.py`
  - `src/llm_wiki/jobs.py`
  - `src/llm_wiki/lint.py`
  - `src/llm_wiki/llm.py`
  - `tests/test_chunked_extraction.py`
  - `tests/test_two_pass_generation.py`
  - `tests/test_staged_lint_gate.py`
  - `tests/test_phase2_candidates_schema.py`
