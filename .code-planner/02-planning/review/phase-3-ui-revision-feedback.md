# Phase 3 UI Revision Feedback — 2026-07-19

## 상태

- Review result: `changes_requested`
- Source: Tailnet UI 확인 중 사용자 피드백
- Scope: Phase 3 Web UI UX/IA 재설계 수준 변경

## 사용자 피드백 원문 요약

### 1. Onboarding UX 재설계

- 현재 입력 폼 중심 UX가 아니라 사용자 중심 wizard/dropdown/file browser UX 필요.
- LLM 선택 흐름:
  1. provider 선택: `ollama`, `lmstudio` 등
  2. endpoint 주소 입력/추천
  3. API key 입력 또는 설정
  4. 시스템에서 연결 테스트
  5. 연결 결과 기반 모델 목록 제공
- Vault 선택 흐름:
  - 신규 vault / 기존 vault 사용 선택
  - 기존 vault는 mapping 필요
  - 신규 vault는 사용할 경로를 file browser로 선택

### 2. Wiki 본문 뷰어 재설계

- Markdown 원문이 그대로 보이지 않고 Markdown viewer로 렌더링되어야 함.
- 우상단에 1-hop graph 제공.
- graph 관계값을 눌러 해당 관계/대상으로 이동 가능해야 함.
- frontmatter는 본문 상단에 노출하지 않아야 함.
- 왼쪽 list의 카드 UX는 불필요.
- Wiki 목차 페이지처럼 디자인하고, 본문 상단에는 파일 위치를 제공하는 구조가 적절함.

### 3. Mapping 페이지 UX 재설계

- 상단 가이드 문구는 불필요.
- 신규 항목 카드는 작게 floating list 형태로 표시.
- 항목 클릭 시 확장되어 다음 내용을 보여야 함:
  - LLM이 반영한 평가 내용
  - 어떤 신규 값인지
  - 기존 wiki에 merge/create 판단에 필요한 정보

### 4. Workflows / Tasks 미구현

- 단순 inbox 목록보다 실제 CLI/LLM 작업을 컨트롤하는 화면이 필요함.
- `vault/00_Inbox`는 source input queue로 다루되, 페이지명/주요 UX는 Workflows/Tasks 방향이 적절함.
- 해당 source queue를 trigger하고 `scan/ingest/normalize/extract/map/sync` 같은 CLI 작업으로 이어지는 구성이 구현되지 않음.

### 5. Vault folder viewer 미구현

- 전체 vault 폴더 목록과 내용을 읽어보는 viewer가 보이지 않음.

### 6. Settings route save 의미 불명확

- Save route 기능의 의미가 명확하지 않음.
- 작업별 모델 분할 기능으로 보이나, 현재 모델 설정 자체가 불가능하거나 충분히 명확하지 않음.

### 7. Prompt 상태 불명확

- 프롬프트가 schema에 맞게 기본 프롬프트로 반영된 것인지,
  아니면 test set인지 UI에서 명확하게 확인이 필요함.

## Planning 해석

이번 피드백은 단순 버그 수정이 아니라 Phase 3 Web UI 정보구조와 주요 화면 흐름을 재설계해야 하는 변경요청이다.

권장 처리:

1. Phase 3를 `changes_requested`로 유지한다.
2. Onboarding, Wiki, Mapping, Workflows/Tasks, Vault viewer, Settings/Prompt를 하나의 큰 fix로 묶지 말고 독립 하위 작업으로 분리한다.
3. UI/UX mockup을 먼저 갱신한 뒤 구현한다.
4. API key 입력/저장 정책은 보안 요구와 충돌 가능성이 있으므로 사용자 확인 후 확정한다.

## 제안 작업 분해

### UI-FIX-01 — Onboarding wizard 재설계

- Provider dropdown: Ollama / LM Studio / OpenAI-compatible custom
- Provider별 endpoint 기본값 제안
- API key 처리 정책 확정
- Connection test API
- 모델 목록 조회 API
- Vault 신규/기존 선택
- File browser 또는 path picker UX
- 기존 vault mapping wizard

### UI-FIX-02 — Wiki viewer 재설계

- Markdown renderer 적용
- frontmatter hide/metadata panel 분리
- Wiki 목차형 left navigation
- 본문 상단 file path 표시
- 1-hop graph panel/dropdown
- relation click navigation

### UI-FIX-03 — Mapping review UX 재설계

- 상단 가이드 제거
- 신규 후보 floating compact list
- 클릭 시 expandable detail panel
- LLM 평가/신규값/근거/merge target 명확화

### UI-FIX-04 — Workflows / Tasks 구현

- CLI 작업 컨트롤 화면
- Source input queue: `vault/00_Inbox/memo`, `files`, `text`
- 작업 trigger 정의: `inbox scan`, `ingest`, `ingest-text`, `normalize`, `extract`, `map`, `compile`, `sync`
- Source input → CLI/LLM task → raw source/review 흐름 연결

### UI-FIX-05 — Vault folder viewer 구현

- Vault tree browser
- 파일 내용 viewer
- 지원 파일 타입 및 읽기 제한 정의

### UI-FIX-06 — Settings LLM/model/route 설명 재정의

- Model registry 설정 가능 상태로 개선
- Route save 의미: task별 사용할 model 선택으로 명확화
- route UI는 model 설정이 완료된 뒤 활성화

### UI-FIX-07 — Prompt status 명확화

- schema default prompt / confirmed prompt / test prompt 구분
- 현재 적용 중인 prompt 표시
- schema compatibility 표시

## 구현 전 확인 필요

1. API key를 Web UI에서 직접 입력하도록 허용할지?
   - 기존 정책: API key 값은 저장/노출하지 않고 env var 이름만 저장.
   - 새 피드백: endpoint 다음 API key 입력 흐름 요청.
   - **사용자 확정(2026-07-19): API key는 화면에 보이지 않게 바로 저장한다.**
2. File browser 범위:
   - workspace 내부만 허용할지
   - OS 전체 경로 browsing을 허용할지
   - **사용자 확정(2026-07-19): 전체 경로 browsing을 허용한다.**
3. Inbox의 의미:
   - raw source inbox인지
   - imported-but-not-processed source queue인지
   - review candidate inbox인지
   - **사용자 확정(2026-07-19): `inbox > LLM 처리 > raw source` 구조이다. 기존 폴더구조 문서 확인 필요.**
4. Markdown renderer 방식:
   - backend render 후 sanitize
   - frontend lightweight renderer
   - raw HTML 허용 여부

## 확인된 기존 폴더구조 계약

- 문서: `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
- 기본 구조:

```text
vault/
  00_Inbox/
    memo/
    files/
    text/
  10_Wiki/
    concepts/
    sources/
    claims/
    pages/
  20_Review/
    candidates/
    mapping/
    rejected/
  80_Raws/
  90_Settings/
    templates/
    prompts/
    ontology/

data/
  wiki.sqlite
  raw/
  normalized/
  artifacts/
  exports/
  cache/
```

## 확정 반영 후 UX/API 전제

### API key 저장 정책

- Onboarding에서 API key 값을 입력받는다.
- 입력 직후 저장하고 화면에는 다시 표시하지 않는다.
- 재조회 시에는 `configured / missing` 상태만 표시한다.
- 보안상 최소 원칙:
  - API 응답에 API key 값을 포함하지 않는다.
  - DOM에 저장된 key value를 남기지 않는다.
  - 가능하면 `.env` 또는 별도 local secret store에 저장하고 settings에는 env var/reference만 둔다.

### File browser 정책

- Vault 신규/기존 선택 시 OS 전체 경로 선택을 허용한다.
- 서버는 path traversal, 권한 오류, 홈 디렉터리/마운트 접근 실패를 명확히 처리해야 한다.
- 기존 vault 선택 시 현재 `vault/00_Inbox`, `10_Wiki`, `20_Review`, `80_Raws`, `90_Settings` 구조와의 mapping step을 제공한다.

### Inbox 구조

- UI 구조는 `Inbox → LLM 처리 → Raw Source` 흐름을 기준으로 한다.
- `vault/00_Inbox/{memo,files,text}`를 사용자가 넣는 입력 영역으로 보여준다.
- LLM 처리 후 결과/원본은 시스템 관리 영역인 `data/raw/`, `data/normalized/`, `data/artifacts/` 및 사람이 보는 `vault/80_Raws/` index와 연결한다.
- Review candidate inbox(`vault/20_Review/candidates`)와 source inbox(`vault/00_Inbox`)는 UI에서 분리해서 표현한다.

## Build handoff note

이 문서를 기준으로 기존 Phase 3 fix는 추가 변경요청이 발생한 상태이며, Tailnet 승인 전 Build/Check 완료로 간주하지 않는다.
