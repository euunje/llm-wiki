# Architecture Decision Records

## ADR-001: Inbox item DB + file-move hybrid

- Status: accepted
- Decision: Inbox item 상태는 DB로 관리하고, 실제 원본 파일은 Inbox/Failed/Review/Raw archive 사이에서 이동한다. 처리 중 상태는 실제 `_Processing` 폴더가 아니라 DB `processing` state/lock으로 표현한다.
- Rationale: 파일 이동은 Obsidian 친화적이고 사람이 이해하기 쉬우며, DB 상태는 동시성, retry, 실패 원인, source 연결, candidate review 추적에 필요하다.
- Consequences: DB schema migration, Web/CLI 상태 일관성, move failure recovery가 필요하다.

## ADR-002: Raw Sources is archive, not input

- Status: accepted
- Decision: 사용자 입력은 Inbox로 들어오고, 성공 처리된 원본만 Raw Sources archive로 이동한다. 기존 vault/Raw Sources 문서는 정상 처리 queue가 아니라 Inbox로 가져오는 import/migration source material로 취급한다.
- User-facing flow: `업로드/가져오기 -> Inbox -> LLM 확인/처리 -> Wiki 문서화 완료 -> Raw Sources archive`.
- Consequences: Web upload/paste와 CLI add의 기본 목적지가 Inbox로 바뀐다. `/ingest`의 Raw Sources scan 표현은 “Raw Sources에서 Inbox로 가져오기”로 바뀌어야 한다.

## ADR-003: Failed/Review folders are active work queues

- Status: accepted
- Decision: Failed 원본은 `Inbox/_Failed`, Review 대상은 `Inbox/_Review`로 이동한다. Review UI는 유사 Wiki 후보 편입과 별도 태깅/분류 입력 폼을 제공한다.
- Consequences: Failed/Review action 모델과 diagnostic report가 필요하다.

## ADR-004: Chunked extraction uses parser chunks, not raw file splitting

- Status: accepted
- Decision: 큰 문서는 원본 파일을 물리 분할하지 않고 `ParsedDocument.chunks` 기반 chunked extraction map-reduce로 처리한다.
- Consequences: chunk-level candidate/source provenance와 aggregation/dedupe가 필요하다.

## ADR-005: Reset is test setup only

- Status: accepted
- Decision: qmd/Obsidian 초기화는 이번 테스트 전 일회성 준비로만 취급하고 제품 기능/명령으로 구현하지 않는다.

## ADR-006: CLI Review scope

- Status: accepted
- Decision: CLI는 `add`, `ingest`, `status`, `retry <inbox_item_id>`를 최소 지원한다. Review 상세 처리(유사 Wiki 편입/태깅/분류)는 Web UI 중심이며 CLI `review` 명령은 Build 필수 범위가 아니다.

## ADR-007: Inbox-to-Job dispatch mapping reuses existing source/job pipeline

- Status: accepted
- Decision: `ingest_llm.ingest_source(source_id)`와 `jobs.enqueue(source_id)`를 대규모 refactor하지 않는다. 대신 pending Inbox item 처리 시작 시 내부적으로 `sources` row를 생성/재사용하고 `inbox_items.source_id`에 연결한 뒤 기존 job pipeline을 호출한다.
- Rationale: 기존 LLM ingest, source provenance, job event, chunked extraction 안정화 코드를 재사용하면서 사용자 경험은 Inbox-first로 바꿀 수 있다.
- Source row lifecycle: materialized `sources` rows are retained for provenance and retry. Retry may reuse the linked `source_id` when it is still valid; otherwise Phase 5A may rematerialize and update `inbox_items.source_id` with evidence.
- Consequences: Phase 5A에서 `inbox_item_id -> source_id -> ingest_job` mapping, `/ingest/start`의 `inbox_item_id` 지원, Raw Sources import-to-Inbox scan, `/ingest` pending queue의 `inbox_items` 기반 표시가 Build gate가 된다.
