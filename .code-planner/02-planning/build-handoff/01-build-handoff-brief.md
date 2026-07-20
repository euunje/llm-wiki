# 01 Build Handoff Brief — LLM Wiki Local

## 게이트 상태

- 상태: approved planning handoff
- 기준 handoff 원본: `.code-planner/02-planning/handoff/build-handoff.md`
- 승인 Ideation: `.code-planner/01-ideation-approved.json`
- Build 시작 phase: Phase 1 — CLI Foundation

## Build 목표 요약

LLM Wiki Local은 로컬 개인 지식 시스템이다. Obsidian Vault는 사람이 읽고 수정하는 지식 저장소이고, SQLite는 시스템 상태, 작업 기록, metadata, 검색 index, 후보/검토 상태를 관리한다.

## 확정된 기술 결정

- 실행 환경: local Linux, 단일 사용자
- 구현 언어: Python
- 저장소: Obsidian-compatible Markdown Vault + SQLite
- 설정 파일: YAML
- Web 인증: `.env` 사용자 비밀번호 기반
- Sync 정책: `wiki sync` 기본 dry-run/report, 실제 반영은 `--apply`
- 임베딩: `fastembed` + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- LLM 런타임: configurable endpoint + sample env
- 정본 normalized format: Markdown
- MDX: Web preview/export용 optional format

## Phase 구성

1. Phase 1 — CLI Foundation
   - CLI 기능 구현
   - Markdown ingest/normalize/chunk/embed
   - LLM 연결 테스트와 JSON/artifact 계약
   - SQLite schema, Job/AgentRun/Artifact
   - 수동 `wiki sync`

2. Phase 2 — LLM Wiki Quality
   - LLM 후보 schema/prompt 품질
   - WikiPage compile preview
   - 비-Markdown → Markdown normalized 변환
   - prompt versioning
   - vector/RAG search 확장

3. Phase 3 — Web Review UI
   - 로그인 → Dashboard
   - Review 3영역 UI
   - Graph popup
   - Prompt Settings/versioning

## Build agent 필수 참고 문서

1. `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
2. `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
3. `.code-planner/02-planning/phases/01-phase-plan.md`
4. `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
5. `.code-planner/02-planning/validation/01-validation-plan.md`
6. `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`
7. `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
8. `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
9. `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
10. `.code-planner/02-planning/validation/cli-e2e-test-plan.md`

## 원본 handoff 전문

# Build Handoff — LLM Wiki Local

## 상태

- Planning 상태: Build 전환 승인 대기
- 승인된 Ideation: `.code-planner/01-ideation-approved.json`
- Planning 패키지: `.code-planner/02-planning/`
- 승인된 Web Review HTML 목업: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`
- 목업 승인 기록: `.code-planner/02-planning/review/phase-3-prv-feedback.md`

## 제품 방향

LLM Wiki Local은 로컬 개인 지식 시스템이다. Obsidian Vault는 사람이 읽고 수정하는 지식 저장소이고, SQLite는 시스템 상태, 작업 기록, metadata, 검색 index, 후보/검토 상태를 관리한다.

## 확정된 기술 결정

- 실행 환경: local Linux, 단일 사용자
- 구현 언어: Python
- 저장소: Obsidian-compatible Markdown Vault + SQLite
- 텍스트 검색: SQLite FTS5
- 벡터 검색: sqlite-vec 후보
- 임베딩: `fastembed` + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- LLM 런타임: configurable endpoint + sample env
- 설정 파일: YAML
- Web 인증: `.env` 사용자 비밀번호 기반
- Sync 정책: `wiki sync` 기본 dry-run/report, 실제 반영은 `--apply`
- Git 운영: 단일 브랜치 + phase별 commit
- Git remote 후보: `git@github.com:euunje/llm-wiki-local.git`
- 정본 normalized format: Markdown
- MDX: Web preview/export용 optional format


## PRV 수정 요청 반영

최근 handoff 리뷰에서 나온 3개 수정 요청을 다음처럼 반영했다.

1. `wiki init` 폴더 구조 명확화
   - 문서: `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
   - Vault 기본 구조: `00_Inbox`, `10_Wiki`, `20_Review`, `80_Raws`, `90_Settings`
   - 시스템 data 구조: `data/raw`, `data/normalized`, `data/artifacts`, `data/exports`, `data/cache`

2. LLM 연결 테스트 명령 위치 명확화
   - `wiki doctor`: 로컬 환경 점검
   - `wiki models test <model_id>`: 실제 LLM/chat/embedding endpoint 응답 테스트
   - CLI 동작 명세에 명시

3. Build 목표와 기능별 E2E 테스트 플랜 보강
   - 문서: `.code-planner/02-planning/validation/cli-e2e-test-plan.md`
   - Init, ingest pipeline, embedding, LLM 연결, candidate contract, sync, retry, compile placeholder, healthcheck별 E2E 정의

## Phase 구성

### Phase 1 — CLI Foundation

목표: CLI 기능 구현과 기반 계약 완성.

핵심 구현:

- Python CLI entrypoint
- Settings/sample env/YAML settings
- Vault/data/SQLite schema
- Job/AgentRun/Artifact 기록
- Markdown ingest/normalize/chunk/embed
- LLM 연결 테스트와 JSON/artifact 계약
- validate/lint/status/search/fix/retry/sync
- ask/map/summarize/compile은 Phase 1에서 최소 계약/placeholder, Phase 2에서 품질 고도화

필수 E2E:

```text
ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync
```

### Phase 2 — LLM Wiki Quality

목표: LLM 후보 품질, WikiPage 품질, 비-Markdown 변환 구현.

핵심 구현:

- LLM 후보 JSON schema/validator
- `review_route` 기반 후보 라우팅
- `human_decision` 사람 결정 분리
- `retry_instruction` runner/human 메타
- retry 시 이전 후보 `superseded` 연결
- `propose_relations`에서 같은 응답의 `new_node candidate_key` 참조 허용
- prompt test version → test run → confirmed version
- prompt 전체 snapshot + change note logging
- WikiPage compile preview
- 비-Markdown → Markdown normalized 변환
- MDX는 Web preview/export optional
- 신규 wiki 확정 시 즉시 embedding/index 추가
- 선택 항목/전체 재인덱싱
- vector/RAG search 확장

### Phase 3 — Web Review UI

목표: 단일 관리자용 Dashboard, Review, Graph popup, Settings 구현.

승인된 목업을 기준으로 구현한다.

- HTML: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`
- Feedback: `.code-planner/02-planning/review/phase-3-prv-feedback.md`

필수 UX:

- 로그인 → Dashboard
- Dashboard: 자료 처리 현황, 승인 필요, pending, 오류, wiki 개수, 시스템 상태
- Review 화면:
  - 왼쪽: 기존 wiki 유사도 목록, 리스트형
  - 가운데: 선택한 기존 개념의 의미/aliases/claims/relations
  - 오른쪽: 신규 개념 batch 카드
- Actions: 병합, 신규, 수정, reject reason + retry instruction
- Wiki compile preview: 필요할 때 펼침
- Graph popup: 1-hop graph + wiki 내용 패널
- Settings: model/prompt 설정, prompt test version, test run, confirm version, 변경 로그

---

# CLI 기능별 동작 요약

상세 명세는 `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`를 따른다.

| 명령 | Phase | 동작 요약 | 주요 산출물 |
|---|---:|---|---|
| `wiki init` | 1 | Vault/data/settings/DB/schema 생성, 재실행 안전 | settings path, DB path |
| `wiki settings get/set` | 1 | YAML settings 조회/변경, 민감정보 마스킹, 변경 이력 | settings log |
| `wiki doctor` | 1 | 로컬 환경 점검: 경로, DB, FTS5, sqlite-vec, env | doctor report |
| `wiki inbox scan` | 1 | inbox Markdown 감지, hash/중복 후보, source 후보/job 생성 | scan report, jobs |
| `wiki ingest` | 1 | Markdown 파일을 Source로 등록, raw/source stub/normalize job 생성 | source_id, job_id |
| `wiki ingest-text` | 1 | 직접 입력 텍스트를 Source로 저장 | source_id |
| `wiki normalize` | 1 | Markdown을 normalized Markdown으로 정규화, locator 기록 | normalized path |
| `wiki chunk` | 1 | normalized text를 chunk로 분할, token_count/locator 기록 | chunk rows |
| `wiki embed` | 1/2 | fastembed로 embedding 생성, index 갱신, 재인덱싱 지원 | embeddings, dimension |
| `wiki models list/test` | 1 | 모델 목록 출력, chat/embedding 연결 테스트 | model test artifact |
| `wiki route get/set` | 1 | task별 model routing 조회/변경 | route config/log |
| `wiki extract-claims` | 1/2 | Phase 1은 JSON/artifact 계약, Phase 2는 실제 Claim 후보 품질 | candidate artifact |
| `wiki summarize` | 1/2 | Phase 1 placeholder, Phase 2 실제 요약 | summary artifact |
| `wiki link` | 1/2 | relation 후보 계약/생성, ontology 검증 | relation candidates |
| `wiki map` | 1/2 | mapping diff placeholder → 실제 mapping 후보 | mapping candidates |
| `wiki compile` | 1/2 | 기본 초안/placeholder → WikiPage preview/diff | preview, diff |
| `wiki validate` | 1 | schema/frontmatter/artifact/evidence 검증 | validation report |
| `wiki lint` | 1 | 품질 규칙 검사: broken link, stale embedding 등 | lint report |
| `wiki fix` | 1 | 형식성 수정만 자동 처리, 의미 변경 제외 | fix report |
| `wiki retry` | 1/2 | 실패 run 재실행, retry_instruction 주입, 이전 후보 superseded | new run, artifact |
| `wiki sync` | 1 | 기본 dry-run, `--apply` 반영, Vault/DB 차이 report | sync report |
| `wiki status` | 1 | job/review/source/concept/embedding/LLM 상태 요약 | status report |
| `wiki search` | 1/2 | Phase 1 FTS/metadata, Phase 2 vector/RAG 확장 | search results |
| `wiki ask` | 1/2 | Phase 1 후보 artifact, Phase 2 근거 기반 LLM 답변 | answer artifact |
| `wiki healthcheck` | 3/운영 | DB/Vault/stale embedding/orphan/broken link 종합 점검 | health report |

## CLI 공통 계약

모든 명령은 가능한 범위에서 다음을 지원하거나 not_applicable 사유를 문서화한다.

- `--json`
- exit code
- job/run id
- artifact path
- dry-run/apply 정책
- idempotency 정책
- machine-readable error report

## 주요 설계 계약

### LLM schema 계약

- LLM은 후보만 제안한다.
- LLM은 영구 ID를 만들지 않는다.
- LLM은 Vault 파일을 직접 수정하지 않는다.
- LLM은 사람 결정을 출력하지 않는다.
- 후보 라우팅: `review_route`
- 사람 결정: `human_decision`
- 재시도 지시: `retry_instruction`
- retry 이전 후보: `superseded`

초기 `review_route` 값:

- `normal_review`
- `needs_merge_decision`
- `needs_retry`
- `conflict_flag`

### Prompt version 계약

- prompt 변경은 test version으로 저장한다.
- test version은 test run으로 검증한다.
- 사용자가 확인하면 confirmed version으로 승격한다.
- prompt 전체 snapshot과 change note를 저장한다.
- AgentRun은 prompt version을 기록한다.

### Sync 계약

- `wiki sync`: read-only dry-run/report
- `wiki sync --apply`: 실제 반영 + artifact 기록

### Reindex 계약

- 신규 wiki 확정 시 즉시 embedding/index 추가
- 선택 항목 재인덱싱 지원
- 전체 재인덱싱 지원

## 검증 문서

- `.code-planner/02-planning/validation/validation-plan.md`
- `.code-planner/02-planning/validation/planning-crosscheck.md`

Build는 required validation check를 phase 완료 기준으로 사용한다.

## Build agent가 먼저 볼 문서

1. `.code-planner/01-ideation-approved.json`
2. `.code-planner/02-planning/README.md`
3. `.code-planner/02-planning/decisions/ADRs.md`
4. `.code-planner/02-planning/decisions/dependencies.md`
5. `.code-planner/02-planning/phases/phase-1-cli-foundation.md`
6. `.code-planner/02-planning/phases/phase-2-llm-wiki-quality.md`
7. `.code-planner/02-planning/phases/phase-3-web-review-ui.md`
8. `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`
9. `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
10. `.code-planner/02-planning/validation/cli-e2e-test-plan.md`
11. `.code-planner/02-planning/validation/validation-plan.md`
10. `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`


## Build 전 모호성 해소 보강

Build ambiguity check 결과를 반영해 다음 초안/정책을 추가한다.

### 1. SQLite schema 초안

- 문서: `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- 최소 table:
  - `sources`
  - `source_chunks`
  - `embeddings`
  - `jobs`
  - `agent_runs`
  - `artifacts`
  - `review_candidates`
  - `human_decisions`
  - `retry_instructions`
  - `prompt_versions`

Build는 이 초안을 기준으로 구현하되 index, migration tool, sqlite-vec virtual table은 구현 중 확정할 수 있다.

### 2. LLM 후보 JSON schema 초안

- 문서: `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- 핵심:
  - 공통 envelope 유지
  - `review_route` 사용
  - `needs_human_review` 배열 제거
  - `human_decision`과 `retry_instruction`은 LLM 출력 금지
  - Phase 1 placeholder는 빈 후보 배열을 허용하지만 envelope validation은 수행

### 3. Vector index 방향

- 문서: `.code-planner/02-planning/decisions/vector-index-options.md`
- sqlite-vec 설치 실패를 단순 fallback 처리하지 않는다.
- Build 초기에 vector index spike를 수행해 sqlite-vec/sqlite-vss/LanceDB/brute-force/FTS-only 중 방향을 검토한다.
- 단, embedding row 저장은 Phase 1 required다.

### 4. Placeholder 산출물

Phase 1 placeholder는 다음을 최소 산출물로 한다.

- `wiki summarize`: `{target, summary_placeholder, source_refs, status}` JSON artifact
- `wiki map`: `{source_id, mapping_candidates: [], high_similarity_candidates: [], status}` JSON artifact
- `wiki ask`: `{query, candidates, evidence_refs, answer_placeholder, status}` JSON artifact
- `wiki compile`: 최소 Markdown stub 또는 preview artifact

`wiki compile` 최소 Markdown stub:

```md
---
title: "..."
aliases: []
status: draft_preview
source_refs: []
claim_refs: []
relation_refs: []
---

# Title

> Phase 1 placeholder. 실사용 WikiPage 품질은 Phase 2에서 구현한다.
```

### 5. Chunk/token/locator 정책

- chunk 정책은 fastembed tokenizer 기준으로 시작한다.
- 초기 chunk size/overlap은 Build에서 fastembed 모델 제한을 확인한 뒤 상수화한다.
- locator는 normalized Markdown 기준 offset/range를 사용한다.
- locator 최소 필드:
  - `source_id`
  - `start_offset`
  - `end_offset`
  - `char_count`
  - `heading_path`
  - `quote_start`

### 6. Hash/중복 정책

- hash 알고리즘: sha256
- 동일 hash 발견 시 기본 동작: skip + warn report
- 파일명이 달라도 내용 hash가 같으면 동일 Source 후보로 처리

## Build 전환 질문

이 한글 Build handoff와 CLI 기능별 동작 명세를 기준으로 Build 단계로 넘어갈까요?



## UI/UX Build Gate Compatibility

- Canonical mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`
- Build gate compatibility mockup: `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- Canonical approval: `.code-planner/02-planning/review/phase-3-prv-feedback.md`
- Build gate compatibility approval: `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`
- 실제 리뷰는 PRV로 승인되었으며, legacy Lavish 파일명은 Build gate 호환용이다.


## Phase 3 Web UI 확정 기술스택

Build agent는 Phase 3 Web UI를 다음 stack으로 구현한다.

- FastAPI
- uvicorn
- Jinja2
- python-multipart
- pydantic
- PyYAML
- python-dotenv
- server-rendered HTML
- Vanilla JavaScript ES modules
- plain CSS
- inline SVG graph popup
- `.env` 관리자 비밀번호 + stdlib hmac signed session cookie

제외:

- React/Vite/Next.js
- Tailwind build pipeline
- 외부 graph visualization library 필수 의존
- 다중 사용자 auth

Dependency 승인 범위:

- 위 dependency는 Planning에서 승인된 것으로 간주한다.
- 이 목록 밖의 dependency가 필요하면 Build를 중단하고 사용자 승인을 요청한다.
