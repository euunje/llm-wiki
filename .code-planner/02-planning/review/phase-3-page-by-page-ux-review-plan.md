# Phase 3 Page-by-Page UX Review Plan

## 상태

- Status: `planning_revision_required`
- Reason: 현재 Phase 3 Web UI 구현은 페이지별 사용자 목적과 흐름이 충분히 명확하지 않아 UX 구현이 미흡함.
- 원칙: 구현을 먼저 고치지 않고, 페이지 단위로 UX 의도 → 정보구조 → 기능 → validation 기준을 다시 확정한다.

## 전역 UX 원칙

- **PC 화면이 기본이다.** 주요 정보량과 조작 흐름은 데스크톱/노트북 화면 기준으로 설계한다.
- **Tablet/Mobile도 지원한다.** 모바일이 1차 사용 환경은 아니지만, 조회/간단 조작이 깨지지 않아야 한다.
- **아이콘 + 간단한 설명 기반 디자인을 사용한다.** 긴 가이드 문단보다 아이콘, 짧은 label, 1줄 helper text, 상태 chip으로 의미를 전달한다.
- 화면마다 사용자의 다음 행동이 명확해야 한다.
- 개발자용 내부 용어는 필요한 경우에만 보조 설명으로 숨겨서 제공한다.

## 반응형 기준

| Viewport | 설계 기준 |
|---|---|
| PC wide `≥1280px` | 기본 레이아웃. 좌측 nav/목차 + 본문 + 우측 보조 패널 허용 |
| Tablet `768–1279px` | 2-column 또는 접이식 side panel |
| Mobile `<768px` | 단일 column, 주요 CTA 우선, 보조 정보는 accordion/drawer |

## Visual language

- Navigation item: icon + short label
- Action button: verb 중심 짧은 문구, 예: `Test`, `Browse`, `Scan`, `Process`, `Merge`
- 설명: 1줄 helper text 우선, 긴 설명은 `details`, tooltip, help drawer로 이동
- 상태: `configured`, `missing`, `passed`, `failed`, `needs mapping` 같은 chip으로 표시
- 페이지 상단에는 긴 사용법 문단을 두지 않는다. 필요 시 빈 상태/오류 상태에서만 설명한다.

## 검토 방식

각 페이지는 아래 순서로 확인한다. 페이지별 PRV를 매번 열지 않고, 대화 기반 검토와 문서 업데이트를 먼저 완료한다. 모든 페이지의 UX spec/mockup이 정리된 뒤 최종 단계에서 전체 PRV 리뷰를 연다.

```text
페이지 초안 작성
→ 사용자 검토
→ 필요한 부분에 대한 질의/응답
→ 문서 업데이트
→ 해당 페이지 임시 확정
→ 다음 페이지 진행
→ 전체 페이지 완료 후 최종 PRV 리뷰
```

1. 페이지 목적
   - 사용자가 이 페이지에 들어온 이유
   - 이 페이지에서 끝내야 하는 작업
2. 주요 사용자 흐름
   - 첫 진입 상태
   - 정상 처리 흐름
   - 빈 상태 / 오류 상태
   - 다음 페이지로 이어지는 흐름
3. 화면 구성
   - 상단/좌측/본문/우측/하단 영역 역할
   - 표시해야 할 핵심 정보
   - 숨겨야 할 기술 정보
4. 필요한 API/데이터
   - 조회 데이터
   - 저장/실행 action
   - 민감정보 처리
5. 승인 기준
   - 사용자가 화면만 보고 의미를 이해할 수 있는가
   - 클릭해야 할 다음 행동이 명확한가
   - 불필요한 개발자용 정보가 노출되지 않는가

## 검토 대상 페이지

### 1. Onboarding / Setup

Purpose: 첫 실행 또는 설정 변경 시 LLM, Vault, Workflows/Tasks 구조를 사용자 중심 wizard로 설정한다.

Must cover:

- LLM provider 선택: Ollama / LM Studio / Custom OpenAI-compatible
- provider별 endpoint 기본값 제안
- API key 입력 후 화면에 재노출하지 않음
- 연결 테스트
- 모델 목록 조회 및 선택
- 신규 vault / 기존 vault 선택
- 전체 경로 file browser
- 기존 vault folder mapping
- `Source input → CLI/LLM task → Raw Source/Review` 구조 설명 및 설정

### 2. Dashboard

Purpose: 현재 시스템 상태와 다음 행동을 한눈에 보여준다.

Must cover:

- 처리 대기 source/task 수
- LLM 처리 상태
- Review 대기 수
- Wiki 문서 수
- 오류/실패 작업
- 다음 액션 CTA

### 3. Inbox

Purpose: 사용자가 처리할 자료를 업로드하거나 텍스트로 추가하고, 자동 처리 상태를 확인한다.

Must cover:

- 사용자 파일 업로드
- 사용자 텍스트 입력
- `vault/00_Inbox/memo`, `files`, `text`에서 발견된 입력 목록
- status: new / processing / needs_mapping / completed / failed
- 자동 처리 progress chip
- `Process selected`
- 후보 생성 완료 시 `Open Mapping`

### 4. Vault Browser

Purpose: 전체 vault 폴더와 내용을 읽어보고, 시스템이 어떤 문서를 어디에 두는지 확인한다.

Must cover:

- 전체 OS/vault 경로 tree
- `00_Inbox`, `10_Wiki`, `20_Review`, `80_Raws`, `90_Settings` 구분
- 파일 내용 viewer
- Markdown preview / raw toggle
- 읽기 실패/권한 오류 상태

### 5. Wiki

Purpose: 확정된 wiki 문서를 목차형 탐색으로 읽고 관계를 따라 이동한다.

Must cover:

- 왼쪽은 카드가 아닌 목차/list UX
- 본문 상단 파일 위치 표시
- frontmatter는 본문 상단에 노출하지 않음
- Markdown viewer 렌더링
- 우상단 1-hop graph
- relation 클릭 시 대상 wiki로 이동
- raw markdown은 필요 시 toggle/details로만 표시

### 6. Mapping

Purpose: 자동 처리 이후 생성된 후보를 기존 wiki와 비교해 merge/create/retry를 결정한다.

Must cover:

- 상단 가이드 제거
- 신규 후보는 compact floating list
- 클릭 시 확장 detail
- LLM 평가 내용, 신규값, evidence 표시
- 기존 wiki 후보와 비교
- merge target 명확화
- create new / retry instruction flow

### 7. Settings — LLM / Models / Routes

Purpose: LLM 연결, 모델 registry, 작업별 route를 명확히 관리한다.

Must cover:

- provider/endpoint/API key configured 상태
- 모델 목록 refresh
- 모델 registry 편집
- route는 “작업별 사용할 모델 선택”임을 명확히 설명
- 모델 설정 전 route save 비활성화

### 8. Settings — Prompt

Purpose: 현재 적용 중인 prompt와 test prompt 상태를 구분한다.

Must cover:

- schema default prompt
- confirmed prompt
- test prompt
- 현재 적용 중인 prompt
- schema compatibility
- test → confirm 흐름

## 페이지별 산출물

각 페이지 확정 시 다음 문서를 만든다.

```text
.code-planner/02-planning/mockups/phase-3-page-<page>-ux-spec.md
.code-planner/02-planning/mockups/phase-3-page-<page>-mockup.html
```

HTML mockup은 최종 구현 전 visual review 대상으로 사용한다.

## PRV 리뷰 정책

- 페이지별 초안 단계에서는 PRV를 필수로 열지 않는다.
- PRV는 전체 페이지 spec/mockup이 모인 뒤 최종 리뷰용으로 연다.
- 최종 PRV package에는 다음을 포함한다.
  - 페이지별 UX spec
  - 페이지별 HTML mockup
  - 남은 결정사항 목록
  - Build fix handoff 후보 문서
  - 사용자 승인 체크리스트

## 페이지별 진행 상태

| Page | Spec | HTML Mockup | User Q/A | Status |
|---|---|---|---|---|
| Onboarding / Setup | updated | updated | answered | provisional_ready |
| Inbox | updated | integrated_mockup | answered | provisional_ready |
| Vault Browser | drafted | integrated_mockup | answered | provisional_ready |
| Wiki | drafted | integrated_mockup | answered | provisional_ready |
| Mapping | updated | integrated_mockup | answered | provisional_ready |
| Settings — LLM / Models / Routes | updated | integrated_mockup | answered | provisional_ready |
| Settings — Prompt | updated | integrated_mockup | answered | provisional_ready |
| Dashboard | updated | integrated_mockup | answered | provisional_ready |
| Error handling / navigation | drafted | not_started | answered_partial | review_pending |

Integrated HTML mockup:

- `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`

## 권장 진행 순서

1. Onboarding / Setup
2. Inbox
3. Vault Browser
4. Wiki
5. Mapping
6. Settings LLM/Models/Routes
7. Settings Prompt
8. Dashboard

Dashboard는 다른 페이지들의 상태/CTA를 모아야 하므로 마지막에 확정한다.

## 현재 결론

현재 구현을 계속 패치하는 방식은 비효율적이다. Phase 3 UI는 위 페이지 단위로 UX spec/mockup을 다시 확정한 뒤 Build fix로 넘긴다.

## Final approval

- Status: `approved_for_build_fix`
- Approval record: `.code-planner/02-planning/review/phase-3-ux-mockup-approval.md`
- Approved mockups:
  - `.code-planner/02-planning/mockups/phase-3-ui-integrated-mockup.html`
  - `.code-planner/02-planning/mockups/phase-3-page-onboarding-mockup.html`
- Build must not change the approved UX direction without explicit user approval.
