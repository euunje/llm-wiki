# Stage 2 — 기술 확정 및 관련 내역 문서화

## ADR-001: Inbox item DB + file-move hybrid

- Status: accepted
- Decision: Inbox item 상태는 DB로 관리하고, 실제 원본 파일은 Inbox/Processing/Failed/Review/Raw archive 사이에서 이동한다.
- Rationale:
  - 파일 이동은 Obsidian 친화적이고 사람이 이해하기 쉽다.
  - DB 상태는 동시성, retry, 실패 원인, source 연결, candidate review를 추적하기 위해 필요하다.
- Consequences:
  - DB schema migration 필요.
  - Web UI/CLI는 DB 상태와 파일 위치를 함께 표시해야 한다.
  - 파일 이동 실패 시 복구 정책이 필요하다.

## ADR-002: Raw Sources is archive, not input

- Status: accepted
- Decision: 사용자 입력은 Inbox로 들어오고, 성공 처리된 원본만 Raw Sources archive로 이동한다.
- Rationale:
  - Raw Sources가 입력점과 archive를 겸하면 상태가 모호하다.
  - Inbox가 대기/실패/리뷰 흐름을 담당해야 사용자가 처리 대상을 알기 쉽다.
- Consequences:
  - Web upload/paste와 CLI add의 기본 목적지가 Inbox로 바뀐다.
  - 기존 raw 직접 scan은 호환 또는 migration path로만 취급한다.

## ADR-003: Failed/Review folders are active work queues

- Status: accepted
- Decision:
  - Failed 원본은 `Inbox/_Failed`로 이동하고 원인 파악 로그/리포트를 함께 저장한다.
  - Review 대상은 `Inbox/_Review`로 이동한다.
  - Review UI는 유사 Wiki 후보 편입 선택지와 별도 태깅/분류 입력 폼을 제공한다.
- Rationale:
  - 실패/리뷰는 “처리해야 할 작업”이며 단순 archive가 아니다.
  - 원본/후보를 옮겨 공간 낭비를 줄이고 상태를 명확히 한다.
- Consequences:
  - Failed/Review action 모델 필요.
  - Failed 로그는 확인/처리 후 삭제 가능해야 한다.

## ADR-004: Chunked extraction uses parser chunks, not raw file splitting

- Status: accepted
- Decision: 큰 문서는 원본 파일을 물리 분할하지 않고 `ParsedDocument.chunks`를 이용해 chunked extraction map-reduce로 처리한다.
- Rationale:
  - provenance는 원본 파일 1개로 유지해야 한다.
  - context overflow를 해결해야 한다.
- Consequences:
  - extraction prompt와 parser chunk aggregation 로직 필요.
  - chunk-level candidate/source provenance metadata 필요.

## ADR-005: Reset is test setup only

- Status: accepted
- Decision: qmd/Obsidian 값 초기화는 이번 테스트 전 일회성 준비로 취급하고 제품 기능/명령으로 구현하지 않는다.
- Rationale:
  - 파괴적이고 반복 운영 요구가 아니다.
- Consequences:
  - Build scope에 reset command 없음.
  - 테스트/운영 지침에는 별도 주의사항으로만 남긴다.

## Dependencies and affected areas

- `src/llm_wiki/config.py`
  - Inbox/Failed/Review/Raw archive path mapping 확장 또는 기존 `non_categories` 재해석.
- `src/llm_wiki/db.py`
  - `inbox_items`, `inbox_events` 또는 유사 상태 테이블 추가 검토.
- `src/llm_wiki/ingest_raw.py`
  - raw 등록 중심에서 Inbox 등록/Archive 이동 지원으로 역할 조정.
- `src/llm_wiki/ingest_llm.py`
  - Inbox item 처리, chunked extraction, archive move, failed/review routing 연동.
- `src/llm_wiki/jobs.py`
  - source_id 중심 job에서 inbox_item_id 중심 job 지원 필요.
- `src/llm_wiki/webapp/routes/ingest.py`
  - upload/paste/start 흐름 변경.
- `src/llm_wiki/webapp/routes/inbox.py`
  - Review 작업대 확장.
- `src/llm_wiki/webapp/templates/ingest.html`, `inbox.html`, `jobs.html`
  - UI 개편 대상.
- `src/llm_wiki/cli.py`
  - add/ingest/status/retry 명령 의미 조정.
- tests
  - parser chunks, inbox item state, file move, failed/review routing, UI/API, chunked extraction tests 추가.

## Git plan

- 현재 브랜치에서 phase별 commit.
- 권장 commit 단위:
  1. DB/path model and migration
  2. Inbox registration/file movement
  3. Chunked extraction pipeline
  4. Failed/Review routing and actions
  5. Web UI/CLI integration
  6. Test reset guide and end-to-end validation
