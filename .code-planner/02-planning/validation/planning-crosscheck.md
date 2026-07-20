# Planning Crosscheck — LLM Wiki Local

## Result

- checkResult: issues_found
- 실행: planning-crosscheck subagent
- 목적: README, ADRs, dependencies, git-plan, phases, features, mockups, review, validation-plan 간 충돌/누락/모호성 점검

## 핵심 결론

- Build handoff를 즉시 차단하는 대형 blocker는 없음.
- 다만 Build 직전에 잠그지 않으면 validation이 `blocked`로 갈 수 있는 결정들이 남아 있음.
- 가장 큰 누락은 ADR-004의 embedding 재임베딩/재인덱싱 정책이 validation-plan에 반영되지 않은 점.

## Conflicts

- Phase 2 문서에는 `vector/RAG search 확장`이 포함되어 있으나, Phase 2 feature contract에는 동일 항목이 약하게 표현됨.
- Phase 3 phase doc에는 mockup 승인/PRV feedback 경로가 있으나, Phase 3 feature contract에는 관련 cross-reference가 부족함.
- Phase 1 phase doc은 `sync/dry-run/apply 정책 확정`을 task로 두지만, feature contract에서는 사용자 질문으로 남아 있음.

## Missing Items

- ADR-004의 재임베딩/재인덱싱 정책이 validation-plan에 없음.
- Phase 3 validation에 `Wiki compile preview 펼침` UX 검증 항목이 부족함.
- `LLM_WIKI_AUTO_APPROVE_FOR_TESTS`가 어떤 CLI/Web 액션과 연결되는지 문서화 부족.
- Phase 2의 vector/RAG search 확장이 validation required/optional에 명확히 들어가야 함.

## Ambiguous Items

- Web backend/frontend stack 미확정
- Web Auth 방식 미확정
- `wiki sync` dry-run/`--apply` 정책 미확정
- settings 파일 형식 미확정
- `markitdown` optional/default dependency 미확정
- Phase 1 `ask/map/summarize` placeholder 범위 미확정
- prompt 변경 로그 정책(diff 중심 vs 버전별 전체 저장) 미확정
- `review_route` enum 충분성 미확정
- Graph popup 노드 클릭 시 wiki 내용 범위 미확정
- prompt rollback 필요성 미확정
- embedding model dimension reference 미기록

## Validation Mismatch

- ADR-004 재임베딩/재인덱싱 정책 ↔ validation-plan coverage mismatch
- Phase 3 Wiki compile preview UI action ↔ validation required check mismatch
- Phase 1 sync dry-run/apply 정책 ↔ validation check mismatch

## Recommended Regression Step

Stage 5/6 문서를 다음 항목 기준으로 짧게 보정한 뒤 Build handoff로 간다.

1. Web stack/auth 결정
2. `wiki sync` dry-run/`--apply` 정책 결정
3. settings 파일 형식 결정
4. `markitdown` dependency 등급 결정
5. prompt log 정책 결정
6. embedding 재임베딩/재인덱싱 validation 추가
7. Phase 2 vector/RAG search feature/validation 동기화
8. Phase 3 feature contract에 mockup approval cross-reference 추가

## Questions For User

1. Web backend/frontend stack은 무엇으로 확정할까?
2. Web Auth는 token/password 중 무엇으로 갈까?
3. `wiki sync`는 기본 dry-run + `--apply` 반영 정책으로 갈까?
4. settings 파일 형식은 TOML/YAML/JSON 중 무엇으로 갈까?
5. `markitdown`은 optional dependency로 둘까, default dependency로 둘까?
6. Phase 1 `ask/map/summarize` placeholder는 artifact 생성까지면 충분할까?
7. prompt 변경 로그는 diff 중심으로 볼까, 버전별 전체 저장으로 볼까?
8. `review_route` enum 4종으로 충분할까?
9. prompt versioning은 Settings에서만 관리하면 충분할까?
10. Graph popup에서 노드 클릭 시 summary/aliases/claims/relations 중 어디까지 보여줄까?
11. prompt rollback이 필요한가?
12. embedding dimension reference와 재임베딩/재인덱싱 정책을 validation에 추가할까?
13. `LLM_WIKI_AUTO_APPROVE_FOR_TESTS`는 어떤 액션에 연결할까?

## 반영 상태

- 아직 반영 전.
- 사용자 확인 후 Stage 5/6 문서를 보정한다.


## 사용자 결정 반영

- `wiki sync`: 기본 dry-run, 실제 반영은 `--apply`
- settings 파일 형식: YAML
- Web Auth: `.env` 사용자 비밀번호 기반
- prompt log: 버전별 전체 저장 + change note
- embedding/reindex: 신규 wiki 확정 시 즉시 추가, 필요 시 선택/전체 재인덱싱
- Phase 2 vector/RAG search와 Phase 3 Wiki compile preview 검증 보강
- Phase 3 feature contract에 mockup approval reference 추가

## 남은 확인

- 비-Markdown 변환 목표는 Markdown normalized 유지, MDX는 optional preview/export로 확정.
- 결정: Obsidian/LLM 정본 normalized format은 Markdown 유지, MDX는 Web preview/export optional로 둔다.
