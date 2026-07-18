# Phase 2 Execution Brief

## Source planning docs

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md` — Phase 2 lines 95-171
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md` — Phase 2 checks
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`
- `.code-planner/02-planning/decisions/ADRs.md`

## Phase goal

Phase 1 CLI foundation 위에 LLM Wiki Quality 기능을 구현한다. 후보 JSON schema/validator를 Phase 2 수준으로 강화하고, `review_route`/`human_decision`/`retry_instruction`/`superseded` 흐름, prompt versioning, WikiPage compile preview, non-Markdown converter adapter, vector/RAG search 확장을 검증 가능한 CLI/DB/artifact 흐름으로 완성한다.

이번 Phase 2 검증은 사용자가 제공한 `testset/` 자료를 포함한다. 특히 요약 품질과 개념 title/wiki mapping 품질을 핵심 평가 대상으로 둔다. 출력 언어 정책은 “한국어 중심 설명 + 영어 기술용어/고유명사 보존”으로 고정한다. 즉 `summary`, `statement`, `reason`, `review_reason`, WikiPage 설명은 한국어 문장 중심으로 작성하되 `RAG`, `LLM`, `OpenCode`, `Claude Code`, `Palantir`, `SpaceX`, 모델명, 논문/라이브러리명, 도메인 용어는 억지 번역하지 않는다.

## Work units

### WU-001. Existing code discovery and duplicate-risk scan
- Purpose: Phase 2 구현 대상, 기존 CLI/DB/test 구조, 중복 위험을 확인한다.
- Assigned agent: `codebase-explorer`
- Expected files: no source edits; discovery recorded in evidence.
- Completion criteria: existing target symbols, reusable utilities, duplicate-risk warnings, validation commands identified.
- Verification: discovery output cross-checked against `src/llm_wiki/**`, `tests/**`, planning docs.

### WU-002. Candidate schema validator and review persistence
- Purpose: Phase 2 후보 schema를 실제 필드/evidence/ref 규칙까지 검증하고, review candidate/human decision/retry instruction CRUD를 제공한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/schema/candidates.py`, new `src/llm_wiki/schema/review.py`, `src/llm_wiki/schema/__init__.py`, tests.
- Completion criteria: forbidden LLM fields rejected; candidate type별 필수 필드와 `review_route`, same-response `new_node candidate_key` 참조, evidence 규칙 검증; review/human/retry/supersede DB flow works.
- Verification: targeted unit tests and CLI-level persistence smoke tests.

### WU-003. Prompt versioning and LLM task runner
- Purpose: prompt test/confirmed version, full prompt snapshot/change note logging, AgentRun prompt version 참조, OpenAI-compatible JSON task runner를 구현한다.
- Assigned agent: `build-core-dev`
- Expected files: new `src/llm_wiki/schema/prompts.py`, new/updated `src/llm_wiki/llm/chat.py`, `src/llm_wiki/bootstrap.py`, tests.
- Completion criteria: default prompts available; test → confirmed promotion works; LLM JSON response validates and writes artifact/run with prompt_version_id; secrets are masked.
- Verification: mock endpoint tests plus blocked/error artifact tests without secret leakage.

### WU-004. Upgrade Phase 2 CLI quality commands and retry flow
- Purpose: placeholder `extract-claims`, `map`, `link`/`propose_relations`, `summarize`, `ask`, `retry`를 Phase 2 behavior로 전환한다.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli/phase1_placeholders.py` or successor module, `src/llm_wiki/cli/ops_cmds.py`, tests.
- Completion criteria: evidence-based candidates persisted; `node_candidates[].title/aliases/summary` and `mapping_candidates[].existing_node_id/mapping_action/reason` are populated within `candidate.v1`; mapping/relation/conflict routes stored; retry with instruction creates human decision/retry instruction, marks old candidates `superseded`, links new candidates.
- Verification: CLI JSON tests for candidate counts, artifact paths, DB rows, superseded linkage, schema-compliant title/mapping output.

### WU-005. WikiPage compile preview
- Purpose: 승인 전 자동 Vault 반영 없이 Obsidian Markdown 형식의 WikiPage preview를 생성한다.
- Assigned agent: `build-core-dev`
- Expected files: compile command module, optional new `src/llm_wiki/wiki/compile.py`, tests.
- Completion criteria: YAML frontmatter, Claim/Source/Concept links, related concepts, preview/diff artifact path generated; approved Vault write is not performed automatically.
- Verification: compile preview file content assertions and validation report.

### WU-006. Non-Markdown converter adapter
- Purpose: PDF/Office/HTML/URL 입력을 converter adapter 계약으로 Markdown normalized pipeline에 연결하고 실패 시 error artifact를 남긴다.
- Assigned agent: `build-backend-script-dev`
- Expected files: new `src/llm_wiki/pipeline/convert.py`, updates to ingest/hashing CLI path, tests.
- Completion criteria: converter interface exists; supported sample conversion creates `converted_markdown`/normalized Markdown; unsupported/dependency-missing failure is explicit and artifacted.
- Verification: local file/HTML fixture conversion tests; URL/dependency failure path tests.

### WU-007. Vector/RAG search extension
- Purpose: stored embeddings over chunk/source/wiki candidates에 cosine similarity 기반 vector search를 추가하고 `wiki search`/`wiki ask`의 RAG context를 확장한다.
- Assigned agent: `build-core-dev`
- Expected files: new `src/llm_wiki/search/vector.py`, `src/llm_wiki/cli/ops_cmds.py`, tests.
- Completion criteria: selected/all reindex path works; vector similarity smoke test returns ranked refs; `ask` artifact includes evidence refs from Source/Claim.
- Verification: deterministic/fallback vector tests and CLI search/ask JSON assertions.

### WU-008. Testset quality evaluation harness
- Purpose: `testset/` 자료를 Phase 2 E2E 입력으로 사용해 요약 품질과 title/wiki mapping 품질을 평가한다.
- Assigned agent: `build-test-validation`
- Expected files: new/updated tests and quality evaluation reports under allowed evidence/test paths; raw `testset/` inputs must not be modified.
- Completion criteria: Markdown and PDF testset items are processed through ingest/convert/normalize/chunk/embed/extract/map/summarize/compile where applicable; evaluator records schema compliance, summary quality, title quality, wiki mapping quality, evidence grounding, language policy compliance.
- Verification: supervised/gold checks are used when expected labels exist; when no gold labels exist, rubric-based checks must explicitly report `gold_available: false` and must not claim supervised pass. Evaluation artifacts include per-file scores and failure reasons.

### WU-009. Phase 2 validation and evidence
- Purpose: Phase 2 required checks를 실행하고 evidence를 작성한다.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-2-build-evidence.md`, test/e2e logs.
- Completion criteria: real validation commands run; `testset/` quality evaluation recorded; failures/blockers documented; process/port cleanup recorded; ready-for-check flag accurate.
- Verification: `git status`, `git diff --stat`, `git diff --check`, test suite, CLI E2E.

## Quality evaluation criteria

### Summary quality

- 핵심 주장/논점이 빠지지 않는다.
- 원문에 없는 내용을 단정하지 않는다.
- 주요 evidence/source refs가 artifact에 남는다.
- 과도하게 긴 발췌가 아니라 사람이 검토 가능한 압축 요약이다.
- 한국어 중심 문장으로 설명하되 기술용어/고유명사는 원문 영어를 보존한다.

### Title and wiki mapping quality

- `node_candidates[].title`은 개념을 대표하며 너무 일반적인 제목을 피한다.
- `node_candidates[].aliases`는 영어 약어, 제품명, 대체 표현을 보존한다.
- 기존 wiki와 같은 개념이면 `mapping_candidates[].mapping_action`은 `link_to_existing` 또는 `merge_candidate`를 사용한다.
- 다른 개념이면 `create_separate`를 사용한다.
- `mapping_candidates[].existing_node_id`는 허용된 기존 wiki/node allow-list 안에서만 사용한다.
- `mapping_candidates[].reason`과 `review_reason`은 한국어 중심으로 판단 근거를 설명한다.
- `evidence_claim_keys`는 실제 `claim_candidates[].candidate_key`를 참조한다.
- 임의 `tags` 필드를 추가하지 않고 현 schema의 `node_candidates`, `mapping_candidates`, `relation_candidates` 안에서만 표현한다.

### Language policy

- 한국어 중심 설명: `summary`, `statement`, `reason`, `review_reason`, WikiPage 설명 문단.
- 영어 보존: 기술 용어, 고유명사, 제품명, 약어, 모델명, 논문/라이브러리명, 의미가 깨지는 도메인 용어.
- 단순 “한글 비율”만으로 pass 처리하지 않는다. 영어 보존 대상의 무리한 번역도 fail 사유가 될 수 있다.

### Schema compliance

- LLM은 영구 ID, `human_decision`, `retry_instruction`, `approved`, `rejected`, `replaced`, 별도 `needs_human_review` 배열을 출력하지 않는다.
- 후보는 `candidate.v1` envelope와 각 candidate type별 필수 필드를 지킨다.
- `review_route`는 `normal_review`, `needs_merge_decision`, `needs_retry`, `conflict_flag` 중 하나다.
- 같은 응답의 new node 참조는 `candidate_key`로만 연결한다.

## Out of scope

- Web UI 구현, Dashboard/Review 화면, Graph popup, Web Settings UI.
- 다중 사용자 승인/권한.
- 승인 전 자동 Vault 반영.
- Planning 문서와 다른 schema/validation 기준 변경.
- 새 필수 외부 dependency 추가는 사용자 확인 전까지 금지. 필요 시 optional adapter/failure artifact로 처리하거나 별도 승인 요청.

## Validation commands

```text
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m tests.run_phase1
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m llm_wiki.cli init --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest samples/rag.md --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli normalize <source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli chunk <source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli embed source:<source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli extract-claims <source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli map <source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli link source:<source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli compile source:<source_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli retry <run_id> --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli search "RAG" --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ask "What is RAG?" --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli validate --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli lint --path /tmp/opencode/phase2-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli init --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/AlexsJones-Ilmfit.md --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/OKF\ SPEC.md --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/systima-claude-code-vs-opencode-token-overhead.md --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/spacex.pdf --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/SpaceX\ 서플라이\ 체인\ 산업분석.pdf --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli ingest testset/palantir-vs-classic-ontology.pdf --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli validate --path /tmp/opencode/phase2-testset-e2e --json
PYTHONPATH=src python3 -m llm_wiki.cli lint --path /tmp/opencode/phase2-testset-e2e --json
git status --short
git diff --stat
git diff --check
```

## Git checkpoint plan

- Planned checkpoint: `phase-2-llm-wiki-quality`.
- Do not commit unless validation/evidence pass and user/check flow explicitly permits it.
- Before checkpoint/completion: inspect `git status`, `git diff --stat`, `git diff --check`.

## Risks

- LLM endpoint/sample env absence can block live quality validation; use mock endpoint tests and mark real endpoint checks accurately.
- `testset/`에 gold/expected labels가 없으면 supervised quality pass를 주장할 수 없다. 이 경우 rubric 평가와 schema/language/evidence checks를 분리해 기록해야 한다.
- `prompt_versions`, `review_candidates`, `human_decisions`, `retry_instructions` tables exist but are currently unused, so integration breadth is high.
- Non-Markdown conversion may require optional external dependency; mandatory dependency changes need user confirmation.
- No sqlite-vec table exists; vector/RAG extension will initially use existing `embeddings.vector_blob`/`vector_json` unless planning-approved dependency/index change is separately approved.
- Phase 1 committed baseline exists, but current worktree state must be checked before implementation to avoid mixing unrelated edits.
