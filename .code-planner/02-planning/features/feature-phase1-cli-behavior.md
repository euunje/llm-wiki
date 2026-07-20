# CLI 기능별 동작 명세 — Phase 1

## 목적

이 문서는 Build 단계에서 CLI 기능을 구현할 때 각 명령이 어떤 입력을 받고, 어떤 처리를 하며, 어떤 결과를 남겨야 하는지 명확히 하기 위한 명세다.

## 공통 동작 원칙

모든 CLI 명령은 가능한 범위에서 다음 공통 계약을 따른다.

| 항목 | 동작 |
|---|---|
| `--json` | 사람이 읽는 출력 대신 machine-readable JSON을 출력한다. |
| exit code | 성공은 `0`, 사용자 입력 오류는 `2`, 실행 실패는 `1`, 외부 의존성 실패는 `3`처럼 구분한다. 세부값은 Build에서 확정한다. |
| job/run id | 작업성 명령은 `job_id` 또는 `run_id`를 출력한다. 단순 조회 명령은 not_applicable 가능. |
| artifact | LLM 응답, 실패 로그, diff, validation report는 artifact 경로를 남긴다. |
| dry-run | 파일/DB를 변경할 수 있는 명령은 dry-run 가능 여부를 명시한다. |
| idempotency | 같은 입력을 다시 실행했을 때 중복 생성/덮어쓰기/재사용 정책을 명확히 한다. |
| error report | 실패 시 조용히 종료하지 않고 원인과 다음 조치를 출력한다. |

---

## 명령별 동작

### `wiki init`

- 입력: 프로젝트 경로 또는 기본 현재 경로
- 동작:
  - 사전 정의된 Vault/data 폴더 구조 생성
  - Vault: `00_Inbox`, `10_Wiki`, `20_Review`, `80_Raws`, `90_Settings`
  - data: `raw`, `normalized`, `artifacts`, `exports`, `cache`
  - SQLite DB 생성
  - 초기 schema 생성
  - YAML settings 파일 생성
  - 필요한 경우 sample env 안내
- 출력:
  - 생성된 경로 목록
  - DB path
  - settings path
- 실패:
  - 권한 부족, 기존 파일 충돌, DB 생성 실패를 명시
- 주의:
  - 재실행해도 기존 데이터를 망가뜨리지 않아야 한다.

### `wiki settings get`

- 입력: optional key
- 동작:
  - YAML settings에서 전체 또는 특정 key 조회
  - 민감 정보는 기본적으로 마스킹
- 출력:
  - 설정 값 또는 설정 목록
- 실패:
  - 알 수 없는 key, settings 파일 없음

### `wiki settings set <key> <value>`

- 입력: key, value
- 동작:
  - 허용된 key만 변경
  - 변경 전/후 값을 설정 변경 이력에 기록
  - 민감 정보는 출력에서 마스킹
- 출력:
  - 변경된 key
  - 변경 이력 artifact 또는 log ref
- 실패:
  - 잘못된 key, value type 오류, 저장 실패

### `wiki doctor`

- 입력: 없음 또는 `--json`
- 동작:
  - vault path 존재 확인
  - DB 연결 확인
  - FTS5/sqlite-vec 사용 가능성 확인
  - settings/env 확인
  - embedding backend 설정 확인
  - LLM endpoint 설정 존재 여부 확인
- 출력:
  - 항목별 `ok/warn/fail`
- 실패:
  - 점검 자체 실패 시 error report
- 범위:
  - 모델 응답 테스트는 `wiki models test` 책임이다.

### `wiki inbox scan`

- 입력: inbox 경로 또는 settings의 기본 inbox
- 동작:
  - Markdown 파일 감지
  - hash 계산
  - 이미 처리된 파일 제외
  - 중복 후보 표시
  - source 후보와 처리 대기 job 생성
- 출력:
  - 신규 후보 수
  - 중복 후보 수
  - 생성된 job 목록
- 실패:
  - inbox 경로 없음, 파일 읽기 실패

### `wiki ingest <path>`

- 입력: Markdown 파일 경로
- 동작:
  - 1차에서는 Markdown만 지원
  - 파일 hash 생성
  - Source row 생성
  - raw/source ref 저장
  - vault source stub 생성
  - normalize job 생성
- 출력:
  - `source_id`
  - normalize job id
  - source stub path
- 실패:
  - PDF/HTML/URL 등은 unsupported + Phase 2 안내
  - 중복 파일은 기존 Source 또는 중복 후보 report

### `wiki ingest-text`

- 입력: title, text 또는 stdin
- 동작:
  - 직접 입력 텍스트를 Source로 저장
  - source_type은 `user_text`
  - Source row와 vault source stub 생성
- 출력:
  - `source_id`
  - source stub path
- 실패:
  - 빈 텍스트, title 생성 실패

### `wiki normalize <source_id>`

- 입력: source_id
- 동작:
  - Markdown 원본을 normalized Markdown으로 복사/정규화
  - locator 정보를 유지
  - Source 상태를 normalized로 갱신
- 출력:
  - normalized path
  - locator 정책 요약
- 실패:
  - source 없음, raw 파일 없음, Markdown 파싱 실패

### `wiki chunk <source_id>`

- 입력: source_id
- 동작:
  - normalized Markdown을 chunk size/overlap 기준으로 분할
  - SourceChunk row 생성
  - locator와 token_count 기록
- 출력:
  - chunk 수
  - chunk id 목록 또는 artifact
- 실패:
  - normalized file 없음, chunk 생성 실패

### `wiki embed <target>`

- 입력: `source:<id>`, `chunk:<id>`, `claim:<id>`, `concept:<id>`, `all`
- 동작:
  - fastembed와 기본 model로 embedding 생성
  - model name, dimension, target, generated_at 저장
  - sqlite-vec index 갱신
- 출력:
  - embedding 수
  - dimension
  - model
- 실패:
  - 모델 다운로드/로드 실패, dimension 불일치, target 없음
- 재인덱싱:
  - 신규 wiki 확정 시 즉시 index 추가
  - 사용자가 선택 항목 또는 전체 재인덱싱 가능

### `wiki models list`

- 입력: 없음
- 동작:
  - settings/env에 등록된 chat/embedding provider와 model 표시
- 출력:
  - provider, model, capability
- 실패:
  - 설정 없음은 fail이 아니라 warn 가능

### `wiki models test <model_id>`

> LLM 연결 관련 테스트는 `wiki doctor`가 아니라 이 명령에서 수행한다. `doctor`는 환경 점검, `models test`는 실제 모델 endpoint 응답 점검이다.

- 입력: model_id
- 동작:
  - chat model이면 sample prompt 실행
  - embedding model이면 sample embedding과 dimension 확인
  - 결과 artifact 저장
- 출력:
  - ok/fail
  - latency/dimension 가능 시 표시
  - artifact path
- 실패:
  - endpoint 미응답, 인증 실패, JSON 응답 실패

### `wiki route get`

- 입력: optional task_type
- 동작:
  - task별 model routing 설정 조회
- 출력:
  - task_type → model_id mapping

### `wiki route set <task_type> <model_id>`

- 입력: task_type, model_id
- 동작:
  - 허용 task_type 검증
  - model capability 검증
  - routing 변경 이력 기록
- 출력:
  - 변경된 route
- 실패:
  - 알 수 없는 task_type, capability mismatch

### `wiki extract-claims <source_id>`

- 입력: source_id
- Phase 1 동작:
  - LLM 연결과 JSON/artifact 계약 검증
  - 실제 claim 품질은 Phase 2에서 고도화
  - JSON schema validate
  - 실패 시 error artifact와 retry 후보 생성
- Phase 2 동작:
  - evidence 기반 Claim 후보 생성
  - `review_route` 부여
- 출력:
  - 후보 수
  - artifact path
  - validation result

### `wiki summarize <source_id|concept_id>`

- Phase 1 동작:
  - 명령/입출력 계약과 placeholder artifact 생성
- Phase 2 동작:
  - 실제 요약 품질 구현
- 출력:
  - summary artifact path

### `wiki link <target>`

- 입력: claim/concept/source target
- Phase 1 동작:
  - relation 후보 저장 계약과 최소 placeholder
- Phase 2 동작:
  - 기존 Concept 후보 검색
  - relation 후보 생성
  - ontology rule 검증
  - review_route 부여
- 출력:
  - relation candidate 수
  - review_route 요약

### `wiki map <source_id>`

- Phase 1 동작:
  - mapping diff artifact 계약과 placeholder
- Phase 2 동작:
  - 신규 Claim/Concept와 기존 wiki 후보 비교
  - `link_to_existing`, `create_separate`, `merge_candidate` 후보 생성
- 출력:
  - mapping 후보 수
  - high similarity 후보 수

### `wiki compile <target>`

- Phase 1 동작:
  - 명령 구조/출력 계약/placeholder 또는 기본 초안 WikiPage 생성
- Phase 2 동작:
  - YAML frontmatter
  - Claim/Source/Concept 링크
  - 관련 개념
  - compile preview/diff
  - 승인 전 자동 반영 금지
- 출력:
  - preview path
  - diff artifact path

### `wiki validate <target>`

- 입력: source/claim/concept/relation/artifact/frontmatter 등
- 동작:
  - JSON schema, YAML frontmatter, 허용 단어, evidence, ID allow-list 검증
- 출력:
  - validation report
  - pass/fail
- 실패:
  - 검증 실패는 exit code와 report로 표시

### `wiki lint <target>`

- 동작:
  - source 없는 claim
  - locator 없는 claim
  - broken link
  - domain/range 위반
  - stale embedding
  - DB/Vault 불일치 등을 검사
- 출력:
  - severity별 lint report

### `wiki fix <target>`

- 동작:
  - 형식성 수정만 자동 처리
  - JSON format, frontmatter 정렬, alias normalize, stale embedding 재생성 등
  - 의미 변경은 자동 처리하지 않음
- 출력:
  - 수정 목록
  - backup/artifact path

### `wiki retry <job_id|run_id>`

- 동작:
  - 실패 job/run을 같은 입력으로 재실행
  - `retry_instruction`이 있으면 같은 task prompt에 주입
  - 이전 후보는 `superseded`로 표시하고 새 후보와 연결
- 출력:
  - new run id
  - superseded target
  - artifact path

### `wiki sync`

- 기본 동작:
  - read-only dry-run
  - Vault와 DB 차이 report
- `wiki sync --apply`:
  - 확인된 변경을 반영
  - 반영 artifact 기록
- 출력:
  - added/changed/missing/conflict 요약
- 실패:
  - 충돌, 권한 오류, DB lock

### `wiki status`

- 동작:
  - 대기 job 수
  - 실패 job 수
  - review 대기 수
  - source/concept 수
  - embedding index 상태
  - LLM 연결 상태 요약
- 출력:
  - 사람이 읽는 summary 또는 JSON

### `wiki search <query>`

- Phase 1 동작:
  - FTS/metadata 기본 검색
- Phase 2 동작:
  - vector/RAG search 확장
- 출력:
  - Source/Chunk/Claim/Concept/WikiPage 후보

### `wiki ask <query>`

- Phase 1 동작:
  - 명령/입출력 계약과 검색 후보 artifact 생성
- Phase 2 동작:
  - FTS + vector + ontology 확장 후보를 기반으로 LLM 답변 생성
  - 근거 Source/Claim 표시
- 출력:
  - answer artifact
  - evidence refs

### `wiki healthcheck`

- 동작:
  - 시스템 데이터 상태 종합 점검
  - DB/Vault 불일치
  - stale embedding
  - orphan concept
  - broken link
  - failed job 누적
- 출력:
  - health report
- 차이:
  - `doctor`는 로컬 환경 점검
  - `models test`는 모델 연결 점검
  - `healthcheck`는 데이터/시스템 상태 점검


## 관련 보강 문서

- Init 폴더 구조: `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
- CLI E2E 테스트 플랜: `.code-planner/02-planning/validation/cli-e2e-test-plan.md`
