# Phase 2 Search E2E Evidence

## Source phase and planning docs

- `.code-planner/04-check/phase-2-search-e2e-checklist.md`
- `.code-planner/03-build/phases/phase-2-execution-brief.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/phases/01-phase-plan.md` — Phase 2
- `.code-planner/02-planning/validation/01-validation-plan.md`

## Work units completed

- SEARCH-01: empty workspace search behavior.
- SEARCH-02: single Markdown FTS search.
- SEARCH-03: source-title/metadata fallback compatibility smoke.
- SEARCH-04: embed then combined FTS/vector search.
- SEARCH-05: 9-query multi-topic relevance smoke.
- SEARCH-06: Korean query and mixed Korean/English snippet behavior.
- SEARCH-07: `ask` now reuses search evidence refs.
- SEARCH-08: HTML conversion then search.
- SEARCH-09: PDF unsupported behavior confirmed.
- SEARCH-10: validate/lint/status after E2E.

## Files changed

```text
.code-planner/03-build/evidence/phase-2-search-e2e-evidence.md
src/llm_wiki/cli/ops_cmds.py
src/llm_wiki/cli/phase1_placeholders.py
tests/test_models_placeholders_ops.py
```

## Existing code discovery

- Reused existing `run_search` instead of duplicating query logic in `run_ask`.
- Reused existing `search_chunk_vectors` fallback-hash vector search path.
- Reused existing CLI parser/handler flow for E2E script to avoid shell-only false positives.
- Found and fixed an FTS5 natural-language query gap: a sentence query containing `?` could raise `sqlite3.OperationalError`; `run_search` now retries with a conservative quoted-token FTS5 query.

## Subagents used

- None for this narrow follow-up execution. Primary build agent ran checklist, integrated two small fixes, and performed validation.

## Commands run

```text
PYTHONPATH=src python3 - <<'PY'
# Search E2E runner using /tmp/opencode/phase2-search-e2e workspace.
# It executed SEARCH-01 through SEARCH-10 via llm_wiki.cli.build_parser handlers.
PY

PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m tests.run_phase1
PYTHONPATH=src python3 -m tests.run_phase2

PYTHONPATH=src python3 - <<'PY'
# Direct ask regression smoke using /tmp/opencode/phase2-ask-regression.
PY
```

## Validation results

### Search E2E summary

- Workspace: `/tmp/opencode/phase2-search-e2e/workspace`
- Report artifact: `/tmp/opencode/phase2-search-e2e/search-e2e-report.json`
- Result: `10 / 10` checklist items passed.

Representative final output:

```json
{
  "summary": {"passed": 10, "total": 10},
  "workspace": "/tmp/opencode/phase2-search-e2e/workspace"
}
```

### Result count per checklist

| Check | Result |
|---|---:|
| SEARCH-01 empty search | 0 results, vector `attempted: false`, reason `no_chunk_embeddings` |
| SEARCH-02 FTS `pipeline` | 2 results, top `match_type: fts` |
| SEARCH-03 `rag` | 1 result, `match_type: fts` |
| SEARCH-04 embed + `RAG` | vector attempted, 1 vector fallback hit merged with FTS |
| SEARCH-05 9 multi-topic queries | 8/9 top-result relevance smoke passed; threshold 8 |
| SEARCH-06 Korean queries | 4/4 returned results; threshold 3 |
| SEARCH-07 `ask` | exit `0`, `evidence_ref_count: 3` |
| SEARCH-08 HTML search | 6 results, top HTML-converted chunk for `token overhead` |
| SEARCH-09 PDF unsupported | ingest exit `2`, explicit unsupported message |
| SEARCH-10 validate/lint/status | validate `0`, lint `0`, status `0` |

### Vector metadata summary

```json
{
  "attempted": true,
  "match_type": "vector_hash_fallback",
  "dimension": 16,
  "model": "fallback-hash-v1",
  "backend": "fallback_hash",
  "candidate_count": 12,
  "result_count": 5
}
```

### `ask` evidence refs summary

- Before fix: `ask` did not reuse `run_search`; natural-language FTS query with `?` caused SEARCH-07 failure.
- After fix: `wiki ask "RAG에서 groundedness가 왜 중요한가?"` returned exit `0`, answer text, `evidence_ref_count: 3`, and `search_metadata.vector.attempted: true`.
- Direct regression smoke output:

```text
{'exit_code': 0, 'evidence_ref_count': 2, 'vector_attempted': True, 'first_match_type': 'vector_hash_fallback'}
```

### PDF unsupported behavior summary

- `wiki ingest testset/spacex.pdf --path <tmp> --json` returned exit `2`.
- Message: `PDF import requires Phase 2+ conversion support with optional dependency.`
- PDF content was not ingested; any `SpaceX` search hit came from temporary Markdown input, not the PDF.

### Regression validation

```text
PYTHONPATH=src python3 -m compileall -q src tests
=> pass

PYTHONPATH=src python3 -m tests.run_phase1
=> Ran 26 tests in 4.980s — OK

PYTHONPATH=src python3 -m tests.run_phase2
=> Ran 6 tests in 3.017s — OK
```

## Process/port cleanup

- No servers were started for Search E2E.
- Temporary workspaces are under `/tmp/opencode/phase2-search-e2e` and `/tmp/opencode/phase2-ask-regression`.

## Mockup alignment / user-visible verification

- UI/mockup scope not involved in this search E2E follow-up.
- User-visible CLI behavior verified for `search`, `ask`, `validate`, `lint`, and `status`.

## Remaining risks

- Fallback hash vector search is deterministic but not semantic-quality equivalent to a real embedding model.
- One multi-topic query (`Bond Duration`) had a non-relevant top vector fallback result; FTS still retrieved relevant results and the smoke threshold passed. Real embedding backend should improve ranking.
- Korean semantic queries without exact Korean text can return weak vector fallback matches.

## Ready for /check

true
