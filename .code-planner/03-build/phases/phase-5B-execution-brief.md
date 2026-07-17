# Phase 5B Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-5-ui-cli-integration.md`
- `.code-planner/02-planning/features/feature-ui-cli-integration.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.md`
- `.code-planner/02-planning/mockups/phase-5-existing-ux-ingest.html`
- `.code-planner/03-build/evidence/phase-5A-build-evidence.md`
- `.code-planner/04-check/phase-5A-check-report.md`

## Phase goal

Make the approved Inbox-first flow visible and operable from the existing Web UI and CLI without introducing a new design system:

```text
Files/Markdown/Text or Raw Sources import
-> Inbox pending queue
-> process by inbox_item_id
-> existing source/job/LLM pipeline
-> jobs progress / review / failed / archive visibility
```

## Work units

### WU-5B-001. Existing UI/CLI/job-flow discovery

- Purpose: Map current `/ingest`, `/jobs`, CLI commands, job list/event payloads, and tests before implementation.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery for `routes/ingest.py`, `templates/ingest.html`, `jobs.py`, `cli.py`, tests under `tests/`.
- Completion criteria: insertion points, duplicate risks, and affected tests identified.
- Verification: discovery report only.

### WU-5B-002. `/ingest` Inbox pending queue alignment

- Purpose: Update existing `/ingest` route/template/JS to display Inbox pending items as the primary queue and start processing via `inbox_item_id`.
- Assigned agent: `build-ui-dev`
- Expected files: `src/llm_wiki/webapp/routes/ingest.py`, `src/llm_wiki/webapp/templates/ingest.html`, relevant web tests.
- Completion criteria:
  - Upload/paste/Raw Sources import is expressed as Inbox registration.
  - Queue displays `inbox_items.state = pending`, with input_type/source labels separate from status.
  - Per-item, selected, and all-pending start actions post `inbox_item_id`.
  - Raw Sources action copy says “Raw Sources에서 Inbox로 가져오기”.
- Verification: `/ingest` route/template tests and Phase 5A mapping tests remain green.

### WU-5B-003. `/jobs` inbox metadata and chunk progress display

- Purpose: Surface inbox item metadata and chunk/progress phase in jobs list/API/live stream without changing the worker contract unnecessarily.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/jobs.py`, `src/llm_wiki/webapp/routes/ingest.py`, `src/llm_wiki/webapp/templates/jobs.html`, tests.
- Completion criteria:
  - Job list/API can display `inbox_item_id` when available.
  - Existing `phase`/`progress` chunk extraction data is visible in job cards/API.
  - No new background process or external dependency.
- Verification: jobs/web navigation tests plus targeted job metadata tests.

### WU-5B-004. CLI Inbox-first semantics

- Purpose: Update CLI commands so add/ingest/status/retry share the Inbox-first state model.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli.py`, relevant CLI tests.
- Completion criteria:
  - `wiki add` remains/adds Inbox registration semantics.
  - `wiki ingest` processes pending Inbox items via the Phase 5A materialization path.
  - `wiki status` includes Inbox/Review/Failed counts and Web hint.
  - `wiki retry <inbox_item_id>` minimally moves Failed/Review item back to pending.
- Verification: CLI tests using temp vault/state DB.

### WU-5B-005. Validation, evidence, and mockup alignment

- Purpose: Run scoped validation, compare against the approved Ingest mockup, and write Phase 5B evidence.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-5B-build-evidence.md` plus tests if needed.
- Completion criteria:
  - Phase 5B validation-plan items covered by real command output.
  - Phase 5A/4 regressions remain green.
  - Mockup alignment notes recorded.
- Verification: pytest, py_compile, `git diff --check`, git status/diff-stat evidence.

## Out of scope

- New design system or completely new `/ingest` layout.
- Product reset command for qmd/Obsidian.
- Full real-provider LLM E2E matrix (Phase 6).
- Review merge/classification deep CLI UI beyond status/count/link hint.
- Exposing Tailnet/local ports beyond existing local app behavior.

## Validation commands

- `.venv/bin/python -m pytest tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py -v`
- `.venv/bin/python -m pytest tests/test_inbox_domain.py tests/test_inbox_registration.py tests/test_phase4_review_failed_workbench.py -v`
- CLI-focused pytest files discovered/added during WU-5B-004.
- Jobs-focused pytest files discovered/added during WU-5B-003.
- `.venv/bin/python -m py_compile src/llm_wiki/cli.py src/llm_wiki/jobs.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/inbox.py`
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after `/check phase-5B`: `feat: integrate inbox flow in ui and cli`
- Stage only Phase 5B source/test files and required evidence/check artifacts when explicitly requested.

## Risks

- `/ingest` template currently still renders legacy `sources.status = pending` rows; Phase 5B must move primary queue rendering to Inbox pending items.
- CLI command names may have existing user expectations; preserve backward-compatible behavior where practical.
- Jobs currently key on `source_id`; inbox metadata should be joined/adapted without breaking existing jobs.
- User-visible UX testing becomes relevant after this phase because Phase 5A has passed.
