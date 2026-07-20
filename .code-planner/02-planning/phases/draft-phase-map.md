# Draft Phase Map — LLM Wiki Local

## 수정 방향

이전 초안은 구현 단위가 너무 잘게 쪼개져 있었다. 사용자의 방향에 맞춰 **큰 phase는 3개**로 고정하고, 각 phase 내부에 **설계 계약(contracts)** 을 나누어 작성한다.

즉, Build 단계에서는 다음처럼 본다.

```text
큰 Phase = 사용자가 이해하고 검수할 수 있는 제품 단계
설계 계약 = phase 안에서 구현자가 지켜야 할 기능/API/schema/검증 단위
```

## 전체 Phase

| Phase | 이름 | 핵심 목표 | 사용자 기준 완료감 |
|---|---|---|---|
| Phase 1 | CLI Foundation | CLI 기능 전체의 기반 구현 | Markdown 1건이 CLI로 처리되고 DB/artifact/sync까지 이어짐 |
| Phase 2 | LLM Wiki Quality | LLM 프롬프트, schema, WikiPage, 비-Markdown 품질 구현 | 실제 wiki 후보와 page 결과가 검토 가능한 품질로 나옴 |
| Phase 3 | Web Review UI | Dashboard, Review, Settings UI 구현 | 웹에서 처리 현황을 보고 병합/신규/retry/prompt 관리를 수행 |

---

# Phase 1 — CLI Foundation

## 목적

1차 목표는 **CLI 기능 구현**이다.  
이 단계의 목표는 최종 wiki 품질이 아니라, 이후 LLM wiki 기능이 올라갈 수 있는 기반을 완성하는 것이다.

## 사용자에게 보이는 결과

- `wiki init`으로 프로젝트 구조를 만든다.
- Markdown 자료를 넣고 ingest/normalize/chunk/embed 흐름을 실행한다.
- LLM 연결과 JSON/artifact 계약을 검증한다.
- SQLite에 Source/Chunk/Embedding/Job/Artifact 상태가 남는다.
- `wiki sync`로 Vault와 DB 상태를 수동 비교/반영한다.

## 포함 기능

- Python CLI entrypoint
- Settings/sample env
- Vault/data 폴더 구조
- SQLite schema
- Job/AgentRun/Artifact 기록
- Markdown ingest/normalize/chunk
- fastembed embedding
- LLM endpoint 연결 테스트
- LLM JSON/artifact 계약 검증
- validate/lint/status/search 기본
- retry/fix/sync 기본
- ask/map/summarize/compile은 최소 계약 또는 placeholder까지

## 제외 기능

- 실제 LLM wiki 프롬프트 품질 완성
- 실사용 WikiPage 품질
- PDF/Office/HTML/URL 완성 지원
- Web UI
- 자동 file watcher sync

## 설계 계약

### Contract 1. CLI 공통 실행 계약

모든 CLI 명령은 다음을 가져야 한다.

- `--json` 출력 옵션
- 명확한 exit code
- job/run id 출력
- artifact 경로 출력
- dry-run 가능 여부 명시
- 같은 입력 재실행 시 idempotency 정책
- 실패 시 error artifact 기록

### Contract 2. Settings & Environment 계약

- 설정은 Web UI와 공유 가능한 store를 사용한다.
- 실제 secret은 commit하지 않는다.
- sample env에는 LLM endpoint, chat model, embedding backend/model, vault path, DB path를 포함한다.
- LLM provider는 고정하지 않는다.

### Contract 3. Source Pipeline 계약

Markdown Source는 다음 상태를 거친다.

```text
raw → normalized → chunked → embedded
```

각 단계는 DB row, 상태, artifact 또는 file path를 남긴다.

### Contract 4. LLM Candidate 계약 — 최소

Phase 1에서는 LLM 품질보다 계약 검증이 중요하다.

- JSON parse 가능
- schema validation 가능
- artifact 저장
- 실패 시 retry 후보 생성
- 모델 출력이 Vault를 직접 수정하지 않음

### Contract 5. Sync 계약

- 1차는 수동 `wiki sync`만 제공한다.
- 자동 watcher는 제외한다.
- sync는 최소한 Vault와 DB의 차이를 report해야 한다.
- 실제 반영은 dry-run/confirm 정책을 planning에서 더 구체화한다.

## 예상 검증

- 샘플 Markdown 1건이 다음 흐름을 통과한다.

```text
ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync
```

- 실패한 LLM JSON은 error artifact를 남긴다.
- 같은 Markdown을 다시 ingest했을 때 중복/hash 정책이 작동한다.

## Git checkpoint

- `phase-1-cli-foundation`

---

# Phase 2 — LLM Wiki Quality

## 목적

CLI 기반 위에서 실제 LLM wiki 품질을 만든다.

이 phase는 “명령이 돈다”를 넘어서, LLM이 만든 Claim/Concept/Relation 후보와 WikiPage가 사람이 검토할 만한 품질이 되게 하는 단계다.

## 사용자에게 보이는 결과

- LLM이 Source/Chunk에서 Claim 후보를 추출한다.
- 신규 Concept/Relation/Mapping 후보가 생성된다.
- 후보는 `review_route`에 따라 검토 흐름으로 분류된다.
- WikiPage compile preview가 생성된다.
- PDF/Office/HTML/URL 자료도 Markdown으로 변환되어 파이프라인에 들어간다.

## 포함 기능

- 실제 extract-claims prompt 품질
- mapping/linking prompt 품질
- relation/conflict 후보 품질
- WikiPage compile 품질
- `wiki ask` 실제 답변 품질
- vector/RAG search 확장
- PDF/Office/HTML/URL 변환
- `markitdown` converter adapter 후보
- prompt versioning
- prompt change logging

## 제외 기능

- Web UI 구현 자체
- 다중 사용자 승인 워크플로우
- 자동으로 지식을 승인/반영하는 정책

## 설계 계약

### Contract 1. LLM Schema 계약

LLM은 후보만 제안한다.

- 영구 ID 생성 금지
- Vault 직접 수정 금지
- 사람 결정 출력 금지
- 후보 출력은 JSON envelope
- 후보의 검토 흐름은 `review_route`로 통합
- 사람 결정은 `human_decision`
- retry 지시는 `retry_instruction` 메타로 별도 저장
- retry 후 이전 후보는 `superseded`로 표시하고 새 후보와 연결

### Contract 2. Review Route 계약

초기 후보:

- `normal_review`
- `needs_merge_decision`
- `needs_retry`
- `conflict_flag`

`needs_human_review` 배열은 별도로 두지 않고, 후보별 `review_route`, `review_reason`, `related_candidate_keys`로 표현한다.

### Contract 3. Prompt Version 계약

- task별 prompt를 버전관리한다.
- 변경점 logging을 남긴다.
- AgentRun에는 prompt version을 기록한다.
- Web Settings에서 prompt 설정/변경/로그 확인이 가능해야 한다.

### Contract 4. Converter 계약

- 비-Markdown 입력은 converter adapter를 통해 Markdown normalized file로 들어온다.
- `markitdown`은 후보 dependency로 둔다.
- 변환 실패는 artifact와 error로 남긴다.

### Contract 5. WikiPage Compile 계약

- WikiPage는 Claim/Source/Concept 링크를 포함한다.
- YAML frontmatter를 포함한다.
- 기존 파일과 diff 또는 preview를 제공한다.
- 승인 전 자동 반영은 하지 않는다.

## 예상 검증

- 동일 Source에 대해 prompt version별 결과 artifact를 비교할 수 있다.
- reject + retry instruction 후 이전 후보가 `superseded`되고 새 후보와 연결된다.
- PDF/HTML 등 비-Markdown 입력이 Markdown normalized file로 변환된다.
- WikiPage preview가 Obsidian Markdown 형식으로 생성된다.

## Git checkpoint

- `phase-2-llm-wiki-quality`

---

# Phase 3 — Web Review UI

## 목적

단일 관리자 사용자가 Web에서 처리 현황을 보고, LLM 후보를 검토하고, 병합/신규/retry/prompt 관리를 할 수 있게 한다.

## 사용자에게 보이는 결과

- 로그인 후 대시보드에서 전체 상태를 본다.
- Review 화면에서 신규 개념과 기존 wiki 항목을 비교한다.
- 여러 신규 개념을 batch 처리한다.
- 기존 wiki 그래프를 1-hop으로 확인한다.
- reject reason + retry instruction을 입력해 재시도한다.
- Web Settings에서 model/prompt 설정과 prompt 버전 변경점을 관리한다.

## 포함 기능

- 로그인 → 대시보드
- Dashboard
  - 자료 처리 현황
  - 승인 필요
  - pending 항목
  - 오류
  - wiki 개수
  - 시스템 상태
- Review 화면
  - 왼쪽: 기존 wiki 유사도 목록, 카드형 아님
  - 가운데: 선택한 기존 개념 내용/의미
  - 오른쪽: 신규 개념 batch 카드
  - 액션: 병합, 신규, 수정, reject reason + retry with instruction
  - Wiki compile preview는 필요할 때 펼침
- Graph popup
  - 선택 개념 중심 1-hop graph
  - `| 그래프 | wiki 내용 |` 구조
  - 노드 클릭 시 wiki 내용 표시
- Web Settings
  - model 설정
  - prompt 설정
  - prompt version 관리
  - 변경점 logging

## 제외 기능

- 다중 사용자 권한
- 협업 승인 워크플로우
- 다중 사용자 메뉴/프로필 관리. 단, PC/Mobile responsive 기본 지원과 Logout의 향후 사용자 메뉴 배치 예약은 Phase 3 범위에 포함한다.
- Web UI에서 직접 Vault를 무제한 편집하는 기능

## 설계 계약

### Contract 1. Dashboard 계약

Dashboard는 상태를 “처리 가능성” 중심으로 보여준다.

- 지금 처리해야 할 것
- 실패한 것
- 승인 필요한 것
- 시스템이 정상인지

### Contract 2. Review UX 계약

Review는 단순 좌우 비교가 아니다.

```text
왼쪽: 기존 wiki 목록       | 가운데: 선택한 기존 개념 내용       | 오른쪽: 신규 개념 후보
유사도 순 리스트           | 의미/aliases/연결/근거             | batch 카드 + 병합/신규
그래프보기 팝업            |                                   | reject+retry
```

### Contract 3. Graph Popup 계약

- 기본은 1-hop 관계만 보여준다.
- 그래프 노드를 누르면 오른쪽/아래에 wiki 내용을 표시한다.
- 복잡한 전체 graph는 초기 범위가 아니다.

### Contract 4. Settings/Prompt 계약

- prompt는 task별로 설정 가능해야 한다.
- prompt version과 변경 로그가 남아야 한다.
- model setting과 prompt setting은 Web에서 접근 가능해야 한다.

### Contract 5. 목업 검토 계약

Planning Stage 4에서 HTML 목업을 만들고 검토한다.

필수 목업:

- Dashboard
- Review main screen
- Graph popup
- Web Settings prompt versioning

## 예상 검증

- 대시보드에서 pending/error/review/system status를 확인할 수 있다.
- Review에서 신규 개념 여러 개를 batch 처리할 수 있다.
- 그래프 팝업에서 1-hop 관계와 wiki 내용을 확인할 수 있다.
- prompt 변경 이력이 남는다.

## Git checkpoint

- `phase-3-web-review-ui`

---

# Hardening 설명과 배치

## Hardening이란?

Hardening은 “새 기능”이라기보다, 만든 기능을 실제로 오래 쓰기 위해 단단하게 만드는 작업이다.

쉽게 말하면 다음을 확인하는 것이다.

- DB가 꼬였을 때 알 수 있는가?
- 중간에 실패한 job을 다시 돌릴 수 있는가?
- 오래된 embedding을 찾아낼 수 있는가?
- Vault 파일과 DB가 서로 다르면 알려주는가?
- 설정이나 schema가 바뀌어도 기존 데이터를 망가뜨리지 않는가?
- 백업/복구할 수 있는가?

## 배치 결정

Hardening은 별도 큰 phase로 두지 않는다.  
대신 각 phase의 검증/완료 조건에 포함한다.

- Phase 1: CLI 실패, 중복, idempotency, DB/schema 기본 안정성
- Phase 2: LLM 실패, JSON 오류, retry, prompt version, superseded 연결
- Phase 3: Web Review 오류, batch 처리 실패, prompt 변경 로그, graph preview 안정성

필요하면 Build 후반에 “stabilization checkpoint”로 모아 검수한다.

---

# Stage 4로 넘길 항목

다음 단계에서는 phase별 feature 계약과 목업을 작성한다.

우선순위:

1. Phase 1 CLI feature contract
2. Phase 2 LLM schema/prompt/page contract
3. Phase 3 Web Review mockup + feature contract

Web UI 목업은 최종 approval 전에 HTML로 만들어 검토해야 한다.
