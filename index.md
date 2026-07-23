# LLM Wiki Local

## 1. 목표

`LLM Wiki Local`은 문서, 웹 포스트, 사용자 입력 텍스트를 로컬 환경에서 정리하고 누적하는 개인 지식 시스템이다.

핵심 목적은 단순한 문서 보관이 아니라, 사용자와 LLM이 함께 활용할 수 있는 wiki를 만드는 것이다. 사용자는 Obsidian에서 지식을 읽고 수정하며, CLI와 Web UI는 자료 수집, 정규화, 요약, claim 추출, 관계 연결, 검증, 재컴파일을 돕는다.

이 프로젝트는 특정 LLM이나 특정 에이전트에 종속되지 않는다. 로컬 LLM, Codex, Claude 같은 도구가 같은 데이터 구조와 같은 작업 계약을 통해 협업할 수 있도록 설계한다.

## 2. 기본 방향

```text
자료 입력
  -> Source 생성
  -> 텍스트 정규화
  -> Chunk 생성
  -> Embedding 생성
  -> Claim 추출
  -> Ontology rule 검증
  -> Concept 연결
  -> Wiki Page 컴파일
  -> Obsidian에서 검토/수정
```

역할은 다음처럼 나눈다.

```text
Obsidian Vault
= 사람이 읽고 수정하는 지식 저장소

SQLite
= 시스템 상태, 작업 기록, 메타데이터, 관계, 검색 인덱스

SQLite FTS5
= 정확한 텍스트 검색

sqlite-vec
= 의미 기반 벡터 검색

CLI
= 자동화 실행 라인

Web UI
= 사용자가 보고 승인하고 수정하는 컨트롤 화면

Local LLM
= 추출, 요약, 연결, 컴파일을 수행하는 작업자
```

## 3. 입력 자료

초기 대상 자료는 다음과 같다.

- 문서 파일
- 웹 포스트
- 사용자가 직접 입력한 텍스트

하나의 자료는 최대 30page 정도를 기준 단위로 본다. 긴 자료는 여러 Source 또는 SourceChunk로 나누어 처리한다.

## 4. 저장 구조

이 시스템은 하나의 저장소만 사용하지 않는다. 역할에 따라 저장 계층을 분리한다.

```text
llm-wiki-local/
  index.md

  vault/
    00_inbox/
    10_sources/
    20_claims/
    30_concepts/
    40_wiki/
    90_templates/

  data/
    wiki.sqlite
    raw/
    normalized/
    artifacts/

  app/
    cli/
    api/
    web/
    schemas/
    agents/
```

`vault/`는 Obsidian이 여는 폴더다. 사용자가 직접 읽고 고치는 문서는 이곳에 둔다.

`data/wiki.sqlite`는 자동화와 검색을 위한 DB다. 원본 상태, 처리 단계, claim, concept, relation, job, agent run, FTS, vector index를 관리한다.

`data/raw/`는 원본 파일을 보관한다. `data/normalized/`는 파싱된 텍스트 또는 Markdown을 보관한다. `data/artifacts/`는 LLM 응답 JSON, 검증 결과, 실행 로그 같은 산출물을 보관한다.

## 5. 핵심 엔티티

### Source

Source는 입력 자료 하나를 의미한다.

예시는 PDF 문서, HTML 웹 포스트, Markdown 메모, 사용자가 붙여넣은 텍스트다.

주요 필드:

- `id`
- `source_type`
- `title`
- `origin`
- `raw_path`
- `normalized_path`
- `hash`
- `collected_at`
- `pipeline_stage`
- `review_status`

### SourceChunk

SourceChunk는 Source를 검색과 LLM 처리에 적합하게 나눈 조각이다.

주요 필드:

- `id`
- `source_id`
- `chunk_index`
- `text`
- `token_count`
- `locator`
- `embedding_id`

### Claim

Claim은 Source에서 추출한 검증 가능한 주장이다.

Concept가 설명 단위라면, Claim은 근거 단위다. wiki의 신뢰도는 Claim과 Source 추적 가능성에서 나온다.

주요 필드:

- `id`
- `subject`
- `predicate`
- `object`
- `source_id`
- `chunk_id`
- `locator`
- `polarity`
- `confidence`
- `valid_time`
- `extracted_by`
- `review_status`

### Concept

Concept는 wiki의 개념 노드다.

Claim들이 Concept에 연결되고, Concept 사이에는 ontology rule이 허용하는 relation만 만든다.

주요 필드:

- `id`
- `title`
- `aliases`
- `summary`
- `status`
- `source_ids`
- `claim_ids`
- `relations`
- `merged_from`
- `deprecated`

### WikiPage

WikiPage는 Source, Claim, Concept를 바탕으로 컴파일된 읽기용 문서다.

WikiPage는 최종 정본이라기보다 사람이 읽기 쉬운 view에 가깝다. 정본성은 Source, Claim, Concept, Relation의 추적 가능성에서 나온다.

### AgentRun

AgentRun은 LLM 또는 외부 에이전트가 수행한 작업 기록이다.

Codex, Claude, 로컬 LLM이 같은 시스템에 붙으려면 실행 기록과 산출물 형식을 남겨야 한다.

주요 필드:

- `id`
- `agent_type`
- `model`
- `task_type`
- `input_refs`
- `output_refs`
- `prompt_version`
- `schema_version`
- `started_at`
- `finished_at`
- `status`

## 6. DB 방향

초기 DB는 SQLite를 사용한다.

SQLite는 단순 저장소가 아니라 다음 역할을 맡는다.

- pipeline 상태 관리
- 작업 queue 관리
- Source, Claim, Concept, Relation 메타데이터 저장
- FTS5 기반 텍스트 검색
- sqlite-vec 기반 벡터 검색
- AgentRun 실행 기록 저장
- Obsidian 문서와 DB row의 동기화 상태 저장

초기 테이블 후보:

- `sources`
- `source_chunks`
- `claims`
- `concepts`
- `concept_claims`
- `relations`
- `embeddings`
- `agent_runs`
- `jobs`
- `artifacts`

임베딩은 SQLite에 저장할 수 있다. 단순 보관은 `BLOB`으로 가능하고, 유사도 검색은 `sqlite-vec`를 이용한다.

## 7. 검색 전략

검색은 한 가지 방식에 의존하지 않는다.

```text
정확 검색
= FTS5

의미 검색
= sqlite-vec

구조 검색
= ontology relation, concept graph, claim provenance
```

LLM이 wiki를 사용할 때는 다음 순서를 기본으로 한다.

```text
질문 또는 작업 요청
  -> FTS로 고유명사와 정확 일치 후보 검색
  -> vector search로 의미상 가까운 Chunk/Claim/Concept 검색
  -> ontology relation으로 주변 Concept 확장
  -> review_status와 source provenance로 필터링
  -> LLM이 답변, 수정 제안, 또는 WikiPage 재컴파일
```

임베딩은 답을 결정하는 장치가 아니라 후보를 찾는 장치로 본다. 최종 신뢰도는 Claim, Source, review status, ontology rule에서 나온다.

## 8. CLI 방향

CLI는 자동화의 중심이다. Web UI와 외부 에이전트는 CLI 또는 API를 통해 같은 작업을 실행한다.

현재 CLI 명령 표면은 사용자/운영 명령과 debug/dev 명령을 분리한다.

```text
사용자/운영:
wiki init
wiki ingest <file.md> [--llm]
wiki ingest-text <title> --text <text>
wiki inbox scan
wiki ask <question>
wiki search <query>
wiki status
wiki web
wiki settings get|set
wiki models list|test
wiki route get|set
wiki doctor
wiki healthcheck

Debug/dev:
wiki normalize <source_id>
wiki chunk <source_id>
wiki embed source:<source_id>
wiki extract-claims <source_id> [--llm]
wiki validate
wiki lint
wiki debug-repair-source-stubs
```

CLI는 사람이 보지 않아도 실행 가능해야 한다. 그러나 모든 실행 결과는 DB와 artifact로 남아 Web UI에서 확인할 수 있어야 한다.

### Wiki page candidate 생성 동작 logic

LLM은 의미 기반 page candidate를 생성하거나 보완하고, CLI는 parse, repair, provenance, graph 연결, 최종 파일 검증을 책임진다. LLM 응답을 그대로 신뢰하지 않고, 원문 응답과 오류 내용을 artifact로 남긴 뒤 한 번의 correction retry를 허용한다.

```text
[CLI] section chunks 준비

→ [LLM] page candidate 생성 요청
    ├─ document_type 먼저 분류
    ├─ spec/reference/manual/protocol/API/structured_guide → 6-12개 목표
    ├─ short_readme/announcement/single_tool_overview → 1-4개 목표
    ├─ essay/analysis/benchmark/comparison → 3-6개 목표
    └─ 선택한 유형/range에 맞춰 candidate granularity 결정

→ [LLM] page candidate JSON 응답
    ├─ document_type 포함
    ├─ target_candidate_count 포함
    └─ candidates 배열 포함

→ [CLI] JSON parse / syntax repair
    ├─ JSON parse 성공
    │   → schema normalize
    └─ JSON parse 실패
        ├─ [CLI] json_repair 시도
        ├─ repair 성공
        │   → schema normalize
        └─ repair 실패
            → [LLM retry] 원본 JSON + parse error 전달
            → 재응답 parse

→ [CLI] schema normalize / validation
    ├─ ok
    │   → merge
    └─ fail
        ├─ missing required fields
        ├─ wrong field types
        ├─ empty candidates
        ├─ missing tags
        ├─ missing title/body/summary
        └─ [LLM retry] 원본 JSON + validation errors + schema contract 전달

→ [CLI] retry response parse / normalize
    ├─ ok
    │   → merge
    └─ fail
        → deterministic fallback or failed

→ [CLI] merge_wiki_page_candidates

→ [CLI] repair_and_validate_candidates
    ├─ source_id 누락
    ├─ source_common_tag 누락
    ├─ node_type tag 누락
    ├─ source_section_refs 누락
    └─ evidence_claims 누락
    → deterministic repair

→ [CLI] validate_wiki_page_candidate
    ├─ ok
    │   → write
    └─ fail
        → failed/degraded artifact

→ [CLI] write_compiled_candidates

→ [CLI] validate_compiled_pages
    ├─ ok
    │   → success
    └─ fail
        → compiler/write failure
```

처리 기준은 다음과 같다.

| 실패 유형 | 1차 처리 | 2차 처리 |
|---|---|---|
| JSON 문법 오류 | CLI JSON repair | 실패 시 LLM correction retry |
| schema field 불일치 | CLI normalize | 실패 시 LLM correction retry |
| 필수 의미값 누락 | LLM correction retry | 실패 시 deterministic fallback 또는 failed |
| source_id/common tag/node_type tag 누락 | CLI authoritative repair | 재검증 실패 시 quality gate failure |
| compiled markdown 오류 | CLI/compiler failure | LLM retry 대상 아님 |

source provenance와 graph identity는 CLI가 authoritative하게 주입한다. LLM은 `title`, `summary`, `semantic tags`, `draft_body`, `aliases` 같은 의미적 초안을 담당한다.

## 9. Web UI 방향

Web UI는 지식 생성기가 아니라 컨트롤 화면이다.

초기 화면 후보:

- Inbox: 새 자료와 처리 대기 목록
- Pipeline: job 상태, 실패 원인, 재실행
- Source View: 원본, 정규화 텍스트, chunk
- Claim Review: 추출된 claim 승인, 반려, 수정
- Concept View: 연결된 claim, alias, relation
- Graph View: concept 관계와 중복 후보
- Wiki Preview: Obsidian에 기록될 문서 미리보기
- Healthcheck: 충돌, 중복, 출처 부족, 오래된 정보

사용자는 Web UI에서 자동화 결과를 검토하고 승인한다. 승인된 결과가 Obsidian Vault에 반영된다.

## 10. LLM 및 에이전트 호환성

초기 로컬 LLM 후보:

```text
google/gemma-4-26b-a4b-qat
```

모델은 직접 코드에 고정하지 않는다. `agents/` 아래 adapter로 분리한다.

공통 작업 요청 형식은 다음과 같은 방향으로 둔다.

```json
{
  "task_type": "extract_claims",
  "input_refs": ["source:src_001"],
  "constraints": ["json_schema:claim.v1"],
  "model": "google/gemma-4-26b-a4b-qat",
  "output_artifact": "artifact:run_001_claims.json"
}
```

Codex, Claude, 로컬 LLM은 모두 이 작업 계약을 따르게 한다. 차이는 adapter 내부에만 둔다.

## 11. Ontology Rule 방향

초기에는 완전한 OWL 시스템을 목표로 하지 않는다.

대신 다음 정도의 제한된 ontology rule을 사용한다.

- class 목록을 닫힌 목록으로 관리한다.
- predicate 목록을 닫힌 목록으로 관리한다.
- predicate별 domain/range를 검증한다.
- inverse relation을 정의한다.
- symmetric relation 여부를 정의한다.
- transitive relation 여부를 정의한다.
- Concept와 Claim의 relation을 구분한다.
- contradiction은 Concept가 아니라 Claim 사이에 연결한다.

초기 목표는 철학적으로 완벽한 온톨로지가 아니라, 작은 모델이 흔들리지 않게 작업할 수 있는 규칙 집합이다.

## 12. 초기 구현 순서

1. Obsidian Vault 폴더 구조 생성
2. SQLite schema 정의
3. Source ingest CLI 작성
4. Markdown/YAML frontmatter schema 정의
5. FTS5 검색 추가
6. sqlite-vec 임베딩 저장과 검색 추가
7. Claim 추출 schema와 validator 작성
8. Concept 연결과 WikiPage compile 작성
9. Web UI에서 Inbox/Pipeline/Claim Review 구현
10. Healthcheck와 재컴파일 흐름 구현

## 13. 현재 결정

- 저장소는 Obsidian Vault를 중심으로 한다.
- DB는 SQLite를 사용한다.
- 텍스트 검색은 SQLite FTS5를 사용한다.
- 벡터 검색은 SQLite 기반 `sqlite-vec`를 우선 검토한다.
- 자동화는 CLI 중심으로 만든다.
- 사용자가 보는 화면은 Web UI로 만든다.
- LLM은 adapter로 분리한다.
- 핵심 지식 단위는 Source, SourceChunk, Claim, Concept, WikiPage, AgentRun이다.

## 14. 세부 설계 문서

- [CLI Features](docs/01_cli_features.md)
- [Web UI Features](docs/02_web_ui_features.md)
- [Schema and Ontology](docs/03_schema_and_ontology.md)
- [LLM Schema Guide](docs/04_llm_schema_guide.md)
