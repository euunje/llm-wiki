# Feature Contract — Phase 2 LLM Wiki Quality

## Phase 목적

Phase 1의 CLI 기반 위에 실제 LLM wiki 품질을 올린다. Claim/Concept/Relation 후보, mapping, WikiPage compile, 비-Markdown 변환을 사람이 검토할 수 있는 수준으로 만든다.

## 주요 사용자 흐름

```text
source/chunk 준비
  -> extract-claims prompt 실행
  -> node/relation/mapping 후보 생성
  -> review_route로 검토 흐름 분류
  -> reject reason + retry instruction 처리
  -> WikiPage compile preview 생성
  -> 필요 시 PDF/HTML/Office 입력을 Markdown으로 변환
```

## 포함 기능

### 1. LLM schema 고도화

- 후보 출력 envelope 확정
- `review_route`로 검토 라우팅 통합
- `human_decision` 분리
- `retry_instruction`은 runner/human 메타로 별도 저장
- retry 후 이전 후보는 `superseded` 처리
- `propose_relations`에서 같은 응답의 `new_node candidate_key` 참조 허용

### 2. Prompt 품질

- `extract_claims`
- `map_candidates`
- `propose_relations`
- `detect_claim_conflicts`
- `compile_wiki`
- `ask`

### 3. Prompt versioning

- task별 prompt version 기록
- 변경점 logging
- AgentRun에 prompt version 연결
- Web Settings에서 관리 가능하게 설계

### 4. WikiPage compile 품질

- YAML frontmatter
- Claim/Source/Concept 링크
- 관련 개념
- 근거 Claims
- 기존 파일 diff/preview
- 승인 전 자동 반영 금지

### 5. Non-Markdown conversion

- PDF/Office/HTML/URL 변환
- `markitdown` adapter 후보
- 변환 결과는 normalized Markdown으로 저장
- 실패 artifact 기록

## 제외 기능

- Web UI 자체 구현
- 다중 사용자 승인
- 자동 승인 기반 지식 반영

## 성공 상태

- 동일 Source에 대해 prompt version별 결과 artifact를 비교할 수 있다.
- reject + retry instruction 후 이전 후보가 `superseded`되고 새 후보와 연결된다.
- WikiPage preview가 Obsidian Markdown 형식으로 생성된다.
- 비-Markdown 입력이 converter adapter를 통해 Markdown으로 들어온다.

## 사용자 검토 질문

1. `review_route` enum은 `normal_review`, `needs_merge_decision`, `needs_retry`, `conflict_flag`로 충분한가?
2. prompt 변경 로그는 버전별 전체 prompt 저장 + change note로 확정한다.
3. `markitdown`/MDX 변환 방향은 추가 확인 후 확정한다.


## 확정 보정

- Prompt 변경 로그: 버전별 전체 prompt 저장 + change note
- 신규 wiki 확정 시 즉시 embedding/index 추가
- 사용자가 필요 시 선택 항목 또는 전체 재인덱싱 가능
- vector/RAG search 확장은 Phase 2 범위에 포함
- 정본 normalized format은 Markdown 유지. MDX는 Web preview/export optional format으로 확정.
