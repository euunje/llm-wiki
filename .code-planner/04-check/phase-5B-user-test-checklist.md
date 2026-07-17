# Phase 5B 사용자 기능 테스트 체크리스트 (초안)

- Phase: phase-5B — CLI/Web UI integration for Inbox-first flow
- 작성일: 2026-07-16
- Branch: feature/upgrade-plan-implementation
- HEAD: 29e4808 (Phase 5A) 위에 Phase 5B 변경이 stacked 상태
- 모킹: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html`
- 기대되는 자동 검증: `41 passed` (web navigation 9 + inbox-to-job 5 + inbox domain 4 + inbox registration 16 + phase4 workbench 4 + cli inbox 3)

이 체크리스트는 **사용자 화면/명령행에서 실제로 확인해야 하는 항목**입니다. 자동화 테스트로 검증되지 않는 시각적·상호작용 항목 위주입니다.

## 사전 준비

1. 서버 실행:
   - `uvicorn src.llm_wiki.webapp.main:app` 또는 기존 dev 환경
2. 비교용 mockup 열기:
   - `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html`
3. 테스트 vault에 다음이 섞여 있도록 준비:
   - `Inbox/Files/`, `Inbox/Markdown/`, `Inbox/Text/` 각 입력 유형별 1건 이상
   - Pending/Processing/Failed/Review 각 상태 1건 이상 (가능하면)
   - Raw Sources 폴더에 미처리 문서 1건

## Screen: `/ingest`

### 헤더 / 빈 상태
- [ ] 페이지 진입 시 제목 `수집`, 부제 `새 입력을 Inbox에 등록하고 처리 대기열로 보냅니다.`
- [ ] Inbox가 비어 있으면 `Inbox 대기 항목이 없습니다.` 표시
- [ ] 빈 상태의 CTA가 `Raw Sources에서 Inbox로 가져오기` (이전 `Raw Sources 스캔` 아님)

### 입력 등록
- [ ] PDF/DOCX 업로드 → Inbox 대기열에 `document_file` badge + `pending` 상태, relpath 보임
- [ ] Markdown 업로드 → `markdown_file` badge, `pending`
- [ ] 붙여넣기 텍스트 → `pasted_text` badge, `pending`
- [ ] Raw Sources 폴더에 있는 파일을 `Raw Sources에서 Inbox로 가져오기`로 import → 새 Inbox items 등록 (legacy `sources` queue에 직접 들어가지 않음)

### 큐 액션
- [ ] 체크박스 선택 시 카운트 표시 (예: `1개 선택`)
- [ ] `선택 처리 시작` 버튼이 선택 시 활성
- [ ] `전체 처리` 버튼이 활성이고 pending 있을 때 동작
- [ ] per-item `처리 시작` 버튼이 `inbox_item_id`로 `/ingest/start` 호출

## Screen: `/jobs`

- [ ] 새 작업 카드에 `Inbox #<id>` 표시
- [ ] chunk extraction 진행률 `phase · NN%` 형태 표시
- [ ] Job의 relpath가 Inbox path를 보여주거나 fallback `소스 #<id>` 보임
- [ ] Inbox 연결 없는 legacy job 카드는 정상 렌더 유지

## CLI

- [ ] `wiki add <file>` → Inbox 등록, hint에 `wiki ingest` 안내
- [ ] `wiki status` → Pending/Processing/Review/Failed 카운트 표시
- [ ] Review 항목 존재 시 hint에 `/inbox?state=review` 노출
- [ ] `wiki ingest` (no-arg) → pending Inbox items를 materialize해서 처리
- [ ] `wiki ingest <source_id>` → 기존 legacy source_id 경로도 동작
- [ ] (Failed Inbox item이 있을 때) `wiki retry <inbox_item_id>` → Failed → Pending 이동, 진단 sidecar 처리

## Regression

- [ ] `/inbox` Review/Failed 탭 + 액션 (Phase 4) 정상 동작
- [ ] `/jobs` 기존 동작 유지
- [ ] `/api/reprocess/<source_id>` 정상 동작

## 결정 입력 사항 (blocking)

1. **빈 상태 카피 정확성**
   - 실제 표시되는 한국어 문구가 mockup/승인 카피와 정확히 일치하는지 확인.
   - 위양이면 fix 필요 (build agent: `build-ui-dev`).

2. **입력 유형 + 상태 badge 레이아웃**
   - 현재: per-row에 input_type pill과 status pill 2개.
   - 옵션: input_type을 relpath 아래 sub-label로 강등.
   - 위양이면 fix 필요 (build agent: `build-ui-dev`).

3. **`/ingest/start` 후 JS 흐름**
   - 체크박스 선택 후 모든 항목이 실제로 job으로 들어가는지 콘솔/네트워크 탭 확인.

체크리스트 결과를 다음 중 하나로 답변해주세요:

- **모두 통과** → `/check phase-5B` `approved_with_notes`로 종료하고 커밋 진행
- **일부 항목 실패** → 실패 항목을 fix request로 변환하여 `/fix phase-5B`로 전환
- **사용자 테스트 추후 일괄 진행 합의** → 체크리스트를 `phase-5B-user-test-checklist.md`로 보존, 커밋 진행, 검사는 Phase 6에서 일괄 수행
