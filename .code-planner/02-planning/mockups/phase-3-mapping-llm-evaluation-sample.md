# Phase 3 Mapping — LLM Evaluation Sample

## 목적

Mapping UX를 확정하기 위해, LLM이 최종적으로 생성할 수 있는 후보 평가 결과 예시를 고정한다.

이 샘플은 실제 구현 schema가 아니라 UX 판단용 예제다.

## 상황 예시

사용자가 Inbox에 `paper-agentic-rag.md`를 넣었다.

LLM 자동 처리 후 기존 wiki `RAG` 문서와 관련된 여러 후보가 생성되었다.

현재 Mapping에서 열린 wiki:

```yaml
wiki_id: concept_rag
title: RAG
path: vault/10_Wiki/concepts/rag.md
aliases:
  - Retrieval-Augmented Generation
existing_relations:
  - RAG --uses--> Vector Search
  - RAG --uses--> LLM
```

## LLM 후보 평가 결과 예시

```json
{
  "evaluation_id": "eval_20260719_agentic_rag_001",
  "source": {
    "source_id": "src_paper_agentic_rag",
    "title": "paper-agentic-rag.md",
    "path": "vault/00_Inbox/files/paper-agentic-rag.md"
  },
  "current_wiki_context": {
    "concept_id": "concept_rag",
    "title": "RAG",
    "path": "vault/10_Wiki/concepts/rag.md"
  },
  "model_run": {
    "provider": "ollama",
    "model": "llama3.1:8b",
    "prompt_version": "mapping-eval-confirmed-v3",
    "schema_version": "candidate-envelope-v1",
    "finished_at": "2026-07-19T01:20:00Z"
  },
  "candidates": [
    {
      "candidate_id": "cand_alias_001",
      "type": "alias",
      "proposed_value": "Retrieval Augmented Generation",
      "target_wiki_id": "concept_rag",
      "llm_recommendation": "add_to_current_wiki",
      "confidence": 0.94,
      "reason": "The phrase is a spelling variant of the existing alias with the same meaning.",
      "evidence": [
        {
          "quote": "Retrieval Augmented Generation (RAG) combines retrieved context with generation.",
          "locator": "chunk_3"
        }
      ]
    },
    {
      "candidate_id": "cand_claim_001",
      "type": "claim",
      "proposed_value": "RAG improves answer grounding by injecting retrieved context into the generation step.",
      "target_wiki_id": "concept_rag",
      "llm_recommendation": "add_to_current_wiki",
      "confidence": 0.87,
      "reason": "The claim directly describes the mechanism of RAG and is supported by the source text.",
      "evidence": [
        {
          "quote": "The retrieved documents are provided as context before the model generates the answer.",
          "locator": "chunk_5"
        }
      ]
    },
    {
      "candidate_id": "cand_relation_001",
      "type": "relation",
      "source_concept": {
        "concept_id": "concept_rag",
        "title": "RAG"
      },
      "relation_label": "uses",
      "target_concept": {
        "concept_id": "concept_vector_search",
        "title": "Vector Search"
      },
      "direction": "outgoing_from_current_wiki",
      "llm_recommendation": "confirm_existing_or_strengthen",
      "confidence": 0.91,
      "reason": "The source repeatedly states that RAG uses vector search to retrieve relevant chunks.",
      "evidence": [
        {
          "quote": "RAG retrieves relevant chunks using vector similarity search.",
          "locator": "chunk_7"
        }
      ],
      "existing_relation_status": "already_exists"
    },
    {
      "candidate_id": "cand_concept_001",
      "type": "concept",
      "proposed_value": {
        "title": "Agentic RAG",
        "summary": "A RAG pattern where an agent decides when and how to retrieve, reason, and call tools.",
        "aliases": ["Agent-based RAG"]
      },
      "similar_existing_wiki": [
        {
          "concept_id": "concept_rag",
          "title": "RAG",
          "similarity": 0.72,
          "match_reason": "Parent/general concept"
        },
        {
          "concept_id": "concept_llm_agent",
          "title": "LLM Agent",
          "similarity": 0.68,
          "match_reason": "Shares agent behavior"
        }
      ],
      "llm_recommendation": "create_new_concept_and_link_to_current_wiki",
      "recommended_relation_to_current_wiki": {
        "source": "Agentic RAG",
        "relation_label": "specializes",
        "target": "RAG",
        "direction": "candidate_to_current_wiki"
      },
      "confidence": 0.81,
      "reason": "Agentic RAG is related to RAG but introduces agent decision loops, so it should be separate and linked as a specialization.",
      "evidence": [
        {
          "quote": "Agentic RAG lets the agent decide whether to retrieve, refine the query, or call a tool.",
          "locator": "chunk_11"
        }
      ]
    },
    {
      "candidate_id": "cand_relation_002",
      "type": "relation",
      "source_concept": {
        "title": "Agentic RAG",
        "is_new_candidate": true
      },
      "relation_label": "uses",
      "target_concept": {
        "concept_id": "concept_tool_use",
        "title": "Tool Use"
      },
      "direction": "candidate_to_existing_wiki",
      "llm_recommendation": "defer_until_new_concept_created",
      "confidence": 0.74,
      "reason": "This relation depends on whether Agentic RAG is created as a new concept.",
      "evidence": [
        {
          "quote": "The agent can call tools before deciding whether retrieval is necessary.",
          "locator": "chunk_12"
        }
      ]
    }
  ],
  "summary_for_human": {
    "recommended_actions": [
      "Add alias to RAG",
      "Add claim to RAG",
      "Confirm/keep existing RAG -> Vector Search relation",
      "Create new concept Agentic RAG",
      "After creating Agentic RAG, consider linking it to Tool Use"
    ],
    "requires_human_attention": [
      "Whether Agentic RAG should be a separate concept or merged into RAG",
      "Whether relation Agentic RAG -> Tool Use should be added immediately or deferred"
    ]
  }
}
```

## 이 샘플에서 Mapping UI가 지원해야 하는 판단

### 현재 wiki에 바로 추가 가능한 것

- alias 후보
- claim 후보
- 현재 wiki에서 나가는 relation 후보

UI action:

```text
Add alias to RAG
Add claim to RAG
Confirm relation RAG → Vector Search
```

### 신규 개념으로 만들 가능성이 높은 것

- `Agentic RAG`

UI action:

```text
Create new concept “Agentic RAG”
Create and link: Agentic RAG --specializes--> RAG
```

### 신규 개념 생성 후에야 판단 가능한 것

- `Agentic RAG --uses--> Tool Use`

UI action:

```text
Defer until “Agentic RAG” is created
```

## UX 시사점

Mapping은 단순히 후보 하나를 기존 wiki 하나에 merge하는 화면이 아니다.

현재 wiki 기준으로 여러 후보를 묶어서 보여줘야 한다.

권장 candidate grouping:

```text
For current wiki “RAG”

Quick add
- alias candidates
- claim candidates
- relation candidates where source/target is current wiki

New concept candidates
- concepts related to current wiki
- create + link options

Deferred candidates
- candidates depending on another candidate decision
```

권장 action group:

```text
Add to current wiki
Create new and link
Defer
Reject + retry
```
