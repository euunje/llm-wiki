# Feature Contract — Phase 1 CLI Foundation

## Phase 목적

CLI 기능 구현을 통해 LLM Wiki Local의 기반 동작을 완성한다. 이 단계는 최종 wiki 품질이 아니라, 자료 처리·상태 기록·LLM 연결·artifact·sync가 작동하는 기반을 만드는 것이 목표다.

## 주요 사용자 흐름

```text
wiki init
  -> wiki settings get/set
  -> wiki doctor
  -> wiki ingest sample.md
  -> wiki normalize <source_id>
  -> wiki chunk <source_id>
  -> wiki embed source:<source_id>
  -> wiki models test <model_id>
  -> wiki extract-claims <source_id>
  -> wiki validate <target>
  -> wiki sync
```

## 포함 기능

### 1. 프로젝트 초기화

- `wiki init`
- Vault/data/settings/DB/schema 생성
- 재실행 안전성 보장

### 2. 설정 관리

- `wiki settings get`
- `wiki settings set <key> <value>`
- sample env 기준 설정
- 민감정보 마스킹

### 3. 환경 점검

- `wiki doctor`
- 로컬 경로, DB, FTS5, sqlite-vec, settings, env 점검

### 4. Markdown Source Pipeline

- `wiki inbox scan`
- `wiki ingest <markdown_path>`
- `wiki ingest-text`
- `wiki normalize <source_id>`
- `wiki chunk <source_id>`

1차에서 PDF/Office/HTML/URL은 명확한 unsupported 안내 또는 Phase 2 안내를 반환한다.

### 5. Embedding

- `wiki embed <target>`
- 기본값: `fastembed` + `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- model, dimension, target, generated_at 기록

### 6. LLM 연결과 후보 계약 최소 구현

- `wiki models list`
- `wiki models test <model_id>`
- `wiki route get/set`
- `wiki extract-claims <source_id>` 최소 JSON/artifact 계약
- `wiki summarize`, `wiki map`, `wiki ask`는 1차에서 계약/placeholder 또는 최소 artifact까지

### 7. 검증/상태/복구

- `wiki validate <target>`
- `wiki lint <target>`
- `wiki status`
- `wiki fix <target>` 형식성 수정
- `wiki retry <job_id|run_id>`
- `wiki sync`

## 공통 CLI 계약

모든 명령은 다음을 문서화하고 가능하면 지원한다.

- `--json`
- exit code
- job/run id
- artifact path
- dry-run 가능 여부
- idempotency 정책
- 실패 시 error artifact

## 제외 기능

- 실제 LLM 프롬프트 품질 완성
- 실사용 WikiPage 품질
- 비-Markdown 변환 완성
- Web UI
- 자동 파일 watcher

## 성공 상태

- 샘플 Markdown 1건이 ingest → normalize → chunk → embed → LLM 연결 테스트 → artifact/DB 저장 → sync를 통과한다.
- 실패 상황이 artifact와 job status로 남는다.
- Build가 각 CLI 명령의 최소 입출력 계약을 구현할 수 있다.

## 사용자 검토 질문

1. `wiki ask`, `wiki map`, `wiki summarize`의 1차 placeholder 출력은 artifact 중심이면 충분한가?
2. `wiki sync`는 기본 dry-run, 실제 반영은 `--apply`로 확정한다.
3. settings 파일 형식은 TOML/YAML/JSON 중 무엇이 좋은가?


## 확정 보정

- Settings 파일 형식: YAML
- `wiki sync`: 기본 dry-run/report, 실제 반영은 `--apply`
- Web Auth secret은 `.env`에 둔 사용자 비밀번호 기반
