# Build Ambiguity Check

## Result

- checkResult: issues_found
- 목적: 최신 Build handoff를 기준으로 Build 과정에서 추측/질문이 발생할 가능성이 큰 부분만 점검
- 실행: planning-crosscheck subagent

## 핵심 결론

Build handoff의 큰 방향은 충분하지만, Build agent가 바로 구현에 들어가면 schema/contract를 추측해야 하는 부분이 남아 있다.

가장 중요한 모호성은 다음 7개다.

1. SQLite 최소 schema DDL
2. LLM 후보 JSON schema
3. YAML settings schema
4. chunk/token/locator 정책
5. artifact 경로 규약
6. hash/중복 처리 정책
7. Phase 1 placeholder 산출물 형식

## Required before Build

아래 항목은 Build 전에 짧게라도 확정하는 것이 좋다.

### 1. SQLite schema 초안

필요한 최소 table:

- Source
- SourceChunk
- Embedding
- Job
- AgentRun
- Artifact
- ReviewCandidate
- HumanDecision
- PromptVersion

Build 전 결정 필요:

- Planning에서 column-level 초안을 줄지
- Build agent가 초안 작성 후 사용자 승인받을지

### 2. LLM 후보 JSON schema

Phase 1 placeholder라도 JSON validation을 하려면 최소 schema가 필요하다.

필수 결정:

- `candidate_key` 규칙
- `review_route` enum
- evidence 필수 여부
- `human_decision`은 LLM 출력 금지
- `retry_instruction`은 runner/human metadata

### 3. YAML settings schema

필수 top-level 후보:

```yaml
vault:
  path: ./vault
db:
  path: ./data/wiki.sqlite
llm:
  provider: openai_compatible
  endpoint: http://localhost:11434/v1
  chat_model: ""
embedding:
  backend: fastembed
  model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
web:
  admin_user: admin
route:
  extract_claims: ""
  map_candidates: ""
  compile_wiki: ""
```

필수 결정:

- env override 우선순위
- settings 변경 이력 저장 위치

### 4. chunk/token/locator 정책

모호성:

- chunk size
- overlap
- tokenizer 기준
- locator 형식

추천 결정:

- token_count는 fastembed tokenizer 기준을 우선 검토
- locator는 normalized Markdown 기준 offset/range로 시작

### 5. artifact 경로 규약

추천 규약:

```text
data/artifacts/<task_type>/<target_id>/<run_id>.json
data/artifacts/<task_type>/<target_id>/<run_id>.log
```

### 6. hash/중복 정책

추천 결정:

- hash 알고리즘: sha256
- 동일 hash 발견 시 skip + warn report
- 파일명이 달라도 내용 hash가 같으면 동일 Source 후보로 처리

### 7. Phase 1 placeholder 산출물 형식

명확화 필요:

- `wiki compile` placeholder가 어떤 Markdown stub를 만드는지
- `wiki ask` placeholder artifact의 최소 필드
- `wiki map/summarize` placeholder artifact의 최소 필드

## Can decide in Build, but should be noted

- `wiki init --path` 미지정 시 우선순위
- exit code 세부값
- sync 충돌 시 Vault 우선/DB 우선/수동 해결 정책
- Web auth session/cookie 만료 정책

## sqlite-vec fallback

현재 sqlite-vec는 candidate로 되어 있으나 validation에서는 required 성격으로 다뤄진다.

추천:

- sqlite-vec 설치 실패 시 embedding row는 저장한다.
- vector search는 disabled로 report한다.
- `wiki doctor`가 fallback 상태를 표시한다.

## Minimal Questions For User

1. SQLite schema DDL은 Planning에서 column-level 초안을 줄까요, Build agent가 작성 후 승인받게 할까요?
2. Phase 1 LLM 후보 JSON schema는 Planning에서 최소 schema를 제공할까요?
3. sqlite-vec 설치 불가 시 fallback은 “embedding 저장만 하고 vector search disabled”로 할까요?
4. Phase 1 placeholder 산출물은 artifact JSON + 최소 Markdown stub로 고정할까요?
5. chunk 정책은 fastembed tokenizer 기준으로 시작할까요?

## Recommended Handoff Patch

Build handoff에 다음 섹션을 추가하는 것을 권장한다.

- Build 전 schema 확정 항목
- SQLite 최소 table 목록
- YAML settings schema 초안
- artifact 경로 규약
- hash/중복 정책
- chunk/locator 기본값
- Phase 1 placeholder 산출물 최소 형식
- sqlite-vec fallback 정책

## 반영 상태

- 아직 handoff에는 미반영.
- 사용자 결정 후 Build handoff를 짧게 보정한다.


## 사용자 결정 반영

- SQLite schema DDL 초안은 Planning에서 제공한다.
- LLM 후보 JSON schema 초안은 Planning에서 제공한다.
- sqlite-vec 설치 실패 fallback을 바로 정하지 않고, Build 초기에 vector index 방향을 사전 검토한다.
- Phase 1 placeholder 산출물은 artifact JSON + 최소 Markdown stub로 고정한다.
- chunk 정책은 fastembed tokenizer 기준으로 시작한다.

## 반영 문서

- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- `.code-planner/02-planning/decisions/vector-index-options.md`
- `.code-planner/02-planning/handoff/build-handoff.md`
