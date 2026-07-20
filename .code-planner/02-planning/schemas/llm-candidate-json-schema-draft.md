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
