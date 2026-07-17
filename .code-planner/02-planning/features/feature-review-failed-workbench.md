# Feature Contract — Review/Failed workbench

## 목적

`Inbox/_Review`와 `Inbox/_Failed`를 사용자가 처리 가능한 작업대로 만든다.

## Review로 올라오는 조건

- 기존 Wiki와 유사하지만 merge 확신이 낮음
- 여러 기존 page와 중복/충돌 가능성 또는 multiple exact/near matches
- low/ambiguous/pending confidence
- entity/concept 분류 애매함
- guide/runbook/map/MOC 등 canonical Wiki page가 아닌 내용
- JSON validation 실패 후 retry 실패
- allowed_links violation 또는 links_used/body wikilink mismatch
- source reference 누락/불명확
- source/canonical slug conflict
- chunk별 extraction 결과 충돌
- 사람이 승인해야 할 merge/update 후보

## Review UI 동작

- 기존 Wiki 유사 후보 표시
  - title
  - slug
  - similarity/reason
  - 기존 page preview
- 사용자 action
  - 기존 page에 편입
  - 새 entity/concept로 생성
  - 별도 태깅/분류 입력
  - 수정 후 재처리
  - 거절/보류

## Failed UI 동작

- 원본 파일 표시
- 실패 phase 표시
- sanitized error/log 표시
- action
  - 재시도
  - 원본 열기
  - 보류/archive
  - 삭제
  - 로그 삭제

## Acceptance criteria

- Review item은 사용자가 편입/생성/태깅/보류 중 하나를 선택할 수 있다.
- Failed item은 원인 파악과 재시도가 가능하다.
- 로그는 민감정보를 과도하게 저장하지 않는다.
