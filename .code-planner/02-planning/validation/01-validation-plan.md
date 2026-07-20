# 01 Validation Plan — LLM Wiki Local

## Canonical validation plan

이 파일은 Build agent 입력 게이트가 요구하는 canonical validation path다. 원본 validation 문서는 `.code-planner/02-planning/validation/validation-plan.md`이며, CLI E2E 세부 계획은 `.code-planner/02-planning/validation/cli-e2e-test-plan.md`다.

---

# Phase별 validation plan

# Validation Plan — LLM Wiki Local

## 목적

이 문서는 Build 단계에서 각 Phase가 “끝났다”고 판단하기 위한 검증 목표를 정의한다.

검증 상태는 다음 중 하나다.

- `pass`: 요구 검증을 통과했다.
- `fail`: 요구 검증을 시도했지만 실패했다.
- `blocked`: 외부 조건, 미구현 dependency, 설정 누락 등으로 검증할 수 없다.

검증 중요도는 다음 중 하나다.

- `required`: phase 완료 전에 반드시 통과해야 한다.
- `optional`: 통과하면 좋지만 phase 완료를 막지는 않는다.
- `not_applicable`: 해당 phase에는 적용하지 않는다.

---

# 공통 검증 기준

## Required

- [ ] CLI/API/Web 실행 결과는 대화 기억이 아니라 파일/DB/artifact에 남는다.
- [ ] 실패는 error artifact 또는 상태 report로 확인 가능하다.
- [ ] sample env 또는 settings 예시가 실제 실행 흐름과 모순되지 않는다.
- [ ] 실제 secret은 repository에 포함하지 않는다.
- [ ] phase별 exit criteria가 문서와 일치한다.

## Optional

- [ ] 성능 지표가 baseline으로 기록된다.
- [ ] 로그 포맷이 구조화되어 있다.

## Evidence path

- Build 단계에서 phase별 evidence는 다음 위치 중 하나에 남긴다.
  - `data/artifacts/`
  - CLI JSON output
  - test report
  - PRV/mockup approval 기록
  - `.code-planner/02-planning/validation/`

---

# Phase 1 — CLI Foundation

## Required checks

### 기능 동작

- [ ] `wiki init`이 Vault/data/settings/DB/schema를 생성한다.
- [ ] `wiki init`은 재실행해도 기존 데이터를 망가뜨리지 않는다.
- [ ] `wiki settings get/set`이 허용 key를 조회/변경한다.
- [ ] 민감 정보는 기본 출력에서 마스킹된다.
- [ ] `wiki doctor`가 로컬 경로, DB, FTS5/sqlite-vec, settings/env 상태를 report한다.
- [ ] `wiki ingest <markdown>`이 Source row, raw file 또는 source ref, vault source stub, normalize job을 만든다.
- [ ] 1차에서 PDF/Office/HTML/URL 입력은 명확한 unsupported/phase-2 안내를 반환한다.
- [ ] `wiki normalize`가 Markdown normalized file과 상태를 남긴다.
- [ ] `wiki chunk`가 SourceChunk row와 locator/token_count를 남긴다.
- [ ] `wiki embed`가 fastembed 기본 모델로 embedding을 생성하고 model/dimension/target을 저장한다.
- [ ] `wiki models test`가 chat/embedding 연결 성공 또는 실패 artifact를 남긴다.
- [ ] `wiki extract-claims` 최소 계약이 JSON/artifact 검증까지 수행한다.
- [ ] `wiki validate/lint/status/search`가 최소 report를 제공한다.
- [ ] `wiki retry/fix/sync`가 최소 계약을 제공한다.

### 공통 CLI 계약

- [ ] 각 CLI 명령은 exit code 기준을 가진다.
- [ ] 각 CLI 명령은 `--json` 출력 여부가 정의되어 있다.
- [ ] job/run id 또는 not_applicable 사유가 출력된다.
- [ ] 실패 시 error artifact 또는 machine-readable report가 남는다.
- [ ] dry-run/apply가 필요한 명령은 기본 정책이 명확하다.

### 데이터/상태

- [ ] Source, SourceChunk, Embedding, Job, AgentRun, Artifact의 최소 row가 연결된다.
- [ ] 중복 ingest/hash 정책이 동작한다.
- [ ] 수동 `wiki sync`가 Vault와 DB 차이를 report한다.

## Optional checks

- [ ] sqlite-vec 실제 index search까지 smoke test한다.
- [ ] embedding cache 위치와 모델 다운로드 상태를 report한다.
- [ ] CLI 명령별 help text snapshot을 보관한다.

## Not applicable

- Web UI 시각 검증
- PDF/Office/HTML/URL 변환 품질
- 실제 WikiPage 품질

## Pass 기준

샘플 Markdown 1건이 다음 E2E를 통과하면 Phase 1 pass로 본다.

```text
ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync
```

## Fail 기준

- Source/Chunk/Embedding/Artifact 중 하나라도 추적 불가능하면 fail.
- 실패가 사용자에게 보이지 않고 조용히 무시되면 fail.
- 1차 제외 입력(PDF/URL 등)을 잘못 처리한 것처럼 보이면 fail.

## Blocked 기준

- Python 실행 환경 미준비
- SQLite 기본 기능 사용 불가
- fastembed/model 설치 불가
- LLM endpoint가 필요한 검증에서 sample env가 제공되지 않음

---

# Phase 2 — LLM Wiki Quality

## Required checks

### LLM schema

- [ ] LLM 후보 출력은 영구 ID를 만들지 않는다.
- [ ] LLM 후보 출력은 Vault Markdown을 직접 수정하지 않는다.
- [ ] `review_route`가 후보 검토 흐름을 표현한다.
- [ ] 별도 `needs_human_review` 배열을 쓰지 않고 후보별 `review_route/review_reason/related_candidate_keys` 정책과 일치한다.
- [ ] 사람 결정은 `human_decision`에 기록된다.
- [ ] `retry_instruction`은 runner/human 메타로 저장된다.
- [ ] retry 후 이전 후보는 `superseded`로 표시되고 새 후보와 연결된다.
- [ ] `propose_relations`는 같은 응답의 `new_node candidate_key` 참조 규칙을 검증한다.

### Prompt/versioning

- [ ] task별 prompt version이 기록된다.
- [ ] prompt는 버전별 전체 내용과 change note를 저장한다.
- [ ] test version → test run → confirmed version 흐름이 동작한다.
- [ ] AgentRun은 prompt version을 참조한다.
- [ ] prompt 변경점 logging이 남는다.
- [ ] 신규 wiki 확정 시 해당 항목이 즉시 embedding/index에 추가된다.
- [ ] 선택 항목 재인덱싱과 전체 재인덱싱 경로가 검증된다.
- [ ] vector/RAG search 확장 smoke test가 통과한다.

### 품질 기능

- [ ] `extract_claims`가 evidence가 있는 Claim 후보를 만든다.
- [ ] `map_candidates`가 기존 node 후보 allow-list 안에서 mapping 후보를 만든다.
- [ ] `propose_relations`가 evidence_claim_keys를 가진 relation 후보를 만든다.
- [ ] `detect_claim_conflicts`가 근거 있는 conflict 후보만 만든다.
- [ ] WikiPage compile preview가 YAML frontmatter, Claim/Source/Concept 링크를 포함한다.
- [ ] 승인 전 자동 Vault 반영이 일어나지 않는다.

### Non-Markdown conversion

- [ ] converter adapter 인터페이스가 정의된다.
- [ ] PDF/Office/HTML/URL 변환 실패 시 error artifact가 남는다.
- [ ] 변환 성공 시 normalized Markdown으로 들어온다.

## Optional checks

- [ ] prompt version별 결과 diff를 UI 없이 CLI로 볼 수 있다.
- [ ] relation/conflict 후보의 false positive를 수동 sample로 기록한다.
- [ ] `wiki ask` 답변에 사용된 Claim/Source가 표시된다.

## Not applicable

- Web Review 실제 UI 구현
- 다중 사용자 승인

## Pass 기준

- 동일 Source에서 prompt version별 artifact 비교가 가능하다.
- reject + retry instruction → superseded → 새 후보 연결이 재현된다.
- WikiPage compile preview가 Obsidian Markdown 형식으로 생성된다.
- 비-Markdown 입력이 converter adapter를 통해 normalized Markdown으로 들어온다.

## Fail 기준

- LLM이 영구 ID를 생성했는데 validator가 통과시키면 fail.
- evidence 없는 Claim/Relation이 정상 후보로 저장되면 fail.
- 사람 결정과 LLM 후보 라우팅이 같은 필드에 섞이면 fail.
- prompt 변경 기록이 남지 않으면 fail.

## Blocked 기준

- LLM endpoint/sample env 부재
- JSON schema/validator 미정
- converter dependency 설치 또는 입력 sample 부재

---

# Phase 3 — Web Review UI

## Required checks

### Mockup/UX match

- [x] Phase 3 HTML mockup이 생성되었다.
- [x] PRV Tailnet review가 열렸다.
- [x] 사용자가 목업을 확인하고 승인했다.
- [ ] Build 결과 UI가 승인된 mockup의 핵심 구조와 일치한다.

### Dashboard

- [ ] FastAPI + uvicorn server가 로컬에서 실행된다.
- [ ] Jinja2 template 기반 Dashboard가 렌더링된다.
- [ ] Vanilla JS 기반 Review interaction이 동작한다.
- [ ] `.env` 관리자 비밀번호 기반 login/session이 동작한다.
- [ ] 로그인 후 Dashboard로 진입한다.
- [ ] Dashboard가 자료 처리 현황, 승인 필요, pending, 오류, wiki 개수, 시스템 상태를 보여준다.
- [ ] 실패/경고 상태가 사용자에게 명확히 보인다.

### Review Main

- [ ] 왼쪽은 기존 wiki 유사도 목록을 리스트형으로 보여준다.
- [ ] 가운데는 선택한 기존 개념의 의미/aliases/claims/relations를 보여준다.
- [ ] 오른쪽은 신규 개념 batch 카드를 보여준다.
- [ ] 사용자가 신규 개념을 병합/신규/수정 처리할 수 있다.
- [ ] `reject reason + retry instruction`을 입력할 수 있다.
- [ ] Wiki compile preview는 필요할 때 펼칠 수 있다.
- [ ] 펼친 preview가 현재 mapping/merge 결정의 영향을 반영한다.
- [ ] batch 처리에서 실수 방지 또는 확인 흐름이 있다.

### Graph popup

- [ ] 선택 개념 중심 1-hop graph를 보여준다.
- [ ] graph node 클릭 시 wiki 내용이 표시된다.
- [ ] 전체 graph 탐색으로 과도하게 확장되지 않는다.

### Settings

- [ ] Web Auth는 `.env` 사용자 비밀번호 기반으로 동작한다.
- [ ] Web Settings에서 model 설정을 볼 수 있다.
- [ ] prompt test version을 저장할 수 있다.
- [ ] test run 후 confirmed version으로 승격할 수 있다.
- [ ] prompt 변경점 logging이 남는다.
- [ ] 신규 wiki 확정 시 해당 항목이 즉시 embedding/index에 추가된다.
- [ ] 선택 항목 재인덱싱과 전체 재인덱싱 경로가 검증된다.
- [ ] vector/RAG search 확장 smoke test가 통과한다.

## Optional checks

- [ ] keyboard shortcut 또는 빠른 batch action을 제공한다.
- [ ] review filter/saved view를 제공한다.
- [ ] prompt rollback을 제공한다.

## Not applicable

- 다중 사용자 권한
- 다중 사용자 메뉴/프로필 관리. 단, PC/Mobile responsive 기본 지원과 Logout의 향후 사용자 메뉴 배치 예약은 Phase 3 범위에 포함한다.
- Web에서 Vault 전체 직접 편집

## Pass 기준

- 승인된 HTML mockup의 핵심 정보 구조가 실제 UI에 유지된다.
- Review에서 신규 개념 여러 개를 batch 처리할 수 있다.
- graph popup에서 1-hop 관계와 wiki 내용을 확인할 수 있다.
- prompt test → confirm 흐름과 변경 로그가 동작한다.

## Fail 기준

- Review UI가 단순 좌우 비교로 축소되어 기존 wiki 목록/선택 개념/신규 batch 카드 구조를 잃으면 fail.
- reject+retry instruction 흐름이 없으면 fail.
- prompt 변경 이력이 남지 않으면 fail.

## Blocked 기준

- Phase 2의 review_route/human_decision/retry_instruction schema 미구현
- Web stack 또는 auth 방식 미결정
- Dashboard/Review API 계약 미구현

---

# 최종 Build-ready validation checkpoint

Build handoff 전 다음을 확인한다.

- [ ] Phase 1~3의 required checks가 모두 pass 또는 명시적 user-approved known issue 상태다.
- [ ] approved mockup 경로가 handoff에 포함된다.
- [ ] LLM schema 결정이 handoff에 포함된다.
- [ ] Git checkpoint 계획이 handoff에 포함된다.
- [ ] secrets/sample env 구분이 명확하다.


# Crosscheck 보정 반영

- Settings 파일 형식: YAML
- Sync 정책: 기본 dry-run, 반영은 `--apply`
- Web Auth: `.env` 사용자 비밀번호 기반
- Prompt log: 버전별 전체 저장 + change note
- Embedding/reindex: 신규 wiki 확정 시 즉시 추가, 선택/전체 재인덱싱 지원
- Phase 2 vector/RAG search 확장 검증 추가
- Phase 3 Wiki compile preview 펼침 검증 추가
- MDX 변환 여부는 사용자 추가 확인 필요


# CLI E2E 보강 문서

- 기능별 E2E 테스트 플랜: `.code-planner/02-planning/validation/cli-e2e-test-plan.md`
- init 폴더 구조 계약: `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`


---

# CLI E2E Test Plan

# CLI E2E Test Plan — Phase 1

## 목적

Build에서 구현되어야 할 목표를 기능별 E2E 테스트로 명확히 한다.

## 공통 E2E 조건

- 모든 테스트는 임시 workspace에서 실행한다.
- 실제 secret은 사용하지 않는다.
- LLM 연결 테스트는 sample env 또는 test endpoint를 사용한다.
- 파일/DB 변경 명령은 결과 artifact 또는 report를 남긴다.
- `--json` 모드는 핵심 명령에서 smoke test한다.

---

## E2E-01. Init

```text
wiki init --path ./tmp-wiki
```

기대 결과:

- `vault/00_Inbox`, `vault/10_Wiki`, `vault/20_Review`, `vault/80_Raws`, `vault/90_Settings` 생성
- `data/wiki.sqlite`, `data/raw`, `data/normalized`, `data/artifacts` 생성
- YAML settings 생성
- 재실행 시 idempotent

Pass:

- 필수 폴더/DB/settings가 존재하고 재실행해도 손상 없음

---

## E2E-02. Markdown ingest pipeline

```text
wiki ingest samples/rag.md
wiki normalize <source_id>
wiki chunk <source_id>
wiki status --json
```

기대 결과:

- Source row 생성
- normalized Markdown 생성
- SourceChunk row 생성
- status에서 source/chunk 상태 확인

Pass:

- Source → normalized → chunked 상태 전이가 DB와 artifact로 확인됨

---

## E2E-03. Unsupported input guard

```text
wiki ingest samples/paper.pdf
wiki ingest https://example.com/article
```

기대 결과:

- Phase 1에서는 unsupported 또는 Phase 2 안내 반환
- 처리된 것처럼 Source를 잘못 만들지 않음

Pass:

- 명확한 error/warn과 exit code가 있음

---

## E2E-04. Embedding

```text
wiki embed source:<source_id>
```

기대 결과:

- chunk embedding 생성
- model name, dimension, target 저장
- sqlite-vec index 갱신 또는 갱신 예정 report

Pass:

- embedding row와 dimension 확인 가능

---

## E2E-05. LLM 연결 테스트

```text
wiki models list
wiki models test <chat_model_id>
wiki models test <embedding_model_id>
```

기대 결과:

- 등록된 provider/model 표시
- chat model sample prompt 응답 확인
- embedding model sample vector/dimension 확인
- 성공/실패 artifact 저장

Pass:

- LLM 연결 테스트 위치가 `wiki models test`로 명확함
- 실패 시 endpoint/auth/model 오류가 report됨

---

## E2E-06. LLM candidate contract

```text
wiki extract-claims <source_id> --json
```

Phase 1 기대 결과:

- 실제 품질보다 JSON/artifact 계약 검증
- JSON parse/schema validation 수행
- 실패 시 error artifact와 retry 후보 생성

Pass:

- artifact path, run id, validation result가 출력됨

---

## E2E-07. Sync dry-run/apply

```text
wiki sync
wiki sync --apply
```

기대 결과:

- 기본 `wiki sync`는 read-only dry-run report
- `--apply`에서만 반영
- 반영 결과 artifact 저장

Pass:

- dry-run에서 파일/DB 변경 없음
- apply 후 변경 요약과 artifact 존재

---

## E2E-08. Retry with instruction

```text
wiki retry <run_id> --instruction "태그 범위를 더 좁혀 다시 판단"
```

기대 결과:

- 이전 후보는 `superseded`
- 새 run 생성
- retry_instruction이 run metadata에 기록
- 새 artifact 생성

Pass:

- 이전 후보와 새 후보 연결 추적 가능

---

## E2E-09. Compile placeholder

```text
wiki compile concept:<concept_id>
```

Phase 1 기대 결과:

- 기본 초안 또는 placeholder WikiPage preview 생성
- 실사용 품질은 Phase 2

Pass:

- preview path 또는 artifact가 생성됨

---

## E2E-10. Healthcheck

```text
wiki healthcheck --json
```

기대 결과:

- DB/Vault 불일치
- stale embedding
- orphan concept
- broken link
- failed jobs 누적 상태 report

Pass:

- 시스템 데이터 상태를 한 번에 확인 가능

---

# Phase 1 완료 기준

다음이 모두 pass이면 Phase 1 CLI foundation 완료로 본다.

- E2E-01 Init
- E2E-02 Markdown ingest pipeline
- E2E-04 Embedding
- E2E-05 LLM 연결 테스트
- E2E-06 LLM candidate contract
- E2E-07 Sync dry-run/apply
- 공통 CLI 계약: `--json`, exit code, artifact/report
