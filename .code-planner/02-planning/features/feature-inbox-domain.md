# Feature Contract — Inbox domain and state model

## 목적

Inbox-first ingest의 공통 상태 모델을 정의한다.

## 사용자 가치

사용자는 새 입력, 처리중, 실패, 리뷰, 성공 archive 상태를 명확히 볼 수 있다.

## 핵심 객체

### Inbox item

- 원본 입력 1개를 나타낸다.
- 입력 유형:
  - `document_file`
  - `markdown_file`
  - `pasted_text`
- 주요 상태:
  - `pending`: Inbox에 등록됨
  - `processing`: 처리중/lock 획득
  - `failed`: 실패, `Inbox/_Failed`에 있음
  - `review`: 검토 필요, `Inbox/_Review`에 있음
  - `archived`: Raw Sources archive로 이동됨
  - `ingested`: Wiki/source page 반영 완료

### Inbox event

- 상태 변화 로그.
- 파일 이동, LLM error, validation error, review action, archive 이동 결과를 기록한다.

### Candidate review

- 기존 Wiki 유사도 후보와 사용자 선택 결과를 저장한다.
- 편입 후보가 없을 경우 별도 태깅/분류 입력 결과를 저장한다.

## 주요 규칙

- Raw Sources는 input이 아니라 archive다.
- 성공한 원본만 Raw Sources archive로 이동한다.
- 실패 원본은 `Inbox/_Failed`로 이동한다.
- Review 원본/후보는 `Inbox/_Review`로 이동한다.
- 같은 원본을 물리적으로 중복 복사하지 않는다.
- chunk는 파일이 아니라 처리 메타데이터다.

## Edge cases

- 동일 content hash 재유입
- 파일명 충돌
- 처리중 서버 재시작
- Web/CLI 동시 처리
- archive 이동 실패

## Acceptance criteria

- 모든 Inbox item은 DB 상태와 파일 위치가 일관된다.
- 실패/리뷰/성공 이동이 재시도 가능하다.
- 상태 이벤트만으로 원인 파악이 가능하다.
