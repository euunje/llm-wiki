# Phase 3 User UI Test Revision Plan — Onboarding/Wiki/Review/Settings

## 목적

Tailnet UI 검증에서 나온 사용자 피드백을 기준으로 Phase 3의 남은 문제를 재분류하고, 다음 `/fix phase-3`에서 구현할 수정 범위를 명확히 한다.

이 문서는 기존 fix request와 gap plan을 보강한다.

- Fix request: `.code-planner/04-check/fix-requests/phase-3-fix-request.md`
- Gap plan: `.code-planner/04-check/fix-requests/phase-3-web-ui-gap-review-and-fix-plan.md`
- A/B 구조 결정: `.code-planner/04-check/fix-requests/phase-3-web-ui-ab-wireframes.md`

## 사용자 UI 검증 결과

1. Onboarding 설정 과정을 실제로 테스트할 수 없다.
2. Wiki sample data는 실제 Wiki 화면에서 눌렀을 때 내용이 보이지 않는다.
3. Review / Mapping 페이지의 구성상 의미가 명확하지 않다. 기존 concept 문서와 후보의 관계를 재검토해야 한다.
4. Settings page에 LLM 주소, API key env, model 설정 기능이 없다.
5. Settings Vault 설정에서 경로 재설정을 위한 기능이 없다.
6. Mapping 시 기존 wiki 개념과 merge하는 부분이 명확하지 않다.

## 문제 분류

| 피드백 | 분류 | 원인 |
|---|---|---|
| Onboarding 설정 과정 테스트 불가 | 미구현 | Onboarding이 상태 표시 중심이고 설정 wizard/저장 동작이 없음 |
| Wiki sample click 시 내용 없음 | 기능/데이터 연결 버그 | master-detail 선택, route, JS/API detail 연결 중 하나가 실제 화면에서 실패 |
| Review/Mapping 의미 불명확 | IA/UX 실패 | 후보 → 기존 wiki → decision의 판단 흐름이 화면에 명확히 표현되지 않음 |
| Settings LLM/API/model 설정 기능 없음 | 미구현 | Settings LLM 탭이 상태 표시/route 일부에 머물고 실제 설정 입력/저장이 부족 |
| Vault 경로 재설정 기능 없음 | 결정 변경/미구현 | 이전 결정은 Vault를 Onboarding에서 변경하기로 했으나 Onboarding에 해당 step이 없음 |
| 기존 wiki와 merge 불명확 | UX/기능 부족 | mapping 후보와 existing concept 비교/확정 UI가 부족 |

## 수정 목표 v2

### 1. Onboarding은 “상태표시”가 아니라 “설정 wizard”여야 한다

Onboarding은 최초 접속 시 다음 설정을 실제로 진행할 수 있어야 한다.

필수 step:

1. Web Auth 상태 확인
   - `.env` admin password configured 여부만 표시.
   - 값은 표시하지 않는다.
2. Vault/Data 경로 설정
   - 현재 vault/data 경로 표시.
   - 사용자가 workspace 내부의 vault/data 경로를 입력/변경 가능.
   - 설정 저장 후 settings.yaml에 반영.
   - 경로 생성/검증은 safe action으로 제공.
3. LLM 설정
   - endpoint URL 입력.
   - API key env name 입력. 실제 key 값은 저장/표시하지 않는다.
   - chat model / embedding model 입력.
   - route 기본값 확인.
4. 완료 후 Dashboard/Wiki/Review로 이동할 next action.

비범위:

- 실제 secret 값을 Web에 입력/저장하는 기능.
- destructive Vault migration.

### 2. Wiki 화면은 click → detail이 반드시 보여야 한다

필수 기능:

- `/wiki` 좌측 목록에서 RAG/Vector/LLM Agent sample을 클릭하면 우측 detail이 즉시 표시된다.
- detail에는 최소 다음이 보여야 한다.
  - title
  - path
  - aliases
  - meaning/summary
  - claims
  - relations
  - raw markdown preview
- JS 실패 시에도 server-side fallback 또는 detail route 링크(`/wiki/{id}`)로 내용을 볼 수 있어야 한다.

Acceptance:

- Tailnet에서 사용자가 sample wiki를 클릭했을 때 빈 화면이 아니어야 한다.

### 3. Review / Mapping 화면은 판단 흐름을 명확히 해야 한다

현재 3-column은 유지하되, 각 column의 의미를 더 명확히 한다.

```text
왼쪽: 기존 Wiki 후보
  - 이 후보가 병합될 수 있는 기존 wiki concept 목록
  - similarity / mapping reason / existing title 표시

가운데: 비교 패널
  - 선택한 기존 Wiki concept 상세
  - 오른쪽 후보와 비교되는 필드 강조
  - aliases / claims / relations / markdown preview

오른쪽: 신규/Mapping 후보
  - LLM이 제안한 신규 concept 또는 mapping 후보
  - candidate payload / evidence / confidence
  - merge / create_new / edit / reject+retry
```

필수 UX:

- 후보 카드를 선택하면 왼쪽이 해당 후보 기준 유사도 목록으로 갱신된다.
- 기존 wiki를 선택하면 가운데 비교 패널이 채워진다.
- merge 버튼에는 “선택한 기존 wiki와 병합”이라는 대상이 명확히 표시되어야 한다.
- merge 전 confirmation에 다음이 포함되어야 한다.
  - source candidate title/key
  - target existing wiki title/id
  - decision type: merge
- create_new은 기존 wiki 선택 없이도 가능하지만, 신규 wiki 생성 후보임을 명확히 표시한다.

### 4. Settings LLM 탭은 실제 설정 입력/저장을 제공해야 한다

필수 필드:

- endpoint URL
- API key env name
- default chat model
- default embedding model
- task route mapping:
  - extract_claims
  - summarize
  - link
  - map
  - compile
  - ask

필수 동작:

- 저장 버튼은 settings.yaml에 반영한다.
- API key 값은 입력받지 않고 env var name만 입력한다.
- 저장 후 configured/missing 상태를 다시 계산해 보여준다.
- model test는 실제 호출이 아니라 read-only 안내 또는 CLI command 안내로 둬도 된다.

### 5. Settings Vault 탭과 Onboarding Vault step의 역할 분리

사용자 피드백에 따라 Vault 경로 재설정 기능이 필요하다. 최종 역할은 다음처럼 둔다.

- Onboarding: 실제 Vault/Data 경로 설정 wizard.
- Settings > Vault: 현재 경로 표시 + “Onboarding에서 변경” CTA + read-only status.

즉, Settings Vault 탭 자체에서 직접 변경하지 않더라도, 경로 재설정 흐름으로 바로 이동할 수 있어야 한다.

### 6. Evidence/테스트 보강

자동 테스트만으로는 충분하지 않다. 다음 manual test evidence가 필요하다.

PC/Tailnet 체크:

- Onboarding에서 LLM endpoint/model/env name을 입력하고 저장한다.
- Onboarding에서 Vault/Data 경로를 테스트 경로로 설정하고 저장한다.
- Wiki에서 sample 3개를 클릭해 모두 detail이 나온다.
- Review/Mapping에서 후보 선택 → 기존 wiki 선택 → merge confirmation 대상이 명확히 보인다.
- Settings LLM 탭에서 endpoint/model/route 변경 후 저장된다.
- Settings Vault 탭에서 Onboarding 변경 CTA가 동작한다.

## 다음 `/fix phase-3` 작업 단위

### build-core-dev

- Onboarding settings save APIs:
  - `POST /api/setup/llm`
  - `POST /api/setup/vault`
  - optional `POST /api/settings/llm/config`
- Wiki detail API/route fallback 점검.
- Review decision payload에 target existing wiki를 명확히 포함.

### build-ui-dev

- Onboarding wizard UI.
- Wiki master-detail click 동작 수리 및 server-side fallback 링크.
- Review/Mapping 비교 패널/merge confirmation 재설계.
- Settings LLM config form.
- Settings Vault → Onboarding CTA.

### build-test-validation

- API 저장 테스트.
- Wiki click/detail TestClient 또는 JS-equivalent 테스트.
- Review merge target confirmation 테스트.
- Tailnet manual checklist evidence 업데이트.

## Check decision

현재 Phase 3는 여전히 **changes_requested**다.

이 문서의 항목들이 해결되고 사용자 Tailnet 확인이 끝나기 전에는 commit하지 않는다.
