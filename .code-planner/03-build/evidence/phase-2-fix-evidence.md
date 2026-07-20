# Phase 2 Fix Evidence

## Source fix request

- `.code-planner/04-check/fix-requests/phase-2-fix-request.md`
- User follow-up: fix all four medium issues and run repeated real LLM connection/JSON parsing tests.

## Fixed items

### STAB-001 — Conversion failure artifacts

- `src/llm_wiki/pipeline/ingest.py` now records `ingest_conversion_error` artifacts before raising on URL unsupported and HTML conversion failure.
- URL artifact avoids persisting raw URL content and records `type: url_unsupported`.
- `tests/run_phase2.py::test_url_ingest_records_failure_artifact` verifies artifact creation.

### STAB-002 — Retry consumed run tracking

- `src/llm_wiki/cli/ops_cmds.py` now creates a follow-up `agent_runs` row for candidate retry and passes its id as `consumed_run_id` to `supersede_candidate`.
- `src/llm_wiki/schema/review.py::supersede_candidate` now documents its audit behavior.
- `tests/run_phase2.py::test_extract_map_retry_summary_compile_flow` verifies `retry_instructions.consumed_run_id` equals the CLI payload `consumed_run_id`.

### STAB-003 — Recursive forbidden-key validation

- `src/llm_wiki/schema/candidates.py` now recursively scans the full candidate envelope for forbidden LLM-output keys (`human_decision`, `retry_instruction`, `approved`, `rejected`, `replaced`).
- `tests/run_phase2.py::test_candidate_schema_rejects_nested_forbidden_metadata` verifies a nested `subject_ref.human_decision` is rejected.

### STAB-004 — Module docstrings

- Added Phase 2 module docstrings to:
  - `src/llm_wiki/schema/candidates.py`
  - `src/llm_wiki/schema/review.py`
  - `src/llm_wiki/schema/prompts.py`
  - `src/llm_wiki/quality.py`
  - `src/llm_wiki/search/vector.py`
  - `src/llm_wiki/search/__init__.py`
  - `src/llm_wiki/llm/chat.py`
- Direct recheck found the first `src/llm_wiki/search/__init__.py` docstring was placed after imports, so `llm_wiki.search.__doc__` was `None`. The docstring was moved to the first statement and verified with `PYTHONPATH=src python3 -c "import llm_wiki.search; assert llm_wiki.search.__doc__"`.

## Live LLM JSON parsing hardening

- Added `src/llm_wiki/llm/chat.py`:
  - OpenAI-compatible chat JSON call helper.
  - JSON extraction from plain text or fenced markdown.
  - Safe fallback endpoint path candidates including `/v1/chat/completions` when the base endpoint returns `Unexpected endpoint`.
  - Lenient parse retry for common trailing commas; schema validation remains strict.
- Added `wiki extract-claims --llm` CLI option.
- Tightened LLM prompt in `run_extract_claims`:
  - exact `candidate.v1` skeleton.
  - exactly one claim and one node for smoke stability.
  - relation/mapping/conflict arrays empty in this extraction smoke.
  - explicit Korean explanation + English technical/proper noun preservation.

## Commands run

```text
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m tests.run_phase1
PYTHONPATH=src python3 -m tests.run_phase2
git diff --check
```

Results:

- `compileall`: pass.
- `tests.run_phase1`: pass — 26 tests OK.
- `tests.run_phase2`: pass — 6 tests OK.
- `git diff --check`: pass.
- Direct docstring check: `import llm_wiki.search; assert llm_wiki.search.__doc__` pass.

## Live LLM repeated tests

Secrets were loaded into subprocess environment only via `.env`; secret values were not printed.

### First run before prompt/path hardening

- 3 runs on `samples/rag.md`: LLM status failed because endpoint returned non-OpenAI `{"error":"Unexpected endpoint or method. (POST /chat/completions)"}` shape.
- `models test` returned HTTP OK because it only checked status code, not task JSON body.

### After endpoint fallback hardening

- 3 runs on `samples/short-note.md` with 60s timeout:
  - LLM JSON parsing succeeded, but schema validation failed because model output used wrong schema names/version.
  - Representative errors: `schema_version` was `1.0`, invalid `candidate_key`, missing `review_route`, missing `statement`, missing `claim_relation_type`, missing refs/evidence chunk.

### After strict schema skeleton prompt

- 3 runs on `samples/short-note.md`:
  - `llm_status: parsed`
  - `validation_ok: true`
  - `error_count: 0`
  - `candidate_count: 4`
  - `quality_score: 0.7`

### Long `testset/` Markdown parsing

- Initial 2-run test on `testset/systima-claude-code-vs-opencode-token-overhead.md`:
  - one run failed with malformed/trailing JSON style parse error.
  - one run succeeded with schema validation true.
- Added lenient trailing-comma parse retry and reduced source text window.
- 3-run test still had one `Unterminated string` due long output/truncation.
- Added prompt constraint: exactly one claim and one node, relation/mapping/conflict empty.
- Final 3-run test on the same long testset Markdown:
  - run 1: `llm_status: parsed`, `validation_ok: true`, `error_count: 0`, `candidate_count: 2`, `quality_score: 0.7`
  - run 2: `llm_status: parsed`, `validation_ok: true`, `error_count: 0`, `candidate_count: 2`, `quality_score: 0.7`
  - run 3: `llm_status: parsed`, `validation_ok: true`, `error_count: 0`, `candidate_count: 2`, `quality_score: 0.7`

### 10-topic synthetic Markdown live LLM test

User requested an additional broad-topic test with approximately 10 Markdown inputs covering finance, AI, Python, Claude, GPT, ontology, and supply chain topics.

Temporary Markdown files were generated under `/tmp/opencode` only and were not added to the repository. Each file was ingested, normalized, chunked, and processed with `wiki extract-claims --llm` against the real configured LLM endpoint. Secret values were loaded into subprocess environment only and were not printed.

| Topic file | LLM parse | Schema | Candidate count | Quality score | Title |
|---|---:|---:|---:|---:|---|
| `finance-bond-duration.md` | parsed | true | 2 | 0.8 | `Bond Duration` |
| `finance-defi-liquidity.md` | parsed | true | 2 | 0.7 | `DeFi Liquidity Pool` |
| `ai-rag-evaluation.md` | parsed | true | 2 | 0.7 | `RAG Evaluation` |
| `ai-embedding-drift.md` | parsed | true | 2 | 0.7 | `Embedding Drift` |
| `python-asyncio.md` | parsed | true | 2 | 0.7 | `Python asyncio TaskGroup` |
| `python-packaging.md` | parsed | true | 2 | 0.7 | `pyproject.toml` |
| `claude-code-workflow.md` | parsed | true | 2 | 0.7 | `Claude Code` |
| `gpt-tool-calling.md` | parsed | true | 2 | 0.7 | `GPT Tool Calling` |
| `ontology-palantir.md` | parsed | true | 2 | 0.7 | `Palantir Ontology` |
| `supply-chain-spacex.md` | parsed | true | 2 | 0.7 | `SpaceX의 생산 전략` |

Summary: `total=10`, `parsed_and_schema_ok=10`, `failed=0`.

Observation: parsing and schema compliance are stable across all 10 topics. The automatic language-policy score was `1.0` for one file and `0.5` for nine files because the heuristic expects all extracted English terms to appear in the combined candidate text. This is a quality-review signal, not a schema/parsing failure. Titles generally preserved technical/proper nouns; some aliases duplicated titles, and Korean naturalness still requires user review.

## Remaining risks

- Live LLM output quality still requires user review for Korean naturalness, title specificity, and mapping usefulness.
- `extract-claims --llm` is now stable for schema smoke, but it intentionally limits live extraction to one claim and one node for parse stability.
- Full PDF/Office conversion remains unsupported without optional dependency approval.
- Low-severity check notes STAB-005..STAB-011 remain for future cleanup unless the next check requires them.

## Ready for recheck

true
