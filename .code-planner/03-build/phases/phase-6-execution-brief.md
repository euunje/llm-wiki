# Phase 6 Execution Brief

## Source planning docs

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/03-build/evidence/phase-5B-build-evidence.md`
- `.code-planner/04-check/phase-5B-check-report.md`

## Phase goal

Document and validate a safe end-to-end test path for the Inbox-first ingest flow without adding a product reset command:

```text
test setup / optional one-time vault cleanup
-> Raw Sources import into Inbox
-> Files / Markdown / pasted text / large document / failure / review / archive checks
-> evidence capture
```

## Work units

### WU-6-001. Existing documentation and E2E test surface discovery

- Purpose: Find current docs, CLI/web commands, tests, fixtures, and safe validation patterns for the Phase 6 guide.
- Assigned agent: `codebase-explorer`
- Expected files: read-only discovery across docs, README, tests, CLI/web routes, config/scaffold.
- Completion criteria: existing reset/test guidance, E2E coverage gaps, and safe command candidates identified.
- Verification: discovery report only.

### WU-6-002. Test reset guide and E2E validation checklist

- Purpose: Write user-facing documentation for one-time qmd/Obsidian reset as test setup only, Raw Sources -> Inbox preparation, and E2E matrix.
- Assigned agent: `build-test-validation`
- Expected files:
  - `.code-planner/03-build/evidence/phase-6-test-reset-guide.md`
  - `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
- Completion criteria:
  - Explicitly warns about destructive data deletion / backup.
  - Does not introduce a product reset command.
  - Covers document file, markdown scrape, pasted text, large document, failed route, review route, archive move, existing Raw Sources import.
  - Defines evidence capture locations.
- Verification: document review and consistency check against planning docs.

### WU-6-003. Automated non-destructive validation pass

- Purpose: Run non-destructive automated validation that supports the Phase 6 guide without touching a real user vault.
- Assigned agent: `build-test-validation`
- Expected files: `.code-planner/03-build/evidence/phase-6-build-evidence.md`
- Completion criteria:
  - Records scoped test commands and outputs.
  - Confirms current Phase 5B stacked code remains green.
  - Separates automated validation from manual real-vault E2E evidence.
- Verification: pytest, py_compile, `git diff --check`, git status/diff stat.

## Out of scope

- Implementing a repeatable or operational reset command.
- Running destructive cleanup against a real user vault without explicit step-by-step user confirmation.
- Real provider LLM calls unless the user explicitly provides environment/approval.
- Changing Phase 1~5 product behavior except documentation/test evidence.

## Validation commands

- `.venv/bin/python -m pytest tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_inbox_domain.py tests/test_inbox_registration.py tests/test_phase4_review_failed_workbench.py tests/test_cli_inbox.py -v`
- `.venv/bin/python -m py_compile src/llm_wiki/cli.py src/llm_wiki/jobs.py src/llm_wiki/webapp/routes/ingest.py src/llm_wiki/inbox.py tests/test_web_navigation.py tests/test_inbox_to_job_mapping.py tests/test_cli_inbox.py`
- `git diff --check`

## Git checkpoint plan

- Intended checkpoint after final `/check phase-6`: `test: document inbox flow validation`
- User has instructed not to commit until the current full work is complete.

## Risks

- Phase 5B is currently source-validated but uncommitted; Phase 6 is intentionally stacked on top until final completion.
- Any real-vault reset/move procedure is potentially destructive; documentation must require backup and explicit user choice.
- Automated tests use temp vaults and do not prove real-provider LLM quality; manual E2E remains a separate checklist item.
