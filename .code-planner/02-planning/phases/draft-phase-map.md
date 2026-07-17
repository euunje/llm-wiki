# Stage 3 — Draft Phase Map

## Phase 설계 원칙

- 파괴적 reset은 제품 기능으로 만들지 않는다. 테스트 준비 절차로만 문서화한다.
- 원본 파일의 물리 chunk 분할은 하지 않는다.
- Inbox item 상태와 파일 위치 이동을 먼저 안정화한 뒤 chunked extraction을 연결한다.
- Web UI와 CLI는 같은 도메인 상태 모델을 공유한다.
- UI/UX가 포함되므로 Planning Stage 4에서 HTML mockup + Lavish review가 필요하다.

## Phase 1 — Inbox domain model and path/state foundation

### 목표

Inbox-first flow의 공통 기반을 만든다. 기존 `sources` 중심 모델에 Inbox item 상태를 추가하고, Inbox/Failed/Review/Archive path 의미를 확정한다.

### 포함 기능

- DB schema 설계/마이그레이션 초안
  - 예: `inbox_items`, `inbox_events`, `inbox_candidates` 또는 equivalent
- 상태 모델 정의
  - `pending`, `processing`, `failed`, `review`, `archived`, `ingested`
- path mapping 정의
  - Inbox root
  - `Inbox/_Failed`
  - `Inbox/_Review`
  - `processing` DB 상태/lock (실제 `_Processing` 폴더는 만들지 않음)
  - Raw Sources archive
- 파일명 충돌/중복 hash 정책 초안
- current branch 기준 migration compatibility

### 의존성

- 기존 `config.WikiPaths`, `db.py`, `ingest_raw.py`, `jobs.py`

### 검증 방향

- DB migration idempotent
- path config가 Ja vault layout과 default layout 모두 통과
- 기존 tests가 깨지지 않음

### Resolved decisions

- `inbox_items`와 `sources`는 처리 시작 시 materialize/link한다. 생성된 `sources` row는 provenance/retry를 위해 유지한다.
- Inbox root는 별도 path semantics로 두고, 기존 `non_categories`는 Review compatibility layer로만 취급한다.

## Phase 2 — Inbox registration and file movement

### 목표

사용자 입력 3유형을 Inbox에 등록하고, 성공/실패/리뷰/Archive 이동의 원자성을 정의한다.

### 포함 기능

- 입력 유형별 등록
  - 문서파일: PDF/DOCX/PPTX/HTML/TXT 등
  - Markdown/Obsidian scrape
  - pasted text를 `.md` raw-like source로 생성
- Inbox 등록 API/CLI plumbing
- move 중심 파일 이동
  - incoming → processing DB state/lock
  - success → Raw Sources archive
  - failure → Inbox/_Failed
  - review → Inbox/_Review
- Failed 로그/리포트 생성
- 오류 확인 후 로그 삭제 가능성

### 의존성

- Phase 1 상태 모델
- 기존 `ingest_raw.add_file`, parser registry

### 검증 방향

- 실제 move semantics
- 이동 실패 시 상태 불일치 방지
- 동일 파일/hash 중복 처리
- 실패 원본과 로그가 같이 추적됨

### Open questions

- 이동 실패 시 전체 rollback vs partial state with retry
- Failed/Review 폴더 내 파일/리포트 naming convention

## Phase 3 — Chunked extraction map-reduce

### 목표

큰 문서를 `parsed.text` truncate가 아니라 `ParsedDocument.chunks` 기반으로 extraction한다.

### 포함 기능

- 작은 문서 single extraction 유지
- 큰 문서 chunk-level extraction
- context overflow 400 감지 시 chunked extraction fallback
- chunk별 결과:
  - summary
  - candidates
  - key takeaways
  - chunk index/source offset metadata
- aggregate/dedupe
- 기존 2-pass resolution/page generation과 연결

### 의존성

- Phase 1/2 state and source tracking
- 기존 parsers, prompts, ingest_llm models

### 검증 방향

- 100k+ chars 문서가 context overflow 없이 처리됨
- 뒤쪽 chunk entity/concept도 후보에 포함됨
- chunk 실패 시 재시도/failed routing

### Open questions

- chunk extraction 실패가 전체 source 실패인지, partial retry 가능한지
- aggregate confidence 계산 방식

## Phase 4 — Review/Failed workbench behavior

### 목표

`Inbox/_Review`와 `Inbox/_Failed`를 active work queue로 만든다.

### 포함 기능

- Review item 생성 조건
  - fuzzy duplicate/merge ambiguity
  - low confidence
  - entity/concept classification ambiguity
  - multiple exact/near matches
  - guide/runbook/map/MOC 등 canonical Wiki page로 바로 넣기 어려운 내용
  - JSON validation failed after retry
  - allowed_links violation or links_used mismatch
  - source reference missing/unclear
  - source/canonical slug conflict
  - chunk extraction conflict
- Review UI/API behavior
  - 유사 Wiki 편입 후보 표시
  - 편입 대상 선택
  - 편입 대상 없음 → 별도 태깅/분류 입력 폼
  - 승인/수정 후 재처리/거절·보류
- Failed behavior
  - 원인 로그/리포트 표시
  - 재시도
  - 원본 열기
  - 보류/archive
  - 삭제

### 의존성

- Phase 1 상태 모델
- Phase 2 file movement
- 기존 `relinker.promote_file`, `webapp/routes/inbox.py`

### 검증 방향

- Review 후보가 올바른 action set을 갖는다.
- Failed log가 저장되고 처리 후 삭제 가능하다.
- 유사도 후보와 별도 태깅 폼이 UI에서 이해 가능하다.

### UI/UX 필요

- HTML mockup 필수
- Lavish review 필수

## Phase 5A — Inbox-to-Job dispatch mapping

### 목표

Inbox pending item을 실제 job/LLM 처리 pipeline에 연결한다. 사용자에게는 Inbox-first로 보이되 내부적으로는 기존 `sources`/`jobs`/`ingest_llm` 안정화 코드를 재사용한다.

### 포함 기능

- `inbox_item_id -> source_id -> ingest_job` mapping
- 처리 시작 시 `sources` row 생성/재사용 및 `inbox_items.source_id` 저장
- `/ingest/start` 또는 equivalent API가 `inbox_item_id`를 primary input으로 받음
- `/ingest/scan` 의미를 Raw queue 등록에서 “Raw Sources에서 Inbox로 가져오기”로 변경
- 기존 Raw Sources 문서가 Inbox pending으로 보인 뒤 처리됨

### 의존성

- Phase 1~4
- 기존 `sources`, `jobs`, `ingest_llm.ingest_source(source_id)`

### 검증 방향

- upload/paste/imported Raw Sources -> Inbox pending -> source/job materialization
- `sources` 직접 queue 우회 없음
- UX test 시작 전 이 phase 통과 필수

## Phase 5B — CLI/Web UI integration

### 목표

사용자가 Inbox-first 흐름을 CLI와 Web UI에서 일관되게 사용할 수 있게 한다.

### 포함 기능

- Web ingest screen 개편
  - Files/Markdown/Text 입력 구분
  - Inbox queue 표시
  - Raw Sources CTA는 가져오기/import로 표현
  - Processing/Failed/Review 상태 표시
- Review workbench screen
- Failed diagnostics screen
- Jobs/progress screen update
- Chunk extraction progress 표시
- CLI command semantics
  - `wiki add` 또는 신규 명령이 Inbox로 넣음
  - `wiki ingest`가 Inbox pending을 처리
  - status/retry/review 관련 명령 검토

### 의존성

- Phase 5A

### 검증 방향

- Web/CLI parity
- browser UX review
- queue/retry/failed/review happy and sad path

### UI/UX 필요

- HTML mockup 필수
- Lavish review 필수

## Phase 6 — Test reset guide and end-to-end validation

### 목표

사용자가 말한 일회성 테스트 초기화와 전체 E2E 검증 절차를 안전하게 문서화한다.

### 포함 기능

- qmd/Obsidian 값 초기화 절차 문서
- 기존 Wiki 자료 삭제 후 Inbox 기반 재처리 테스트 절차
- 기존 Raw 자료를 Inbox로 실제 move하는 테스트 절차
- 제품 명령으로 reset 구현하지 않음
- E2E test matrix
  - 문서파일
  - Markdown scrape
  - pasted text
  - 큰 문서 chunked extraction
  - failed route
  - review route
  - archive move

### 의존성

- Phase 1~5

### 검증 방향

- 사용자가 실제 vault에서 테스트 가능
- 운영 데이터 손실 주의사항 명확
- qmd/Obsidian reset이 제품 기능으로 오해되지 않음

## 예상 Phase 순서

1. Inbox domain model and path/state foundation
2. Inbox registration and file movement
3. Chunked extraction map-reduce
4. Review/Failed workbench behavior
5A. Inbox-to-Job dispatch mapping
5B. CLI/Web UI integration
6. Test reset guide and end-to-end validation

## Cross-phase risks

- `ingest_llm.py`가 이미 크고 복잡하므로 refactor 없이 기능 추가하면 유지보수성이 악화된다.
- 상태 모델을 파일 frontmatter에만 두면 Web/CLI/job retry가 불안정해진다.
- Raw archive 이동과 Wiki commit 사이 장애 복구 정책이 필요하다.
- Raw Sources를 계속 queue로 보이게 하면 Inbox-first 목표와 충돌한다.
- UI/UX 범위가 크므로 phase별 visual review가 필요하다.
- 기존 tests는 `non_categories`를 `00. Inbox/_Review`로 쓰는 Ja layout에 의존한다.
