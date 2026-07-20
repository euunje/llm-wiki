# Phase 2 — LLM Wiki Quality

## Purpose

Phase 1의 CLI 기반 위에 실제 LLM wiki 품질을 올린다. Claim/Concept/Relation 후보, mapping, WikiPage compile, 비-Markdown 변환을 사람이 검토 가능한 수준으로 만든다.

## User-visible outcome

- LLM이 Source/Chunk에서 Claim 후보를 추출한다.
- Concept/Relation/Mapping 후보가 `review_route`와 함께 저장된다.
- reject + retry instruction 이후 이전 후보가 `superseded`되고 새 후보와 연결된다.
- WikiPage compile preview
- vector/RAG search 확장가 Obsidian Markdown 형식으로 생성된다.
- PDF/Office/HTML/URL 자료가 Markdown으로 변환되어 파이프라인에 들어간다.

## Related mockup

- not_applicable: Phase 2는 주로 schema/prompt/page 품질 phase이다. Web Review 표시는 Phase 3 목업을 참조한다.

## Included features

- LLM 후보 JSON schema 확정
- `review_route` 통합
- `human_decision` 분리
- `retry_instruction` runner/human 메타
- `superseded` 후보 연결
- `propose_relations`의 `new_node candidate_key` 참조 허용
- `extract_claims`, `map_candidates`, `propose_relations`, `detect_claim_conflicts`, `compile_wiki`, `ask` prompt 품질
- prompt test version → test run → confirmed version 흐름
- prompt change logging
- WikiPage compile preview
- vector/RAG search 확장
- `markitdown` adapter 후보를 통한 비-Markdown 변환

## Excluded features

- Web UI 구현 자체
- 다중 사용자 승인
- 승인 전 자동 Vault 반영

## Tasks

1. LLM schema 세부 JSON 필드 확정
2. Validator 규칙 확정
3. review_route enum 최종 확정
4. human_decision/retry_instruction/superseded 저장 구조 확정
5. prompt versioning 저장 위치와 diff/log 정책 확정
6. WikiPage frontmatter/link/claim/source 포함 규칙 확정
7. converter adapter 인터페이스 확정

## Git checkpoint

- `phase-2-llm-wiki-quality`

## Entry criteria

- Phase 1 CLI foundation 완료
- Source/Chunk/Embedding/Artifact 기반 존재
- LLM endpoint 연결 테스트 가능

## Exit criteria

- 동일 Source에 대해 prompt version별 artifact 비교 가능
- rejected 후보 retry 시 superseded 연결 보존
- WikiPage preview 생성 가능
- 비-Markdown 변환 결과가 normalized Markdown으로 저장됨


## 확정 보정

- Prompt 변경 로그: 버전별 전체 prompt 저장 + change note
- 신규 wiki 확정 시 즉시 embedding/index 추가
- 사용자가 필요 시 선택 항목 또는 전체 재인덱싱 가능
- vector/RAG search 확장은 Phase 2 범위에 포함
- 정본 normalized format은 Markdown 유지. MDX는 Web preview/export optional format으로 확정.
