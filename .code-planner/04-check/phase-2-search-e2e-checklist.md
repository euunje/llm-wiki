# Phase 2 Search E2E Checklist

## Purpose

Phase 1 CLI 구현 당시 데이터 부족으로 검색 기능의 실제 E2E 검증이 제한적이었다. Phase 2에서 `testset/`과 추가 Markdown 데이터를 사용해 FTS, metadata fallback, vector/RAG search, `ask` evidence 흐름을 실제 데이터 기준으로 점검한다.

## Current known coverage

- Phase 1 evidence:
  - `wiki search pipeline` smoke: 2 FTS results.
  - `tests.run_phase1`: `test_status_search_validate_lint_smoke` covers FTS search after ingest/normalize/chunk.
- Phase 2 evidence:
  - `tests/test_vector_search.py`: vector metadata and vector result smoke exists.
  - `tests.run_phase2`: quality/schema/HTML/testset smoke exists, but search-specific E2E is not broad enough.

## Gap

The following are not yet sufficiently proven by E2E:

- Multi-document search relevance across varied topics.
- No-data search behavior.
- FTS + vector combined output on real ingested/embedded documents.
- `ask` evidence refs using retrieved context.
- Korean query + English technical term query behavior.
- Search behavior after non-Markdown/HTML conversion.

## Test data

Use temporary workspace only. Do not modify or commit `testset/`.

Recommended inputs:

- `samples/rag.md`
- `samples/short-note.md`
- `testset/AlexsJones-Ilmfit.md`
- `testset/OKF SPEC.md`
- `testset/systima-claude-code-vs-opencode-token-overhead.md`
- temporary Markdown topics:
  - finance bond duration
  - DeFi liquidity pool
  - RAG evaluation
  - Python asyncio
  - Claude Code workflow
  - GPT tool calling
  - Palantir ontology
  - SpaceX supply chain

PDFs in `testset/` should be checked for explicit unsupported/error artifact unless optional conversion dependency is approved.

## E2E checklist

### SEARCH-01. Empty workspace search

Command:

```text
wiki init --path <tmp>
wiki search "RAG" --path <tmp> --json
```

Expected:

- exit code `0`
- `status: ok`
- `results: []`
- vector metadata indicates no embeddings, e.g. `attempted: false` or `reason: no_chunk_embeddings`
- no crash, no traceback

### SEARCH-02. Single Markdown FTS search

Command:

```text
wiki ingest samples/rag.md --path <tmp> --json
wiki normalize <source_id> --path <tmp> --json
wiki chunk <source_id> --path <tmp> --json
wiki search "pipeline" --path <tmp> --json
```

Expected:

- at least one result
- at least one `match_type: fts`
- result has `target_type: chunk`, `target_id`, `source_id`, `snippet`
- snippet includes or highlights query-related text

### SEARCH-03. Metadata fallback search

Command:

```text
wiki search "<source title term>" --path <tmp> --json
```

Expected:

- if FTS returns no rows, metadata fallback can return `target_type: source`
- result includes `title` and `match_type: metadata`

### SEARCH-04. Embedding then vector search

Command:

```text
wiki embed source:<source_id> --path <tmp> --json
wiki search "RAG" --path <tmp> --json
```

Expected:

- `metadata.vector` exists
- if embeddings exist: `metadata.vector.attempted: true`
- at least one result has `match_type` starting with `vector_`
- vector result includes `score`, `vector_model`, `vector_backend`
- FTS results are not duplicated by same chunk id

### SEARCH-05. Multi-topic relevance smoke

Ingest/normalize/chunk/embed 8~10 topic Markdown files.

Queries:

```text
wiki search "Bond Duration"
wiki search "DeFi liquidity"
wiki search "RAG evaluation"
wiki search "Embedding Drift"
wiki search "Python asyncio"
wiki search "Claude Code"
wiki search "GPT tool calling"
wiki search "Palantir Ontology"
wiki search "SpaceX supply chain"
```

Expected:

- each query returns at least one relevant source/chunk
- top result should be from the matching topic or clearly related topic
- English technical/proper nouns remain visible in title/snippet
- Korean queries should still retrieve related mixed-language content where present

### SEARCH-06. Korean query + English technical term preservation

Queries:

```text
wiki search "금리 리스크"
wiki search "토큰 오버헤드"
wiki search "검색 근거"
wiki search "공급망 병목"
```

Expected:

- Korean query finds Korean text where it exists
- returned snippets preserve English terms such as `LLM`, `RAG`, `token overhead`, `SpaceX`

### SEARCH-07. `ask` evidence refs

Command:

```text
wiki ask "RAG에서 groundedness가 왜 중요한가?" --path <tmp> --json
```

Expected:

- exit code `0`
- answer text exists
- `evidence_refs` is present
- when searchable chunks exist, evidence refs include source/chunk/snippet references
- answer uses Korean-centered explanation with English technical terms preserved

### SEARCH-08. Search after HTML conversion

Create temporary HTML:

```html
<h1>RAG와 LLM token overhead</h1>
<p>이 문서는 RAG pipeline과 LLM token overhead를 비교한다.</p>
```

Command:

```text
wiki ingest input.html --path <tmp> --json
wiki normalize <source_id> --path <tmp> --json
wiki chunk <source_id> --path <tmp> --json
wiki search "token overhead" --path <tmp> --json
```

Expected:

- HTML ingest succeeds as converted Markdown
- search returns the converted content
- snippet preserves `RAG`, `LLM`, `token overhead`

### SEARCH-09. Unsupported PDF search precondition

Command:

```text
wiki ingest testset/spacex.pdf --path <tmp> --json
wiki search "SpaceX" --path <tmp> --json
```

Expected:

- PDF ingest exits `2` with explicit unsupported optional dependency message
- failure artifact is present if conversion failure path applies
- PDF content should not appear in search results because it was not ingested

### SEARCH-10. Validation after search E2E

Command:

```text
wiki validate --path <tmp> --json
wiki lint --path <tmp> --json
wiki status --path <tmp> --json
```

Expected:

- `validate.status: ok`
- no unexpected failed jobs from search path
- status counts reflect sources/chunks/embeddings/review candidates

## Pass criteria

Search E2E pass requires:

- SEARCH-01 through SEARCH-08 pass.
- SEARCH-09 explicit unsupported behavior is confirmed for PDFs unless optional conversion dependency is approved.
- SEARCH-10 reports no unexplained failed jobs.
- Evidence records command outputs, result counts, match types, and representative top results.

## Evidence target

Record results in:

```text
.code-planner/03-build/evidence/phase-2-search-e2e-evidence.md
```

Minimum evidence fields:

- workspace path under `/tmp/opencode`
- input documents used
- command list and exit codes
- result count per query
- top result per query
- vector metadata summary
- `ask` evidence refs summary
- PDF unsupported behavior summary
- cleanup/process note
