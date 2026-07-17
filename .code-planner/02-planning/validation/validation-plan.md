# Stage 6 — Validation Plan

## 공통 원칙

- 각 phase는 pass/fail/blocked로 판정한다.
- `required` 검증은 Build handoff 후 phase 완료 조건이다.
- UI가 포함된 phase는 기존 UX 기반 HTML mockup/PRV 승인과 구현 결과의 일치 여부를 확인한다.
- reset은 제품 기능이 아니므로, 테스트 초기화 절차는 별도 evidence로만 검증한다.

## Phase 1 — Inbox domain model and path/state foundation

### Required checks

- [ ] DB migration idempotent.
- [ ] 기존 DB에서 schema migration 후 기존 sources/jobs/runs 데이터가 유지됨.
- [ ] Inbox item 상태 enum이 문서와 코드에 일치.
- [ ] path config가 default layout과 Ja layout 모두 통과.
- [ ] 기존 `non_categories` 기반 tests가 새 구조와 호환되거나 migration path가 명확함.
- [ ] `processing`은 실제 `_Processing` 폴더가 아니라 DB state/lock으로 동작함.

### Optional checks

- [ ] migration rollback 또는 backup guide.

### Pass criteria

- 모든 required checks 통과.
- 기존 `pytest tests/test_phase*_*.py` 주요 경로가 깨지지 않음.

### Fail/block criteria

- DB migration이 기존 데이터를 손상하면 fail.
- path config가 external vault layout을 깨면 blocked.

## Phase 2 — Inbox registration and file movement

### Required checks

- [ ] document file, markdown file, pasted text가 Inbox item으로 등록됨.
- [ ] 권장 입력 하위 폴더 `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`가 문서/구현에서 일치함.
- [ ] 성공 시 원본이 Raw Sources archive로 move됨.
- [ ] 실패 시 원본이 `Inbox/_Failed`로 move됨.
- [ ] review 시 원본/후보가 `Inbox/_Review`로 move됨.
- [ ] Failed diagnostic report 생성.
- [ ] 파일명 충돌/중복 hash 처리.
- [ ] move 실패 시 DB/file state mismatch가 남지 않음.
- [ ] move 실패 evidence: 원본 path, target path, DB state, retry 가능 여부가 report/event에 남음.

### Optional checks

- [ ] large file move performance.

### Pass criteria

- 세 입력 유형 각각 happy/failure path 통과.
- 원본 중복 복사 없이 위치 이동이 추적됨.

### Fail/block criteria

- 원본 파일 손실 가능성이 있으면 blocked.

## Phase 3 — Chunked extraction map-reduce

### Required checks

- [ ] 작은 문서는 single extraction 가능.
- [ ] 큰 문서는 `ParsedDocument.chunks` 기반 chunk extraction 사용.
- [ ] context overflow 400 발생 시 chunked fallback.
- [ ] chunk별 candidates/summaries/key_takeaways 수집.
- [ ] chunk extraction progress가 job event/progress에 기록됨.
- [ ] aggregation/dedupe 후 기존 resolution 흐름에 연결.
- [ ] 뒤쪽 chunk의 entity/concept가 누락되지 않음.

### Optional checks

- [ ] chunk-level provenance char range/page info.

### Pass criteria

- 100k+ chars 문서가 context overflow 없이 처리됨.
- chunk 실패/retry/failure routing이 evidence로 남음.

### Fail/block criteria

- truncate만으로 큰 문서를 처리하면 fail.

## Phase 4 — Review/Failed workbench behavior

### Required checks

- [ ] Review 조건별 routing 테스트:
  - fuzzy duplicate/merge ambiguity
  - multiple exact/near matches
  - low/ambiguous/pending confidence
  - entity/concept classification ambiguity
  - guide/runbook/map/MOC 등 canonical Wiki page로 바로 넣기 어려운 내용
  - JSON validation failed after retry
  - allowed_links violation 또는 links_used/body wikilink mismatch
  - source reference missing/unclear
  - source/canonical slug conflict
  - chunk extraction conflict
  - human-approved merge/update required
- [ ] 유사 Wiki 후보 표시.
- [ ] 기존 page 편입 action.
- [ ] 새 entity/concept 생성 또는 별도 태깅/분류 입력 action.
- [ ] Failed 로그/리포트 표시.
- [ ] Failed 재시도/삭제/로그 삭제 action.
- [ ] PRV 승인 HTML mockup과 구현 UX 일치.

### Optional checks

- [ ] batch review actions.

### Pass criteria

- 사용자가 Review item을 편입/생성/태깅/보류 중 하나로 처리 가능.
- Failed item의 원인 파악과 재시도가 가능.

### Fail/block criteria

- Review item이 action 없이 막히면 fail.

## Phase 5A — Inbox-to-Job dispatch mapping

### Required checks

- [ ] Raw Sources import registers files as Inbox pending items, not direct `sources` queue entries.
- [ ] `/ingest/start` or equivalent accepts `inbox_item_id` and resolves/materializes `source_id` internally.
- [ ] A job can be enqueued from an Inbox pending item.
- [ ] `inbox_items.source_id` is persisted after materialization.
- [ ] The existing LLM ingest pipeline still receives a valid `source_id` and can create/update Wiki pages.
- [ ] UX/user testing is blocked until this phase passes.

### Evidence

- API/route test output for `inbox_item_id -> source_id -> ingest_job`.
- DB assertion showing `inbox_items.source_id` populated after start.
- Raw Sources import evidence showing `inbox_items.state = pending` before processing.

### Pass criteria

- A pending Inbox item can start processing without exposing `source_id` to the user.
- Existing Raw Sources material is imported into Inbox before LLM processing.

### Fail/block criteria

- `/ingest` or CLI still treats Raw Sources as the normal processing queue.
- UX testing starts from synthetic seeded workbench items without proving Inbox pending -> job.

## Phase 5B — CLI/Web UI integration

### Required checks

- [ ] `/ingest`에서 Files/Markdown/Text를 Inbox로 등록.
- [ ] `/ingest` 대기열은 `inbox_items`를 primary source로 표시하고 legacy `sources.status = pending`을 주 queue로 쓰지 않음.
- [ ] Raw Sources action copy는 “Raw Sources에서 Inbox로 가져오기”로 표현됨.
- [ ] `/inbox`에서 Review/Failed filter/action 제공.
- [ ] `/jobs`에서 inbox item 상태 표시.
- [ ] `/jobs`에서 chunk extraction phase/progress 표시.
- [ ] CLI add/ingest/status 흐름이 Inbox-first semantics를 반영.
- [ ] CLI `wiki retry <inbox_item_id>`가 Failed item 재시도를 지원.
- [ ] CLI status가 Review count와 Web UI 처리 hint를 제공.
- [ ] Web/CLI가 같은 DB 상태 모델 사용.
- [ ] PRV 승인 HTML mockup과 구현 UX 일치.

### Evidence

- `/ingest`, `/inbox`, `/jobs` 구현 스크린샷 또는 HTML snapshot.
- CLI command output snapshot.
- PRV 승인 HTML mockup path와 구현 화면 비교 메모.

### Optional checks

- [ ] mobile/Tailnet display sanity check.

### Pass criteria

- Web과 CLI로 같은 end-to-end flow 수행 가능.

### Fail/block criteria

- Web과 CLI 상태가 다르게 표시되면 fail.
- Raw Sources action이 다시 직접 queue scan으로 회귀하면 fail.
- Phase 5A mapping 검증 없이 UX 테스트로 넘어가면 blocked.

## Phase 6 — Test reset guide and end-to-end validation

### Required checks

- [ ] qmd/Obsidian 초기화가 제품 기능이 아닌 일회성 테스트 절차로 문서화됨.
- [ ] 기존 Raw 자료를 Inbox로 실제 move하는 테스트 절차 문서화.
- [ ] E2E matrix 문서화:
  - document file
  - markdown scrape
  - pasted text
  - large document chunked extraction
  - failed route
  - review route
  - archive move
- [ ] ingest 성공 E2E가 Wiki page 생성/갱신과 Raw Sources archive 이동을 모두 검증함.
- [ ] 사용자 기능 테스트 evidence path 정의.
- [ ] UX/E2E 테스트는 Phase 5A mapping 통과 후에만 시작됨.
- [ ] Raw Sources에서 Inbox로 가져오기 -> 처리 -> Raw Sources archive 경로가 실제 vault 자료로 검증됨.

### Optional checks

- [ ] dry-run helper script for manual test preparation (제품 기능 아님).

### Pass criteria

- 사용자가 실제 vault에서 테스트할 수 있고 데이터 삭제 위험을 이해함.

### Fail/block criteria

- reset이 제품 자동 기능처럼 구현되면 fail.

## Verification evidence paths

- `.code-planner/03-build/evidence/phase-1-*`
- `.code-planner/03-build/evidence/phase-2-*`
- `.code-planner/03-build/evidence/phase-3-*`
- `.code-planner/03-build/evidence/phase-4-*`
- `.code-planner/03-build/evidence/phase-5-*`
- `.code-planner/03-build/evidence/phase-6-*`
