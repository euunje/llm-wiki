# Schema and Ontology

## 1. 목적과 범위

이 문서는 `LLM Wiki Local`이 사용하는 지식 스키마와 최소 온톨로지 규칙을 정의한다.

목표는 일반적인 지식 그래프를 모두 표현하는 것이 아니다. 작은 로컬 LLM도 안정적으로 Source를 Claim으로 추출하고, Claim을 Concept에 연결하며, 사람이 그 결과를 검토할 수 있도록 제한된 어휘와 검증 규칙을 제공하는 것이다.

초기 스키마 버전은 `1`이다. 스키마를 바꿀 때에는 기존 문서를 해석하지 못하게 바꾸지 않고 migration을 제공한다.

## 2. 정본과 동기화 원칙

같은 사실을 Markdown과 SQLite에서 각각 독립적으로 수정할 수 있게 만들면 충돌 원인이 된다. 따라서 데이터의 책임을 다음처럼 나눈다.

```text
승인된 지식 기록
= Obsidian Vault의 Source / Claim / Concept Markdown과 YAML frontmatter

자동화 상태와 파생 데이터
= SQLite의 job, agent run, artifact, FTS, embedding, mapping candidate, relation index
```

승인된 관계는 Vault의 entity frontmatter에 기록하고, SQLite의 `relations`는 그 내용을 인덱싱한 조회용 row로 동기화한다. 승인 전 mapping 후보와 LLM 원본 응답은 Vault를 변경하지 않고 SQLite와 artifact에만 저장한다.

Web UI와 CLI가 승인된 지식을 수정할 때는 Markdown 파일을 먼저 갱신하고, 동기화 작업이 SQLite 인덱스를 갱신한다. 사람이 Obsidian에서 파일을 수정한 경우에도 같은 동기화 작업이 변경을 읽는다.

## 3. 지식 계층

```text
Source
  -> SourceChunk
  -> Claim
  -> Concept 또는 다른 Knowledge Node
  -> WikiPage
```

- `Source`: 원문 자료와 수집 정보다.
- `SourceChunk`: Source 안의 인용 가능한 위치다.
- `Claim`: Source가 말한, 참/거짓 또는 조건을 검토할 수 있는 주장이다.
- `Knowledge Node`: Concept, Project, Method, Model, System처럼 wiki에서 연결되는 노드다.
- `WikiPage`: 승인된 노드를 사람이 읽기 좋게 컴파일한 문서다.

`Claim`과 `Knowledge Node`를 섞지 않는다. 예를 들어 “Self-Attention은 장거리 의존성을 잘 모델링한다”는 Claim이고, “Transformer의 Self-Attention”은 Concept다.

## 4. 공통 식별자와 상태

### 식별자

모든 ID는 소문자 kebab-case를 사용하고 생성 후 변경하지 않는다.

```text
source-arxiv-2408-1234
chunk-arxiv-2408-1234-p03-s02
claim-attention-long-range-001
concept-transformer-attention
project-nlp-study
relation-concept-attention-part-of-project-nlp-study
```

파일명은 ID와 일치시키는 것을 기본값으로 둔다. 제목과 alias는 바뀔 수 있지만 ID는 링크와 DB 동기화 키이므로 바꾸지 않는다.

### 공통 상태

`node_state`는 Knowledge Node의 성숙도다. Claim이나 Relation의 승인 상태와 혼용하지 않는다.

| 값 | 의미 |
| --- | --- |
| `draft` | 자동 생성 또는 작성 중이며 사람 검토 전이다. |
| `reviewed` | 사람이 내용과 근거를 확인했다. |
| `stable` | 반복 검토 후 기본 검색과 compile에 사용해도 되는 상태다. |
| `deprecated` | 더 이상 기본 결과에 쓰지 않지만 기록과 링크는 보존한다. |

Claim과 Relation에는 별도 `review_state`를 둔다.

| 값 | 의미 |
| --- | --- |
| `pending` | LLM 또는 import가 제안한 상태이며 사람 검토 전이다. |
| `approved` | 사람이 승인했거나 설정된 자동 승인 규칙을 통과했다. |
| `rejected` | 검토 결과 사용하지 않기로 했다. |
| `replaced` | 더 정확한 Claim 또는 Relation으로 대체됐다. |

## 5. Source Schema

Source는 원문과 수집 맥락을 보존한다. 정규화된 본문이나 LLM 요약은 원문을 대체하지 않는다.

```yaml
---
id: source-arxiv-2408-1234
record_type: source
source_type: web_article
title: "Attention Is All You Need"
origin:
  url: "https://example.org/paper"
  retrieved_at: "2026-07-17T00:00:00+09:00"
raw_path: "data/raw/source-arxiv-2408-1234.html"
normalized_path: "data/normalized/source-arxiv-2408-1234.md"
content_hash: "sha256:..."
language: en
source_state: active
schema_version: 1
created_at: "2026-07-17T00:00:00+09:00"
updated_at: "2026-07-17T00:00:00+09:00"
---
```

`source_type`은 초기에는 `pdf`, `web_article`, `markdown`, `text`, `user_text`만 허용한다. `origin`에는 URL, 로컬 파일의 원래 경로, 사용자 입력 시점처럼 출처를 재확인할 정보를 저장한다.

## 6. 노드 타입

초기에는 너무 세분화하지 않는다. 모든 지식 노드는 아래 닫힌 목록 중 하나의 `node_type`을 가져야 한다.

| node_type | 용도 | 예시 |
| --- | --- | --- |
| `concept` | 정의, 이론, 현상, 일반 개념 | Transformer의 Self-Attention |
| `method` | 절차, 알고리즘, 기법 | Chain-of-Thought prompting |
| `model` | 학습된 모델 또는 모델 계열 | Gemma 4 26B |
| `system` | 여러 구성 요소로 이루어진 소프트웨어/서비스 | LLM Wiki Local |
| `project` | 목표와 범위를 가진 사용자 작업 | NLP 학습 프로젝트 |
| `dataset` | 식별 가능한 데이터셋 | SQuAD v2 |
| `person` | 사람 | 논문 저자 |
| `organization` | 조직 | Google DeepMind |
| `event` | 날짜 또는 기간이 중요한 사건 | 모델 출시 |

`Source`, `SourceChunk`, `Claim`, `WikiPage`는 지식 노드 class가 아니다. 별도 entity schema를 사용한다.

새 class는 실제로 class별 규칙이 필요해질 때만 추가한다. 단순 분류 목적이라면 `tags`를 사용한다.

## 7. Knowledge Node 스키마

사용자가 제시한 frontmatter는 다음 형태로 정형화한다. `node_state: draft | reviewed | stable`처럼 가능한 값을 나열하지 않고, 실제 값 하나만 저장한다.

```yaml
---
id: concept-transformer-attention
record_type: knowledge_node
node_type: concept
title: "Transformer의 Self-Attention"
aliases: []
summary: "Transformer가 토큰 간 중요도를 계산하는 핵심 메커니즘이다."
node_state: draft
schema_version: 1
created_at: "2026-07-17T00:00:00+09:00"
updated_at: "2026-07-17T00:00:00+09:00"
created_by: llm
created_with:
  agent: local_llm
  model: google/gemma-4-26b-a4b-qat
source_ids:
  - source-arxiv-2408-1234
claim_ids:
  - claim-attention-mechanism-001
merged_from: []
tags:
  - nlp
  - architecture
relations:
  - id: relation-attention-extends-rnn-limitations
    relation_type: extends
    target_id: concept-rnn-limitations
    evidence_claim_ids:
      - claim-attention-rnn-comparison-001
    created_by: llm
    model_confidence: 0.8
    review_state: pending
  - id: relation-attention-part-of-nlp-study
    relation_type: part_of
    target_id: project-nlp-study
    evidence_claim_ids: []
    created_by: human
    model_confidence: null
    review_state: approved
---
```

본문은 정의, 핵심 Claim, 출처, 관계를 사람이 읽기 좋은 Markdown으로 작성한다. frontmatter의 구조화 필드는 시스템 검증과 검색을 위한 최소 정보만 둔다.

### 필수 필드

- `id`, `record_type`, `node_type`, `title`, `node_state`, `schema_version`
- `created_at`, `updated_at`
- `source_ids`, `claim_ids`, `relations`

### 선택 필드

- `aliases`, `summary`, `created_by`, `created_with`, `merged_from`, `tags`

### 필드 규칙

- `title`은 같은 node_type 안에서 중복을 피하지만, ID의 고유성만 강제한다.
- `aliases`는 title과 중복되거나 다른 alias와 대소문자만 다른 값을 허용하지 않는다.
- `source_ids`는 직접 근거 Source의 목록이며, `claim_ids`가 있으면 해당 Claim을 통해 추적 가능해야 한다.
- `merged_from`의 ID는 삭제하지 않는다. 병합 전 노드의 추적성을 유지한다.
- `created_by`와 `created_with`는 생성 이력일 뿐 신뢰도나 승인 상태를 결정하지 않는다.
- `tags`는 자유 분류다. ontology 관계나 node_type 검증에 사용하지 않는다.

## 8. Claim 스키마

Claim은 관계의 근거와 모순 검토의 중심이다. 하나의 Claim은 가능한 한 하나의 원자적 주장만 담는다.

```yaml
---
id: claim-attention-rnn-comparison-001
record_type: claim
claim_type: comparative
subject_id: concept-transformer-attention
claim_relation_type: improves_on
object_id: concept-rnn-limitations
statement: "Self-Attention은 순차 계산 제약이 있는 RNN의 장거리 의존성 처리 한계를 완화한다."
polarity: positive
qualifiers:
  scope: "sequence modeling"
  conditions: []
evidence:
  - source_id: source-arxiv-2408-1234
    chunk_id: chunk-arxiv-2408-1234-p03-s02
    locator: "p.3, section 2"
    quote: ""
model_confidence: 0.78
review_state: pending
conflicts_with: []
schema_version: 1
created_at: "2026-07-17T00:00:00+09:00"
updated_at: "2026-07-17T00:00:00+09:00"
extracted_by:
  agent: local_llm
  model: google/gemma-4-26b-a4b-qat
---
```

### Claim 필수 규칙

- `statement`는 사람이 읽을 수 있는 완전한 문장이다.
- `subject_id`와 `object_id`는 Knowledge Node ID 또는 값 객체여야 한다. 값 객체가 필요한 경우에는 v1에서 `object_value`를 사용하고, `object_id`와 동시에 쓰지 않는다.
- `claim_relation_type`은 Claim relation 목록에서 선택한다. Knowledge Node의 `relation_type`과 이름이 같아도 의미와 규칙은 별도다.
- `evidence`는 최소 하나 필요하다. 사람이 직접 만든 Claim도 `source_id: user-input-*` 같은 Source를 생성하여 출처를 남긴다.
- `quote`는 원문을 짧게 보조 인용할 때만 사용한다. 원문 전체를 복제하지 않는다.
- `model_confidence`는 LLM의 추출 확신도이지 사실 확률이 아니다. 사람이 직접 만든 Claim은 `null`을 사용한다.
- `polarity`는 `positive`, `negative`, `uncertain` 중 하나다.

### Claim 충돌 형식

상충 관계는 다음처럼 Claim에 기록한다. `claim_id`는 다른 Claim을 가리키며, 양쪽 Claim의 `statement`, `qualifiers`, `evidence`를 함께 검토해야 승인할 수 있다.

```yaml
conflicts_with:
  - claim_id: claim-static-embedding-insufficient-001
    conflict_scope: "contextual representation quality"
    created_by: human
    review_state: approved
```

`conflicts_with`는 대칭 관계다. SQLite 동기화 시 반대쪽 Claim에도 파생 index를 만들지만, Vault에서는 사람이 최초로 기록한 한쪽만 정본으로 둔다.

## 9. Relation 스키마

관계는 `source -> relation_type -> target`만으로는 부족하다. 누가, 어떤 근거로, 어떤 상태에서 관계를 만들었는지 남겨야 한다.

Concept frontmatter의 `relations` 배열은 아래 Relation 객체의 축약 표현이다. SQLite에서는 같은 `id`를 키로 `relations` table에 인덱싱한다.

| 필드 | 설명 |
| --- | --- |
| `id` | 전역 고유 relation ID |
| `relation_type` | ontology에 등록된 관계 이름 |
| `target_id` | 대상 Knowledge Node ID |
| `evidence_claim_ids` | 이 관계를 뒷받침하는 Claim ID 목록 |
| `created_by` | `human`, `llm`, `import`, `rule` 중 하나 |
| `model_confidence` | LLM/규칙 결과의 확신도. human이면 `null` |
| `review_state` | pending/approved/rejected/replaced |

`contradicts`는 Knowledge Node relation으로 허용하지 않는다. 이는 “개념 A와 B가 상충한다”는 모호한 표현이 되기 쉽다. 대신 서로 충돌하는 두 Claim을 `conflicts_with`로 연결하고, 충돌 조건과 근거를 기록한다.

## 10. Knowledge Node Relation Type 목록 v1

관계는 아래 닫힌 목록만 사용한다. `domain -> range`를 벗어나면 validator가 거부한다.

| relation_type | domain | range | 성질 | 의미 |
| --- | --- | --- | --- | --- |
| `related_to` | 모든 Knowledge Node | 모든 Knowledge Node | symmetric | 일반적 관련성. 다른 관계가 맞으면 우선 사용하지 않는다. |
| `part_of` | concept, method, model, system, dataset, event | concept, system, project, dataset, event | inverse: `has_part` | 구조적 또는 범위상 포함 관계 |
| `has_part` | concept, system, project, dataset, event | concept, method, model, system, dataset, event | inverse: `part_of` | 부분을 가짐 |
| `extends` | concept, method, model, system | concept, method, model, system | inverse: `extended_by` | 기존 대상의 범위나 기능을 확장함 |
| `extended_by` | concept, method, model, system | concept, method, model, system | inverse: `extends` | 확장됨 |
| `uses` | method, model, system, project | concept, method, model, system, dataset | inverse: `used_by` | 구현이나 작업에서 사용함 |
| `used_by` | concept, method, model, system, dataset | method, model, system, project | inverse: `uses` | 사용됨 |
| `depends_on` | method, model, system, project | concept, method, model, system, dataset | inverse: `required_by` | 대상이 없으면 성립/실행이 어려움 |
| `required_by` | concept, method, model, system, dataset | method, model, system, project | inverse: `depends_on` | 의존 대상임 |
| `implemented_by` | concept, method | method, model, system | inverse: `implements` | 개념/방법이 구체 구현을 가짐 |
| `implements` | method, model, system | concept, method | inverse: `implemented_by` | 개념/방법을 구현함 |

Source의 저자, 발행자, 수집자 정보는 relation이 아니라 Source의 `origin` metadata로 다룬다. v1은 Source를 ontology node로 올리지 않는다.

### 자동 추론 규칙

v1에서는 다음만 자동 생성한다.

- 승인된 `part_of`가 생기면 `has_part`를 파생 relation으로 생성한다.
- 승인된 `extends`, `uses`, `depends_on`, `implemented_by`가 생기면 inverse relation을 파생한다.
- `related_to`는 양방향으로 하나의 relation처럼 표시한다.

transitive closure는 v1에서 저장하거나 자동 승인하지 않는다. 예를 들어 A `part_of` B, B `part_of` C라고 해서 A `part_of` C를 relation row로 만들지 않는다. 검색 시 경로 확장 후보로만 활용한다.

## 11. Claim Relation Type 목록 v1

Claim의 predicate는 문장 수준의 주장에 사용한다.

| claim_relation_type | 예시 |
| --- | --- |
| `defines` | A는 B로 정의된다. |
| `has_property` | A는 속성 B를 가진다. |
| `improves_on` | A는 조건 C에서 B를 개선한다. |
| `causes` | A는 조건 C에서 B를 유발한다. |
| `enables` | A는 B를 가능하게 한다. |
| `limits` | A는 B를 제한한다. |
| `measures` | A는 B를 측정한다. |
| `uses` | A는 B를 사용한다. |
| `compares_with` | A는 B와 비교된다. |
| `reports_value` | A의 측정값은 B다. |

새 predicate를 추가하려면 이름, 설명, domain/range, 예시, 역관계 유무를 ontology registry에 함께 추가한다. 단순 표현 차이는 새 predicate가 아니라 `statement`와 `qualifiers`로 처리한다.

## 12. Ontology Registry 파일

검증기는 코드에 하드코딩한 목록이 아니라 버전이 있는 registry 파일을 읽는다. 초기 위치는 다음으로 둔다.

```text
ontology/
  v1.yaml
schemas/
  knowledge-node.v1.json
  claim.v1.json
```

`ontology/v1.yaml`의 핵심 구조는 아래와 같다.

```yaml
version: 1
node_types:
  - concept
  - method
  - model
  - system
  - project
  - dataset
  - person
  - organization
  - event
knowledge_relations:
  extends:
    domain: [concept, method, model, system]
    range: [concept, method, model, system]
    inverse: extended_by
    symmetric: false
    transitive: false
  part_of:
    domain: [concept, method, model, system, dataset, event]
    range: [concept, system, project, dataset, event]
    inverse: has_part
    symmetric: false
    transitive: query_only
claim_predicates:
  - defines
  - has_property
  - improves_on
  - causes
  - enables
  - limits
  - measures
  - uses
  - compares_with
  - reports_value
```

## 13. 검증 규칙

`wiki validate`는 최소한 다음을 검사한다.

- YAML frontmatter가 entity schema에 맞는지
- 모든 참조 ID가 존재하는지
- 노드의 `node_type`이 registry에 있는지
- Relation predicate가 registry에 있고 domain/range가 맞는지
- inverse relation이 SQLite index에 올바르게 파생됐는지
- Claim에 근거 `evidence`가 있는지
- Claim evidence의 Source와 Chunk가 존재하고 locator가 유효한지
- `approved` Relation이 `evidence_claim_ids` 또는 `created_by: human`의 명시적 근거를 가지는지
- 같은 source, claim_relation_type, target, scope를 가진 중복 Claim이 없는지
- 폐기된 노드가 새로운 Relation의 target으로 사용되지 않았는지

`wiki lint`는 schema 오류가 아니라 품질 신호를 낸다.

- `related_to`가 과도하게 사용된 경우
- 근거 없는 높은 `model_confidence`의 LLM relation
- 너무 넓은 Concept에 직접 연결된 Claim
- relation은 있지만 WikiPage 본문에 설명이 없는 경우
- `draft` 노드가 기본 답변 검색 결과에 노출되는 경우

## 14. 예시의 변경점

사용자가 제시한 예시에서 `extends`, `part_of`는 Knowledge Node relation으로 유지할 수 있다. 다만 다음 조건이 붙는다.

- `project-nlp-study`는 `node_type: project` 노드로 존재해야 한다.
- `extends`는 비교 근거인 Claim을 `evidence_claim_ids`에 연결해야 한다.
- `contradicts: concept-static-embedding`은 삭제한다. Self-Attention과 static embedding이 어느 조건에서 어떤 주장으로 충돌하는지를 Claim 두 개로 만들고, Claim 사이에 conflict를 기록한다.
- `node_state`에는 `draft` 같은 실제 값 하나만 기록한다.
- 날짜는 `created_at`, `updated_at`의 ISO 8601 timestamp를 사용한다.

## 15. v1에서 의도적으로 제외하는 것

- OWL/RDF 전체 호환과 추론 엔진
- 자유로운 node type 상속 체계
- 자동 관계 병합
- Claim 모순의 자동 판정
- 시간에 따라 변하는 사실의 완전한 temporal logic

이 기능들은 데이터가 누적된 뒤에도 필요성이 확인될 때 추가한다. v1은 출처가 있는 Claim, 제한된 Relation, 사람의 승인 흐름을 확실히 만드는 데 집중한다.
