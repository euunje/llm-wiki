# Phase 4 User Functional Test Checklist

Phase: 4 — Review/Failed workbench behavior

이 phase는 UI/UX 변경을 포함합니다. 실제 화면 확인이 필요하므로 아래 항목을
직접 확인해주세요. 모든 항목 OK여야 commit 가능합니다.

## 실행 환경

1. 기존 dev 워크트리에서 `/ingest` 또는 `/inbox` URL을 통해 dev server를 띄우거나,
   TestClient 기반 스모크(`uvicorn src.llm_wiki.webapp.main:app`)를 직접 띄웁니다.
2. Phase 4 mockup(`.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.html`)
   스크린샷이나 페이지를 열어둔 채 비교합니다.

## 화면 단독 확인 (Master 가능, 단 OK여야 commit)

1. `/inbox?state=all` 기본 렌더
   - 좌측 list에 pending/review/failed item이 모두 보이는지.
   - 우측 detail panel이 선택된 item 또는 첫 item의 메타데이터/preview를 보이는지.
   - legacy `non_categories/*.md` 항목이 unified 목록에 함께 보이는지.
2. `/inbox?state=pending`
   - 좌측 list에서 failed/review 항목이 보이지 않는지.
3. `/inbox?state=review`
   - 좌측 list의 배지가 amber/review, 각 항목에 review reason이 표시되는지.
   - 우측 detail panel에 "유사 Wiki 후보" 라디오 리스트, "기존 page에 편입"/"새 page 생성" 버튼,
     kind select, tags input, "수정 후 재처리"/"보류"/"삭제" 버튼이 보이는지.
4. `/inbox?state=failed`
   - 좌측 list의 배지가 red/failed, 각 항목에 failed phase가 표시되는지.
   - 우측 detail panel에 source path, failed phase, error, log preview, "재시도"/"원본 열기"/"삭제"/"로그만 삭제" 버튼이 보이는지.
5. Empty state
   - 위 4가지 상태에서 각각 비어 있을 때 승인된 mockup의 한국어 카피(검토 대기 항목이 없습니다 / 실패 항목이 없습니다 / 수신함이 비어 있습니다)가 보이는지.

## 액션 단독 확인 (Master 가능, 단 OK여야 commit)

6. Review 편입 (DB-backed review item)
   - 후보 라디오 선택 후 "기존 page에 편입" 클릭 시 alert+reload 흐름이 뜨는지.
   - 서버에 `review_classification_submitted` 이벤트가 inbox_events에 추가되는지.
7. Review 새 page 생성
   - kind select 후 "새 page 생성" 클릭 시 같은 이벤트 흐름.
8. Review 태깅/분류
   - kind select + tag 입력 후 "태깅/분류 저장" 시 같은 이벤트 흐름.
9. Review reprocess/hold/delete
   - 각각 200 응답 후 list에서 사라지거나 hold 처리되는지, file/diagnostic이 의도대로 정리되는지.
10. Failed retry
    - "재시도" 클릭 시 item state=pending, source가 input-type inbox folder로 이동, diagnostic sidecar가 삭제되는지.
11. Failed "로그만 삭제"
    - diagnostic sidecar만 삭제되고 source 파일은 남는지.
12. Failed delete (item 삭제)
    - source + diagnostic + DB row/events 정리되는지.

## 회귀 확인 (옵션)

13. 기존 pending promote/delete 흐름(`/api/inbox/promote/{slug}`, `/api/inbox/delete/{slug}`)이 그대로 동작하는지.
14. `/ingest` 등 다른 페이지가 정상적으로 렌더되는지.
15. (선택) 셀렉터로 다른 item 선택 시 sidebar 하이라이트와 detail panel이 동기화되는지.

## 기준

- 위 항목 중 어떤 것이든 실패하면 commit 전에 Fix Build 후 재검증 필요.
- Master 환경에서 OK면 `/check phase-4` 재실행 → `changes_requested` → Fix Build → 재체크 흐름으로 진행.
