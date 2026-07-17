# Mockup Spec — Review/Failed Workbench (existing UX based)

## 목적

기존 `/inbox` 화면의 좌측 list + 우측 preview/control 구조를 유지하면서 Review/Failed 작업대를 확장한다.

## 주요 사용자 흐름

1. 사용자가 `/inbox`에 들어온다.
2. 상단 filter에서 `Review` 또는 `Failed`를 선택한다.
3. 좌측 목록에서 item을 선택한다.
4. 우측에서 원본/후보/로그를 확인한다.
5. Review는 편입/새 생성/태깅/보류 중 하나를 선택한다.
6. Failed는 원인 확인 후 재시도/삭제/로그 삭제를 선택한다.

## Screen: Inbox Workbench

```text
┌─────────────────────────────────────────────────────────────┐
│ 문서 수신함                                                  │
│ [All] [Pending] [Review] [Failed]                            │
├───────────────────────┬─────────────────────────────────────┤
│ 대기/검토 목록         │ 선택 항목 상세                       │
│ - item title           │ title / slug / status / confidence   │
│ - status badge         │ source path / processed at           │
│ - reason short         │                                     │
│                       │ [Preview 원문/후보]                  │
│                       │                                     │
│                       │ Review mode:                         │
│                       │ 유사 Wiki 후보                       │
│                       │ ( ) entities/foo  similarity 0.89    │
│                       │ ( ) concepts/bar   similarity 0.72   │
│                       │ [기존 page에 편입] [새 page]          │
│                       │                                     │
│                       │ 태깅/분류 입력                        │
│                       │ kind: [entity|concept|review]         │
│                       │ tags: [...]                           │
│                       │ [수정 후 재처리] [보류] [삭제]        │
└───────────────────────┴─────────────────────────────────────┘
```

## Empty state

- “검토 대기 항목이 없습니다.”
- “실패 항목이 없습니다.”

## Success state

- Review 편입 완료: item은 `_Review`에서 제거되고 Wiki/source 연결이 갱신된다.
- Failed 재시도 성공: item은 `_Failed`에서 제거되고 Raw archive/Wiki 흐름으로 진행된다.

## Failure state

- 재시도 실패: 같은 item에 새 failure event/log를 추가한다.
- 편입 실패: item은 Review에 남고 error badge를 표시한다.

## Review questions

- 기존 `/inbox` 레이아웃을 유지하는 것이 충분한가?
- Review와 Failed를 tab/filter로 나누는 방식이 적절한가?
- 유사 후보와 별도 태깅 폼이 한 화면에 있으면 복잡하지 않은가?

## HTML/Lavish note

사용자는 별도 신규 목업 구현을 원하지 않았다. 따라서 Planning 후반 review에서는 기존 UX 기반 최소 HTML artifact만 만들고, 새 디자인이 아니라 기존 화면 확장 검토로 제한한다.
