# Feature Contract — Web UI and CLI integration

## 목적

기존 Web UI/CLI 흐름을 Inbox-first에 맞게 재정비한다.

## 기존 UX 기반 원칙

- 별도 신규 디자인 시스템을 만들지 않는다.
- 기존 `/ingest`, `/inbox`, `/jobs` 레이아웃과 색/카드/상태 badge 패턴을 유지한다.
- 필요한 컴포넌트만 확장한다.

## Web UI 대상

### `/ingest`

- 현재 drop zone 유지.
- Raw Sources 스캔 중심 문구를 Inbox 등록 중심으로 변경.
- Raw Sources action은 “Raw Sources에서 Inbox로 가져오기”로 표현한다.
- Files/Markdown/Text 입력 유형을 구분한다.
- Inbox pending queue를 표시한다.
- 처리 시작은 `inbox_item_id`를 기준으로 하며 내부에서 `source_id`를 생성/연결한다.

### `/inbox`

- 현재 좌측 list + 우측 preview/control panel 구조 유지.
- Review/Failed tab 또는 filter 추가.
- Review 후보 상세:
  - 유사 Wiki 후보
  - 편입 선택
  - 별도 태깅/분류 폼
- Failed 상세:
  - 로그/리포트
  - 재시도/삭제/로그 삭제

### `/jobs`

- 기존 job list와 status badge 유지.
- source_id 대신 inbox_item_id도 표시 가능해야 한다.
- chunked extraction 진행률을 job phase/progress로 표시한다.

## CLI 대상

- `wiki add`: Inbox로 등록하는 의미로 전환 또는 신규 alias 제공.
- `wiki ingest`: Inbox pending 처리.
- `wiki status`: Inbox/Failed/Review count 표시.
- `wiki retry <inbox_item_id>`: Failed item 재시도 최소 지원.
- Review 상세 처리(유사 Wiki 편입/태깅/분류)는 Web UI 중심으로 제공한다.
- CLI `review`는 Build 필수 범위가 아니며, `wiki status`가 Review count와 Web URL hint를 보여주는 수준이면 충분하다.

## Acceptance criteria

- Web UI와 CLI가 같은 상태 모델을 공유한다.
- `inbox_item_id -> source_id -> ingest_job` materialize/link가 검증된다.
- 기존 Raw Sources 문서는 직접 processing queue가 아니라 Inbox pending으로 import된 뒤 처리된다.
- UX 테스트는 Inbox pending item이 실제 job/LLM pipeline으로 들어가는 5A 검증 후에만 진행한다.
- 사용자는 현재 UX 패턴 안에서 새 흐름을 이해할 수 있다.
- Review/Failed 처리가 화면 전환 없이 가능하다.
