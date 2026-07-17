# Stage 7 — Planning Crosscheck

## Run 1

- Agent: `planning-crosscheck`
- Result: `issues_found`

## Issues found

1. Phase 4/5 문서에 HTML mockup이 `(to create)`로 남아 있으나 실제 HTML은 생성/PRV 승인됨.
2. Review routing conditions가 draft phase map, phase doc, feature contract 사이에 불일치.
3. `Inbox/_Processing`이 실제 폴더인지 DB 상태인지 모호.
4. Phase 5 mockup의 입력 하위 폴더와 chunk progress 표시가 spec/validation에 반영되지 않음.
5. validation plan의 Review routing/move failure/E2E criteria가 세분화 필요.

## Regression decisions

- Review routing source of truth: `feature-review-failed-workbench.md`를 master로 한다.
- `Inbox/_Processing`: 실제 폴더가 아니라 DB `processing` 상태와 lock으로 정의한다.
- 입력 하위 폴더: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`를 권장 convention으로 채택한다. `Inbox/Articles` 같은 세부 category는 metadata/category로 다룬다.
- Jobs chunk progress: Build scope에 포함한다. chunked extraction phase progress를 jobs/event stream에 노출한다.
- HTML mockup은 생성/PRV 승인 완료 상태로 정정한다.

## Status

- Run 1 이슈는 Stage 5 regression으로 반영 완료.

## Run 2

- Agent: `planning-crosscheck`
- Result: `issues_found` initially, minor residual issues only.

### Run 2 resolved confirmations

- HTML mockup stale annotation resolved.
- Review routing conditions aligned.
- `Inbox/_Processing` clarified as DB state/lock, not folder.
- Input subfolder convention aligned to `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- Jobs chunk progress included in phase scope, mockup spec, and validation.
- Validation plan expanded for move failure evidence, Review routing, and E2E success criteria.

### Run 2 residual issues and resolution

1. `phase-5-existing-ux-ingest.html` still showed `Inbox/Articles/rag-temperature.md`.
   - Resolution: changed to `Inbox/Files/rag-temperature.md`.
2. CLI `retry/review` scope remained ambiguous.
   - Resolution: `wiki retry <inbox_item_id>` is minimal required CLI support; Review detailed actions are Web UI first, CLI only needs status/count/link hint.
3. Pasted text tags storage was ambiguous.
   - Resolution: tags/source_url are stored in generated `.md` frontmatter.

## Final crosscheck status

- Result after regression: `passed_with_documented_defaults`.
- No Build-blocking conflicts remain.

## Run 3 — Build-gate compatibility document check

- Agent: `planning-crosscheck`
- Result: `passed`

### Checked additions

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/mockups/README.md`
- `.code-planner/02-planning/mockups/phase-2-review-workspace.html`
- `.code-planner/02-planning/review/phase-2-lavish-approval-2026-07-10.md`

### Result

- 신규 conflict 없음.
- Compatibility files are summaries/indexes only and do not alter approved scope.
- `phase-2-review-workspace.html` is explicitly a Build-gate compatibility mockup and does not replace approved Phase 4/5 mockups.
- `phase-2-lavish-approval-2026-07-10.md` explicitly points to actual PRV approvals and clarifies the legacy filename date.
- `validation/01-validation-plan.md` now includes the `non_categories` compatibility check.

## Run 4 — Raw Sources / Inbox realignment check

- Agent: `planning-crosscheck`
- Result: `passed`

### Checked additions

- User-confirmed flow: `업로드/Raw Sources에서 가져오기 -> Inbox pending -> LLM 확인/처리 -> Wiki 문서화 완료 -> Raw Sources archive`.
- Phase 5 split into:
  - Phase 5A: Inbox-to-Job dispatch mapping.
  - Phase 5B: CLI/Web UI integration.
- ADR-007 accepted: materialize/link `inbox_item_id -> source_id -> ingest_job` at processing start while reusing existing job/LLM pipeline.
- Raw Sources wording changed from normal scan queue to import/migration source material.
- Validation now blocks UX/user testing until Phase 5A passes.

### Result

- No Build-blocking conflict remains.
- Minor UI note recorded: `pasted_text` / `imported` should be treated as input_type/source labels, not canonical status badges.
