# CLI Features

## 1. 목적

CLI는 `LLM Wiki Local`의 자동화 실행 라인이다.

Web UI, Codex, Claude, 로컬 LLM, 사용자의 직접 명령은 모두 같은 CLI 기능 또는 그에 대응하는 API/job을 통해 시스템을 움직인다.

CLI는 다음 원칙을 따른다.

- 모든 실행은 재현 가능해야 한다.
- 모든 실행은 job과 agent run으로 기록되어야 한다.
- 실패 원인과 중간 산출물은 artifact로 남겨야 한다.
- 사람이 보지 않아도 batch 실행이 가능해야 한다.
- Web UI에서 같은 작업을 다시 실행할 수 있어야 한다.

## 2. 기능 영역

```text
init/settings
  -> inbox/raw
  -> normalize/chunk/embed
  -> extract/map/wiki ingest
  -> validate/lint/debug-repair-source-stubs
  -> search/ask/status
```

## 3. 초기화와 설정

### `wiki init`

새 프로젝트를 초기화한다.

필요 기능:

- Obsidian vault 폴더 구조 생성
- SQLite DB 생성
- 기본 schema 생성
- 기본 ontology rule 생성
- 기본 settings 파일 생성
- local LLM 연결 테스트 옵션
- embedding backend 연결 테스트 옵션

초기 생성 폴더 후보:

```text
vault/
  00_inbox/
  10_sources/
  20_claims/
  30_concepts/
  40_wiki/
  90_templates/

data/
  raw/
  normalized/
  artifacts/
```

### `wiki settings get`

현재 설정을 출력한다.

출력 대상:

- vault path
- DB path
- local LLM endpoint
- default chat model
- default embedding model
- chunk size
- ontology schema version
- auto-run policy
- review threshold

### `wiki settings set <key> <value>`

설정을 변경한다.

필요 조건:

- 설정 변경 이력 기록
- 잘못된 key 거부
- 민감 정보는 평문 출력 제한
- Web UI와 같은 settings store 사용

### `wiki doctor`

로컬 환경 상태를 점검한다.

점검 대상:

- vault 경로 존재 여부
- DB 연결 가능 여부
- FTS5 사용 가능 여부
- sqlite-vec 사용 가능 여부
- local LLM endpoint 응답 여부
- embedding model 응답 여부
- schema 파일 존재 여부
- Obsidian 파일과 DB row의 동기화 상태

## 4. Inbox와 Raw 저장 흐름

### `wiki inbox scan`

`vault/00_inbox/` 또는 설정된 inbox 경로를 스캔한다.

필요 기능:

- 새 파일 감지
- 이미 처리된 파일 제외
- 파일 hash 계산
- 중복 후보 탐지
- source 후보 생성
- 처리 대기 job 생성

### `wiki ingest <path|url>`

파일 또는 URL을 시스템에 등록한다.

필요 기능:

- source type 감지
- 원본 파일을 `data/raw/`에 저장
- URL인 경우 HTML snapshot 또는 추출 텍스트 저장
- hash 생성
- Source row 생성
- vault source stub 생성
- normalize job 생성

### `wiki ingest-text`

사용자가 직접 입력한 텍스트를 Source로 저장한다.

필요 기능:

- title 입력 또는 자동 생성
- 텍스트 원본 저장
- source type을 `user_text`로 기록
- Source row 생성
- vault source stub 생성

## 5. 정규화, Chunk, Embedding

### `wiki normalize <source_id>`

원본 자료를 Markdown 또는 plain text로 변환한다.

필요 기능:

- PDF, HTML, Markdown, TXT 처리
- normalized file 저장
- 페이지/섹션 locator 유지
- 실패 시 artifact 저장
- normalize 완료 상태 기록

### `wiki chunk <source_id>`

정규화된 텍스트를 검색과 LLM 처리에 적합한 조각으로 나눈다.

필요 기능:

- chunk size 설정 반영
- overlap 설정 반영
- SourceChunk row 생성
- locator 유지
- token count 기록

### `wiki embed <target>`

SourceChunk, Claim, Concept에 embedding을 생성한다.

지원 target:

- `source:<source_id>`
- `chunk:<chunk_id>`
- `claim:<claim_id>`
- `concept:<concept_id>`
- `all`

필요 기능:

- embedding model 기록
- dimension 기록
- vector 저장
- 기존 embedding 재사용 여부 선택
- sqlite-vec index 갱신

## 6. LLM 작업

### `wiki extract-claims <source_id>`

Source 또는 SourceChunk에서 Claim을 추출한다.

필요 기능:

- chunk별 claim 후보 추출
- JSON schema 기반 출력 강제
- source_id/chunk_id/locator 연결
- confidence 기록
- LLM 원본 응답 artifact 저장
- 검증 실패 시 fix 또는 retry 후보 생성

### `wiki summarize <source_id|concept_id>`

Source 또는 Concept의 요약을 생성한다.

필요 기능:

- source summary 생성
- concept summary 생성
- 기존 요약과 새 요약 비교 artifact 저장

### `wiki link <target>`

Claim과 Concept, Concept와 Concept 사이의 관계 후보를 만든다.

지원 target:

- `claim:<claim_id>`
- `concept:<concept_id>`
- `source:<source_id>`

필요 기능:

- 기존 Concept 후보 검색
- 새 Concept 후보 생성
- relation 후보 생성
- ontology rule 검증
- review 대기 상태로 저장

### `wiki map <source_id>`

새 Source에서 나온 Claim/Concept 후보를 기존 wiki 구조에 매핑한다.

필요 기능:

- 기존 Claim/Concept와 비교
- 중복 후보 탐지
- 충돌 후보 탐지
- merge 후보 생성
- Mapping Review용 diff artifact 생성

### `wiki compile <target>`

승인된 Source, Claim, Concept, Relation을 바탕으로 Obsidian 문서를 생성하거나 갱신한다.

지원 target:

- `concept:<concept_id>`
- `source:<source_id>`
- `all`

필요 기능:

- WikiPage Markdown 생성
- YAML frontmatter 생성
- 관련 Claim과 Source 링크 삽입
- 기존 파일과 diff 생성
- review 상태에 따라 자동 반영 또는 승인 대기

## 7. 검증, Lint, Fix

### `wiki validate <target>`

schema와 데이터 무결성을 검증한다.

검증 대상:

- Source schema
- Claim schema
- Concept schema
- Relation schema
- AgentRun schema
- Markdown frontmatter
- artifact JSON

### `wiki lint <target>`

wiki 품질 규칙을 검사한다.

검사 항목:

- source 없는 claim
- locator 없는 claim
- broken Obsidian link
- 허용되지 않은 predicate
- domain/range 위반
- 중복 alias
- orphan concept
- review 없이 compile된 항목
- 오래된 embedding
- DB와 vault 파일 불일치

### `wiki debug-repair-source-stubs [target]`

디버그/운영 복구용 명령이다. DB에는 source row가 있는데
`vault/10_Wiki/sources/<source_id>.md` stub 파일이 누락된 경우에만
복구 계획을 출력하거나 `--apply`로 안전 복구한다.

범위:

- source stub markdown 복구
- 기본 frontmatter 재작성
- 원문/claim/candidate 의미 변경 없음

`fix`라는 일반 명령명은 제거했다. 후보 retry는 CLI가 아니라 Web review/API 흐름에서 처리한다.

## 8. 모델 연결과 라우팅

### `wiki models list`

사용 가능한 모델과 provider를 출력한다.

대상:

- local chat model
- local embedding model
- Codex adapter
- Claude adapter
- future provider

### `wiki models test <model_id>`

모델 연결을 테스트한다.

필요 기능:

- endpoint healthcheck
- sample prompt 실행
- JSON 출력 가능성 테스트
- embedding dimension 확인

### `wiki route get`

작업별 모델 라우팅 설정을 출력한다.

예시:

```text
normalize: deterministic
extract_claims: google/gemma-4-26b-a4b-qat
link_concepts: google/gemma-4-26b-a4b-qat
compile_wiki: local_or_codex
healthcheck: local_or_claude
```

### `wiki route set <task_type> <model_id>`

작업별 모델을 변경한다.

필요 조건:

- task_type 검증
- model capability 검증
- 변경 이력 기록

## 9. 상태와 조회

### `wiki status`

현재 시스템 상태를 보여준다.

출력 항목:

- 처리 대기 job 수
- 실패 job 수
- review 대기 claim 수
- review 대기 mapping 수
- source 수
- concept 수
- embedding index 상태
- LLM 연결 상태

### `wiki search <query>`

기본 검색을 수행한다.

검색 방식:

- FTS
- metadata filter
- tag filter
- source/concept/claim type filter

### `wiki ask <query>`

LLM 기반 조회를 수행한다.

흐름:

```text
query
  -> FTS 후보 검색
  -> vector 후보 검색
  -> ontology relation 확장
  -> review_status 필터링
  -> LLM 답변
  -> 근거 Source/Claim 표시
```

## 10. Job 모델

CLI 명령은 내부적으로 job을 만들 수 있다.

기본 job 필드:

- `id`
- `job_type`
- `target_type`
- `target_id`
- `status`
- `created_at`
- `started_at`
- `finished_at`
- `input_refs`
- `output_refs`
- `error`
- `retry_count`

job status:

- `queued`
- `running`
- `succeeded`
- `failed`
- `needs_review`
- `cancelled`

## 11. 우선 구현 범위

v0에서 필요한 CLI:

```text
wiki init
wiki doctor
wiki settings get
wiki inbox scan
wiki ingest
wiki ingest-text
wiki normalize
wiki chunk
wiki validate
wiki lint
wiki status
```

v1에서 추가할 CLI:

```text
wiki embed
wiki extract-claims
wiki search
wiki debug-repair-source-stubs
```

Web/API 전용 또는 제거된 CLI:

```text
link/map/compile: 현재 별도 top-level CLI가 아니라 ingest/Web pipeline 내부 단계
fix: debug-repair-source-stubs로 명칭 축소
retry/sync: CLI에서 제거; retry는 Web review/API 흐름에서 처리
```

v2에서 추가할 CLI:

```text
wiki ask
wiki models list
wiki models test
wiki route get
wiki route set
wiki healthcheck
```

