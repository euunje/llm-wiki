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
