# 02 Detailed Phase Tasks — LLM Wiki Local

## 목적

Build agent가 phase별 기능을 추측하지 않도록 세부 task와 동작 계약을 한 곳에 정리한다.

---

# Phase 1 상세 task

## 1. Init folder structure

# Init Folder Structure Contract — Phase 1

## 목적

`wiki init`이 생성해야 할 기본 폴더 구조를 Build 전에 명확히 고정한다.  
구조는 사람이 Obsidian에서 보기 쉬운 Vault 영역과, 시스템이 관리하는 data 영역을 분리한다.

## 설계 원칙

- Vault는 사람이 읽고 수정하는 영역이다.
- data는 시스템이 원본, normalized text, artifact, DB를 관리하는 영역이다.
- Obsidian에서 자주 보는 폴더는 숫자 prefix로 정렬한다.
- 원본/로그/설정은 지식 문서와 섞이지 않게 뒤쪽 번호를 쓴다.

## 추천 기본 구조

```text
llm-wiki-local/
  vault/
    00_Inbox/
      memo/
      files/
      text/
    10_Wiki/
      concepts/
      sources/
      claims/
      pages/
    20_Review/
      candidates/
      mapping/
      rejected/
    80_Raws/
      README.md
    90_Settings/
      templates/
      prompts/
      ontology/

  data/
    wiki.sqlite
    raw/
    normalized/
    artifacts/
    exports/
    cache/
```

## 폴더별 역할

| 경로 | 역할 | 사람이 직접 수정? | 시스템 쓰기? |
|---|---|---:|---:|
| `vault/00_Inbox/memo/` | 사용자가 빠르게 적는 메모 | yes | scan/read |
| `vault/00_Inbox/files/` | 사용자가 넣는 입력 파일 참조 또는 안내 | yes | scan/read |
| `vault/00_Inbox/text/` | 직접 입력 텍스트 초안 | yes | scan/read |
| `vault/10_Wiki/concepts/` | 확정된 Concept 문서 | yes | 승인 후 write |
| `vault/10_Wiki/sources/` | Source stub/요약 | yes | 승인 후 write |
| `vault/10_Wiki/claims/` | Claim 문서 또는 claim view | 제한적 | 승인 후 write |
| `vault/10_Wiki/pages/` | compile된 WikiPage | yes | 승인 후 write |
| `vault/20_Review/candidates/` | 검토 대기 후보의 사람이 보는 view | 제한적 | write |
| `vault/20_Review/mapping/` | mapping review용 view | 제한적 | write |
| `vault/20_Review/rejected/` | reject/retry 이력 view | 제한적 | write |
| `vault/80_Raws/` | 원본 파일 위치 안내 또는 사람이 볼 raw index | no 권장 | minimal |
| `vault/90_Settings/templates/` | Markdown template | yes | read/write |
| `vault/90_Settings/prompts/` | prompt confirmed/test version view | yes | write |
| `vault/90_Settings/ontology/` | ontology rule 문서 view | yes | write |
| `data/wiki.sqlite` | DB | no | yes |
| `data/raw/` | 실제 원본 저장 | no | yes |
| `data/normalized/` | normalized Markdown 저장 | no | yes |
| `data/artifacts/` | LLM JSON, logs, validation 결과 | no | yes |
| `data/exports/` | export/backup 산출물 | no | yes |
| `data/cache/` | embedding/model/cache | no | yes |

## `80_Raws`와 `data/raw`의 차이

- `data/raw/`: 실제 원본 파일이 저장되는 시스템 영역
- `vault/80_Raws/`: Obsidian에서 원본 목록/링크/주의사항을 볼 수 있는 문서 영역

즉, 대용량 원본은 `data/raw/`에 두고, 사람이 보는 raw index만 Vault에 둔다.

## `wiki init` 동작

`wiki init`은 다음을 수행한다.

1. 위 폴더 구조 생성
2. `data/wiki.sqlite` 생성
3. YAML settings 생성
4. 기본 templates/prompts/ontology placeholder 생성
5. `.env.sample` 안내 또는 생성
6. 재실행 시 기존 파일을 덮어쓰지 않고 missing path만 보완

## 검증 기준

- `wiki init` 실행 후 모든 필수 폴더가 존재한다.
- 재실행해도 기존 문서/DB가 손상되지 않는다.
- Vault 영역과 data 영역의 역할이 settings에 기록된다.


---

## 2. CLI behavior contract

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


---

## 3. SQLite schema draft

# SQLite Schema Draft — Build 전 초안

## 목적

Build agent가 DB 구조를 임의로 해석하지 않도록 Phase 1에서 필요한 최소 table/column/FK를 고정한다. 세부 index 최적화와 migration 구현 방식은 Build에서 조정할 수 있지만, row의 의미는 이 문서를 기준으로 한다.

## 공통 규칙

- `id`는 사람이 읽을 수 있는 prefix + ULID/UUID 형식을 권장한다.
- 모든 주요 table은 `created_at`, `updated_at`을 가진다.
- JSON 값은 SQLite `TEXT`에 JSON 문자열로 저장한다.
- 상태 값은 closed enum으로 validator에서 검증한다.
- 실제 Vault 파일 경로와 data 파일 경로는 상대 경로 저장을 우선한다.

## 핵심 table

### `sources`

```sql
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  title TEXT NOT NULL,
  origin TEXT,
  raw_path TEXT,
  normalized_path TEXT,
  content_hash TEXT NOT NULL,
  pipeline_stage TEXT NOT NULL DEFAULT 'created',
  review_status TEXT NOT NULL DEFAULT 'pending',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_sources_hash ON sources(content_hash);
```

초기 `source_type`:

- `markdown_file`
- `user_text`
- `converted_markdown` 이후 phase

초기 `pipeline_stage`:

- `created`
- `ingested`
- `normalized`
- `chunked`
- `embedded`
- `candidate_generated`
- `synced`
- `failed`

### `source_chunks`

```sql
CREATE TABLE source_chunks (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(id),
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  token_count INTEGER NOT NULL,
  locator_json TEXT NOT NULL,
  embedding_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(source_id, chunk_index)
);
```

`locator_json` 최소 형식:

```json
{
  "source_id": "source_...",
  "start_offset": 0,
  "end_offset": 1200,
  "char_count": 1200,
  "heading_path": ["..."],
  "quote_start": "..."
}
```

### `embeddings`

```sql
CREATE TABLE embeddings (
  id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  model TEXT NOT NULL,
  backend TEXT NOT NULL,
  dimension INTEGER NOT NULL,
  vector_blob BLOB,
  vector_json TEXT,
  index_status TEXT NOT NULL DEFAULT 'pending',
  generated_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(target_type, target_id, model)
);
```

주의:

- vector 저장 방식은 vector index 결정에 따라 `vector_blob` 또는 sqlite-vec table과 연결한다.
- sqlite-vec 방향이 최종 확정되면 별도 virtual table을 추가한다.

### `jobs`

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  input_refs_json TEXT NOT NULL DEFAULT '[]',
  output_refs_json TEXT NOT NULL DEFAULT '[]',
  error_json TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
```

`status`: `queued`, `running`, `succeeded`, `failed`, `needs_review`, `cancelled`.

### `agent_runs`

```sql
CREATE TABLE agent_runs (
  id TEXT PRIMARY KEY,
  job_id TEXT REFERENCES jobs(id),
  agent_type TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  task_type TEXT NOT NULL,
  prompt_version_id TEXT,
  input_refs_json TEXT NOT NULL DEFAULT '[]',
  output_refs_json TEXT NOT NULL DEFAULT '[]',
  artifact_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  error_json TEXT
);
```

### `artifacts`

```sql
CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  artifact_type TEXT NOT NULL,
  task_type TEXT,
  target_type TEXT,
  target_id TEXT,
  run_id TEXT,
  path TEXT NOT NULL,
  content_hash TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
```

artifact 경로 규약:

```text
data/artifacts/<task_type>/<target_id>/<run_id>.json
data/artifacts/<task_type>/<target_id>/<run_id>.log
```

### `review_candidates`

```sql
CREATE TABLE review_candidates (
  id TEXT PRIMARY KEY,
  candidate_type TEXT NOT NULL,
  candidate_key TEXT NOT NULL,
  source_id TEXT,
  run_id TEXT REFERENCES agent_runs(id),
  payload_json TEXT NOT NULL,
  review_route TEXT NOT NULL,
  review_reason TEXT,
  related_candidate_keys_json TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'pending',
  superseded_by TEXT REFERENCES review_candidates(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`candidate_type`:

- `claim`
- `node`
- `relation`
- `mapping`
- `claim_conflict`

`review_route`:

- `normal_review`
- `needs_merge_decision`
- `needs_retry`
- `conflict_flag`

`status`:

- `pending`
- `approved`
- `rejected`
- `retry_requested`
- `superseded`

### `human_decisions`

```sql
CREATE TABLE human_decisions (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES review_candidates(id),
  decision_type TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  note TEXT,
  retry_instruction_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
```

`decision_type`:

- `approve`
- `reject`
- `merge`
- `create_new`
- `edit`
- `retry_with_instruction`

### `retry_instructions`

```sql
CREATE TABLE retry_instructions (
  id TEXT PRIMARY KEY,
  target_candidate_id TEXT NOT NULL REFERENCES review_candidates(id),
  reason TEXT NOT NULL,
  instruction TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  consumed_run_id TEXT REFERENCES agent_runs(id)
);
```

### `prompt_versions`

```sql
CREATE TABLE prompt_versions (
  id TEXT PRIMARY KEY,
  task_type TEXT NOT NULL,
  version_label TEXT NOT NULL,
  state TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  change_note TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  confirmed_at TEXT,
  UNIQUE(task_type, version_label)
);
```

`state`:

- `test`
- `confirmed`
- `archived`

## Hash 정책

- 알고리즘: `sha256`
- 동일 hash 발견 시 기본 동작: skip + warn report
- 파일명이 달라도 내용 hash가 같으면 동일 Source 후보로 처리

## Build 조정 가능 범위

- 실제 ID 생성 방식
- index 이름/추가 index
- migration tool
- sqlite-vec virtual table 최종 DDL

단, table의 의미와 필수 관계는 유지한다.


---

## 4. LLM candidate JSON schema draft

# LLM Candidate JSON Schema Draft — Phase 1/2

## 목적

Phase 1에서도 LLM 응답 JSON/artifact 계약을 검증할 수 있도록 최소 schema를 제공한다. Phase 2에서는 이 schema를 품질 prompt와 함께 확장한다.

## 핵심 원칙

- LLM은 후보만 제안한다.
- LLM은 영구 ID를 만들지 않는다.
- LLM은 Vault Markdown을 직접 수정하지 않는다.
- LLM은 `human_decision`, `retry_instruction`, `approved`, `rejected`, `replaced`를 출력하지 않는다.
- 검토 흐름은 `review_route`로 표현한다.
- 사람 결정은 runner/Web이 `human_decision`으로 기록한다.

## 공통 envelope

```json
{
  "task_type": "extract_claims",
  "source_id": "source_...",
  "schema_version": "candidate.v1",
  "claim_candidates": [],
  "node_candidates": [],
  "relation_candidates": [],
  "mapping_candidates": [],
  "claim_conflict_candidates": []
}
```

`needs_human_review` 배열은 별도로 두지 않는다. 필요한 흐름은 후보별 `review_route`, `review_reason`, `related_candidate_keys`로 표현한다.

## 공통 candidate 필드

모든 후보는 다음 필드를 가진다.

```json
{
  "candidate_key": "node_01",
  "review_route": "normal_review",
  "review_reason": "",
  "related_candidate_keys": []
}
```

`review_route` enum:

- `normal_review`
- `needs_merge_decision`
- `needs_retry`
- `conflict_flag`

## candidate_key 규칙

- 응답 안에서만 유효한 임시 key
- 형식:
  - `claim_01`
  - `node_01`
  - `relation_01`
  - `mapping_01`
  - `conflict_01`
- 영구 ID 생성 금지

## Claim candidate

```json
{
  "candidate_key": "claim_01",
  "statement": "...",
  "claim_relation_type": "defines",
  "subject_ref": { "kind": "new_node", "candidate_key": "node_01" },
  "object_ref": { "kind": "existing_node", "id": "concept_..." },
  "qualifiers": {},
  "evidence": [
    {
      "source_id": "source_...",
      "chunk_id": "chunk_...",
      "locator": {
        "char_start": 0,
        "char_end": 120,
        "quote": "..."
      }
    }
  ],
  "model_confidence": 0.78,
  "review_route": "normal_review",
  "review_reason": "",
  "related_candidate_keys": []
}
```

Phase 1 placeholder에서는 `claim_candidates`가 빈 배열이어도 된다. 단 schema shape는 유효해야 한다.

## Node candidate

```json
{
  "candidate_key": "node_01",
  "node_type": "concept",
  "title": "Agentic RAG",
  "aliases": [],
  "summary": "...",
  "evidence_claim_keys": ["claim_01"],
  "review_route": "needs_merge_decision",
  "review_reason": "유사한 기존 개념이 있음",
  "related_candidate_keys": []
}
```

## Relation candidate

```json
{
  "candidate_key": "relation_01",
  "source_ref": { "kind": "new_node", "candidate_key": "node_01" },
  "relation_type": "uses",
  "target_ref": { "kind": "existing_node", "id": "concept_vector_search" },
  "evidence_claim_keys": ["claim_01"],
  "model_confidence": 0.81,
  "review_route": "normal_review",
  "review_reason": "",
  "related_candidate_keys": []
}
```

`source_ref`와 `target_ref`는 다음을 허용한다.

- `{ "kind": "existing_node", "id": "..." }`
- `{ "kind": "new_node", "candidate_key": "node_01" }`

## Mapping candidate

```json
{
  "candidate_key": "mapping_01",
  "incoming_ref": { "kind": "new_node", "candidate_key": "node_01" },
  "existing_node_id": "concept_rag",
  "mapping_action": "merge_candidate",
  "evidence_claim_keys": ["claim_01"],
  "reason": "정의와 범위가 유사함",
  "model_confidence": 0.82,
  "review_route": "needs_merge_decision",
  "review_reason": "병합 판단 필요",
  "related_candidate_keys": ["node_01"]
}
```

`mapping_action` enum:

- `link_to_existing`
- `create_separate`
- `merge_candidate`

## Claim conflict candidate

```json
{
  "candidate_key": "conflict_01",
  "claim_ref_a": "claim_01",
  "claim_ref_b": "claim_existing_001",
  "conflict_scope": "...",
  "reason": "...",
  "model_confidence": 0.72,
  "review_route": "conflict_flag",
  "review_reason": "충돌 검토 필요",
  "related_candidate_keys": ["claim_01"]
}
```

## Runner/human metadata: LLM 출력 금지

아래는 LLM 출력에 포함되면 validator가 거부한다.

```json
{
  "human_decision": {},
  "retry_instruction": {},
  "approved": true,
  "rejected": true,
  "replaced": true
}
```

Runner/Web이 별도로 기록할 메타:

```json
{
  "human_decision": {
    "decision_type": "retry_with_instruction",
    "decided_by": "admin",
    "decided_at": "...",
    "retry_instruction_id": "retry_..."
  },
  "retry_instruction": {
    "reason": "범위가 너무 넓음",
    "instruction": "Agentic RAG와 일반 RAG를 구분해서 다시 판단",
    "target_candidate_keys": ["node_01"]
  }
}
```

## Phase 1 placeholder 허용

Phase 1에서는 아래가 허용된다.

- 모든 후보 배열이 빈 배열
- `review_route` 검증만 수행
- error artifact 저장
- schema validation 결과 저장

단, envelope 자체는 유효해야 한다.


---

# Phase 2 상세 task 요약

- LLM 후보 schema를 실제 validator로 구현한다.
- `review_route`, `human_decision`, `retry_instruction`, `superseded` 흐름을 구현한다.
- prompt test version → test run → confirmed version 흐름을 구현한다.
- WikiPage compile preview를 구현한다.
- PDF/Office/HTML/URL → Markdown normalized 변환을 구현한다.
- vector index 방향은 Build 초기 spike 결과로 확정한다.

# Phase 3 상세 task 요약

- 승인된 HTML mockup을 기준으로 UI 구조를 구현한다.
- Dashboard, Review Main, Graph Popup, Settings를 구현한다.
- Web Auth는 `.env` 사용자 비밀번호 기반이다.
- prompt 변경은 test version으로 저장하고, test run 후 confirmed version으로 승격한다.


## Phase 3 Web UI 확정 기술스택

- Backend/API: FastAPI
- Server: uvicorn
- Template: Jinja2
- Form parsing: python-multipart
- Settings YAML: PyYAML
- Env loading: python-dotenv
- Schema validation: pydantic
- Frontend: server-rendered HTML + Vanilla JS ES modules + plain CSS
- Graph: inline SVG + Vanilla JS
- Auth: `.env` 관리자 비밀번호 + stdlib hmac signed session cookie

Build agent는 이 stack으로 Web UI를 완성한다.
