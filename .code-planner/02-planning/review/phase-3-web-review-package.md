# Plan Review Package — Phase 3 Web Review UI

## Plan summary

Phase 3 Web UI는 단일 관리자용 Review 중심 UI입니다. 로그인 후 Dashboard에서 자료 처리 상태를 보고, Review 화면에서 LLM 신규 개념 후보를 기존 wiki와 비교해 병합/신규/retry 처리합니다.

## UX/UI review targets

- Dashboard에서 승인 필요/pending/오류/wiki 개수/시스템 상태가 즉시 보이는가
- Review Main의 3영역 구조가 이해되는가
  - 왼쪽: 기존 wiki 유사도 목록
  - 가운데: 선택한 기존 개념 내용
  - 오른쪽: 신규 개념 batch 카드
- batch 병합/신규 처리 흐름이 위험하지 않은가
- `reject + retry instruction` 흐름이 자연스러운가
- Graph popup의 1-hop 구조와 wiki 내용 패널이 충분한가
- Prompt Settings의 `test version → test run → confirm version` 흐름이 명확한가

## Mockup files

- Markdown: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.md`
- HTML: `.code-planner/02-planning/mockups/phase-3-web-review-mockup.html`

## Visual references / links

PRV review session에서 HTML mockup을 확인합니다.

## Review checklist

- [ ] Dashboard 정보 우선순위가 적절하다
- [ ] Review 3영역 구조가 적절하다
- [ ] 오른쪽 신규 개념 batch 카드 UX가 이해된다
- [ ] Graph popup이 과하지 않다
- [ ] Settings prompt versioning 흐름이 맞다
- [ ] Build 전에 추가할 UX 요구가 없다

## Known limitations

- 실제 데이터 연동 없는 정적 mockup입니다.
- 모바일 최적화는 우선순위에서 제외했습니다.
- 최종 HTML/CSS 구현 기술은 아직 확정하지 않았습니다.
