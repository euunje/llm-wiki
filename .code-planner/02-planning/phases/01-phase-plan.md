# 01 Phase Plan — LLM Wiki Local

## 전체 phase

| Phase | 이름 | 목표 | 완료 기준 |
|---|---|---|---|
| 1 | CLI Foundation | CLI 기능 구현과 기반 계약 완성 | Markdown 1건 E2E + DB/artifact/sync 통과 |
| 2 | LLM Wiki Quality | LLM 후보 품질, WikiPage, 변환/검색 고도화 | review_route/retry/WikiPage/non-Markdown 품질 검증 |
| 3 | Web Review UI | 단일 관리자 Web Review UI | 승인된 목업 구조 구현 및 prompt settings 작동 |

## Phase 1 — CLI Foundation

# Phase 1 — CLI Foundation

## Purpose

LLM Wiki Local의 1차 목표인 CLI 기능 구현을 완성한다. 이 phase는 최종 wiki 품질보다 자료 처리, 설정, DB, artifact, LLM 연결, sync의 기반을 만드는 단계다.

## User-visible outcome

- 사용자가 로컬에서 `wiki init`으로 프로젝트 구조를 초기화한다.
- Markdown 자료를 CLI로 등록하고 chunk/embedding까지 처리한다.
- LLM endpoint 연결과 JSON/artifact 계약을 확인한다.
- SQLite에 Source/Chunk/Embedding/Job/Artifact 상태가 기록된다.
- `wiki sync`로 Vault와 DB 상태를 수동 확인한다.

## Related mockup

- not_applicable: Phase 1은 CLI 중심 phase이며 UI 목업 대상이 아니다.

## Included features

- Python CLI entrypoint
- `wiki init`
- `wiki settings get/set`
- `wiki doctor`
- `wiki inbox scan`
- `wiki ingest`, `wiki ingest-text`
- `wiki normalize`
- `wiki chunk`
- `wiki embed`
- `wiki models list/test`
- `wiki route get/set`
- `wiki extract-claims` 최소 JSON/artifact 계약
- `wiki validate`, `wiki lint`, `wiki status`, `wiki search` 기본
- `wiki fix`, `wiki retry`, `wiki sync`
- `wiki ask`, `wiki map`, `wiki summarize`, `wiki compile`은 최소 계약/placeholder 수준

## Excluded features

- 실제 LLM wiki 프롬프트 품질 완성
- 실사용 WikiPage 품질
- PDF/Office/HTML/URL 완성 지원
- Web UI
- 자동 file watcher sync

## Tasks

1. Python package와 CLI command router 설계
2. Settings/sample env 구조 설계
3. SQLite schema와 migration 초기 구조 설계
4. Vault/data 폴더 구조 생성 로직 설계
5. Job/AgentRun/Artifact 기록 계약 설계
6. Markdown ingest/normalize/chunk 구현 범위 확정
7. fastembed embedding 저장 계약 확정
8. LLM endpoint 연결 테스트와 JSON schema validation 계약 확정
9. sync 기본 dry-run, 실제 반영은 --apply 정책 적용

## Git checkpoint

- `phase-1-cli-foundation`

## Entry criteria

- `.code-planner/01-ideation-approved.json` 존재
- ADRs/dependencies/git-plan 작성 완료
- Phase 1 feature contract 작성 완료

## Exit criteria

- 샘플 Markdown 1건이 `ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync` 흐름을 통과할 수 있도록 설계/구현됨
- 모든 CLI 명령의 최소 입출력/실패/재실행 계약이 문서화됨
- Web UI 없이도 CLI만으로 상태 확인 가능


## 확정 보정

- Settings 파일 형식: YAML
- `wiki sync`: 기본 dry-run/report, 실제 반영은 `--apply`
- Web Auth secret은 `.env`에 둔 사용자 비밀번호 기반


---

## Phase 2 — LLM Wiki Quality

# Phase 2 — LLM Wiki Quality

## Purpose

Phase 1의 CLI 기반 위에 실제 LLM wiki 품질을 올린다. Claim/Concept/Relation 후보, mapping, WikiPage compile, 비-Markdown 변환을 사람이 검토 가능한 수준으로 만든다.

## User-visible outcome

- LLM이 Source/Chunk에서 Claim 후보를 추출한다.
- Concept/Relation/Mapping 후보가 `review_route`와 함께 저장된다.
- reject + retry instruction 이후 이전 후보가 `superseded`되고 새 후보와 연결된다.
- WikiPage compile preview
- vector/RAG search 확장가 Obsidian Markdown 형식으로 생성된다.
- PDF/Office/HTML/URL 자료가 Markdown으로 변환되어 파이프라인에 들어간다.

## Related mockup

- not_applicable: Phase 2는 주로 schema/prompt/page 품질 phase이다. Web Review 표시는 Phase 3 목업을 참조한다.

## Included features

- LLM 후보 JSON schema 확정
- `review_route` 통합
- `human_decision` 분리
- `retry_instruction` runner/human 메타
- `superseded` 후보 연결
- `propose_relations`의 `new_node candidate_key` 참조 허용
- `extract_claims`, `map_candidates`, `propose_relations`, `detect_claim_conflicts`, `compile_wiki`, `ask` prompt 품질
- prompt test version → test run → confirmed version 흐름
- prompt change logging
- WikiPage compile preview
- vector/RAG search 확장
- `markitdown` adapter 후보를 통한 비-Markdown 변환

## Excluded features

- Web UI 구현 자체
- 다중 사용자 승인
- 승인 전 자동 Vault 반영

## Tasks

1. LLM schema 세부 JSON 필드 확정
2. Validator 규칙 확정
3. review_route enum 최종 확정
4. human_decision/retry_instruction/superseded 저장 구조 확정
5. prompt versioning 저장 위치와 diff/log 정책 확정
6. WikiPage frontmatter/link/claim/source 포함 규칙 확정
7. converter adapter 인터페이스 확정

## Git checkpoint

- `phase-2-llm-wiki-quality`

## Entry criteria

- Phase 1 CLI foundation 완료
- Source/Chunk/Embedding/Artifact 기반 존재
- LLM endpoint 연결 테스트 가능

## Exit criteria

- 동일 Source에 대해 prompt version별 artifact 비교 가능
- rejected 후보 retry 시 superseded 연결 보존
- WikiPage preview 생성 가능
- 비-Markdown 변환 결과가 normalized Markdown으로 저장됨


## 확정 보정

- Prompt 변경 로그: 버전별 전체 prompt 저장 + change note
- 신규 wiki 확정 시 즉시 embedding/index 추가
- 사용자가 필요 시 선택 항목 또는 전체 재인덱싱 가능
- vector/RAG search 확장은 Phase 2 범위에 포함
- 정본 normalized format은 Markdown 유지. MDX는 Web preview/export optional format으로 확정.


---

## Phase 3 — Web Review UI

# Phase 3 — Web Review UI

## Purpose

단일 관리자 사용자가 Web에서 처리 현황을 보고 LLM 후보를 검토하며 병합/신규/retry/prompt 관리를 할 수 있게 한다.

## User-visible outcome

- 로그인 후 대시보드에서 자료 처리 현황과 시스템 상태를 본다.
- Review 화면에서 기존 wiki 유사도 목록, 선택 개념 내용, 신규 개념 batch 카드를 함께 본다.
- 신규 개념을 병합/신규/수정/reject+retry 처리한다.
- 그래프 팝업에서 1-hop 관계와 wiki 내용을 확인한다.
- Web Settings에서 model/prompt를 설정하고 prompt test version을 confirmed version으로 승격한다.

## Related mockup

- Markdown mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.md`
- Canonical HTML mockup: `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
- Legacy HTML mockup: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`은 구현 기준이 아니다.
- PRV feedback: `.code-planner/02-planning/review/phase-3-prv-feedback.md`
- Approval status: approved

## Included features

- Login → Dashboard
- Dashboard status cards
  - 자료 처리 현황
  - 승인 필요
  - pending 항목
  - 오류
  - wiki 개수
  - 시스템 상태
- Review Main
  - 왼쪽: 기존 wiki 유사도 목록, 리스트형
  - 가운데: 선택 개념 내용/의미/aliases/claims/relations
  - 오른쪽: 신규 개념 batch 카드
  - actions: 병합, 신규, 수정, reject reason + retry instruction
  - Wiki compile preview는 필요 시 펼침
- Graph popup
  - 선택 개념 중심 1-hop graph
  - `| graph | wiki 내용 |` 구조
- Settings
  - model 설정
  - prompt test version
  - test run
  - confirm version
  - change logging

## Excluded features

- 다중 사용자 권한
- 협업 승인 워크플로우
- 다중 사용자 메뉴/프로필 관리. 단, PC/Mobile responsive 기본 지원과 Logout의 향후 사용자 메뉴 배치 예약은 Phase 3 범위에 포함한다.
- Web에서 Vault 무제한 직접 편집

## Tasks

1. Web stack 최종 선택
2. Auth 방식 선택
3. Dashboard API/데이터 계약 설계
4. Review candidate query/similarity sort 계약 설계
5. batch merge/new/retry action 계약 설계
6. Graph popup 1-hop query 계약 설계
7. Settings prompt versioning API 계약 설계
8. Mockup 기반 UI 구현 검증 항목 확정

## Git checkpoint

- `phase-3-web-review-ui`

## Entry criteria

- Phase 1 CLI 상태/job/artifact 기반 존재
- Phase 2 review_route/human_decision/retry_instruction schema 존재
- HTML mockup 승인 완료

## Exit criteria

- Dashboard에서 pending/error/review/system status 확인 가능
- Review 화면에서 신규 개념 batch 처리 가능
- Graph popup에서 1-hop 관계와 wiki 내용 확인 가능
- Prompt 변경 이력과 test→confirm 흐름 작동
