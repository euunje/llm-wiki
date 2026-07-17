# Build Handoff — Inbox-first ingest flow

## Status

- Planning stage: complete. User approved Build transition via PRV.
- Raw Sources → Inbox realignment approved via PRV session `20260716T072651Z-01bdca`.
- Ideation input: `.code-planner/01-ideation-approved.json`
- Technical decisions: accepted.
- Phase docs: fixed.
- Mockups: HTML artifacts created and PRV-confirmed.
- Validation plan: ready.
- Crosscheck: passed with documented defaults; no Build-blocking conflicts remain.

## Goal

Change `llm-wiki` ingest from `Raw Sources -> ingest -> Wiki` to:

```text
Inbox -> ingest/process -> Wiki + Raw Sources archive
```

User-facing expanded flow:

```text
업로드/Raw Sources에서 가져오기
-> Inbox pending
-> LLM 확인/처리
-> Wiki 문서화 완료
-> 원본 파일 Raw Sources archive 이동
```

## Non-negotiable scope

- Inbox is the user input point.
- Raw Sources is success archive only.
- Existing Raw Sources documents are import/migration source material only; they must be registered into Inbox before processing.
- Failed originals move to `Inbox/_Failed` with diagnostic report.
- Review candidates move to `Inbox/_Review` and are handled in a workbench.
- Large documents use `ParsedDocument.chunks` based chunked extraction map-reduce.
- Do not physically split raw source files by chunk.
- Do not implement qmd/Obsidian reset as a product feature.
- Preserve existing UX style; no new design system.

## Key defaults resolved during Planning

- `processing` is DB state/lock, not an `Inbox/_Processing` folder.
- Recommended input subfolders: `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text`.
- `Inbox/Articles` and similar labels are metadata/category, not required folders.
- Pasted text tags/source_url are stored in generated `.md` frontmatter.
- CLI required scope: `wiki add`, `wiki ingest`, `wiki status`, `wiki retry <inbox_item_id>`.
- Review detailed actions are Web UI first; CLI only needs status/count/link hint.
- Jobs must expose chunk extraction phase/progress.

## Build phases

1. Phase 1 — Inbox domain model and path/state foundation
   - Doc: `.code-planner/02-planning/phases/phase-1-inbox-domain.md`
   - Commit: `feat: add inbox domain model`
2. Phase 2 — Inbox registration and file movement
   - Doc: `.code-planner/02-planning/phases/phase-2-inbox-registration-movement.md`
   - Commit: `feat: route inputs through inbox`
3. Phase 3 — Chunked extraction map-reduce
   - Doc: `.code-planner/02-planning/phases/phase-3-chunked-extraction.md`
   - Commit: `feat: add chunked extraction pipeline`
4. Phase 4 — Review/Failed workbench behavior
   - Doc: `.code-planner/02-planning/phases/phase-4-review-failed-workbench.md`
   - Commit: `feat: add inbox review workbench`
5. Phase 5A — Inbox-to-Job dispatch mapping
   - Doc: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
   - Commit: `feat: connect inbox items to ingest jobs`
6. Phase 5B — CLI/Web UI integration
   - Doc: `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
   - Commit: `feat: integrate inbox flow in ui and cli`
7. Phase 6 — Test reset guide and end-to-end validation
   - Doc: `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
   - Commit: `test: document reset and e2e validation`

## Planning documents

- Overview: `.code-planner/02-planning/README.md`
- ADRs: `.code-planner/02-planning/decisions/ADRs.md`
- Dependencies: `.code-planner/02-planning/decisions/dependencies.md`
- Git plan: `.code-planner/02-planning/git/git-plan.md`
- Draft phase map: `.code-planner/02-planning/phases/draft-phase-map.md`
- Feature contracts: `.code-planner/02-planning/features/feature-*.md`
- Validation plan: `.code-planner/02-planning/validation/validation-plan.md`
- Crosscheck: `.code-planner/02-planning/validation/planning-crosscheck.md`

## Approved UI/UX artifacts

- Phase 4 Markdown mockup: `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.md`
- Phase 4 HTML mockup: `.code-planner/02-planning/mockups/phase-4-existing-ux-review-failed.html`
- Phase 5 Markdown mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.md`
- Phase 5 HTML mockup: `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html`
- PRV feedback: `.code-planner/02-planning/review/phase-4-5-prv-feedback.md`

## Source areas likely affected

- `src/llm_wiki/config.py`
- `src/llm_wiki/db.py`
- `src/llm_wiki/ingest_raw.py`
- `src/llm_wiki/ingest_llm.py`
- `src/llm_wiki/jobs.py`
- `src/llm_wiki/webapp/routes/ingest.py`
- `src/llm_wiki/webapp/routes/inbox.py`
- `src/llm_wiki/webapp/templates/ingest.html`
- `src/llm_wiki/webapp/templates/inbox.html`
- `src/llm_wiki/webapp/templates/jobs.html`
- `src/llm_wiki/cli.py`
- tests

## Validation expectations

- Follow `.code-planner/02-planning/validation/validation-plan.md` phase by phase.
- Save Build evidence under `.code-planner/03-build/evidence/phase-*`.
- Phase result values: `pass`, `fail`, `blocked`.
- UI phases must compare implementation against PRV-confirmed HTML mockups.
- E2E success requires both Wiki page creation/update and Raw Sources archive movement.
- UI/UX testing must not begin from synthetic seeded Review/Failed items alone. First prove the real flow: Raw Sources import/upload -> Inbox pending -> job/LLM -> Wiki/Review/Failed/archive.
- Phase 5A must pass before `/ingest` UX/user testing begins.

## Git warnings

- Current worktree may already contain earlier 2-pass generation source changes.
- Before Build commits, inspect `git status` and diff.
- Stage only intended files per phase.

## Build entry checklist

- [x] User approves this Build handoff. PRV session: `20260715T121805Z-371ffe`.
- [ ] Builder reads all phase docs and validation plan.
- [ ] Builder confirms no source-code implementation starts from conversation memory only.
- [ ] Builder separates pre-existing source changes from new Inbox-first work.
