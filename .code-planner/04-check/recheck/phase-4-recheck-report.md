# Phase 4 Recheck Report

- Phase: 4 — Review/Failed workbench behavior
- Recheck date: 2026-07-16
- Result: `changes_requested`
- Commit: not committed

## Recheck inputs

- Original check report: `.code-planner/04-check/phase-4-check-report.md`
- Fix request: `.code-planner/04-check/fix-requests/phase-4-fix-request.md`
- Expected fix evidence: `.code-planner/03-build/evidence/phase-4-fix-evidence.md`

## Fix evidence status

- Missing: `.code-planner/03-build/evidence/phase-4-fix-evidence.md`
- Current worktree contains partial fix changes, but no Build/Fix evidence was
  produced. This is not acceptable for approval.

## Actual git changes at recheck

```text
M src/llm_wiki/inbox.py
M src/llm_wiki/webapp/routes/inbox.py
M src/llm_wiki/webapp/templates/inbox.html
M tests/test_inbox_registration.py
?? tests/test_phase4_review_failed_workbench.py
?? .code-planner/
?? .prv/
```

Tracked diff stat:

```text
src/llm_wiki/inbox.py                    |  37 ++
src/llm_wiki/webapp/routes/inbox.py      | 586 ++++++++++++++++++++++++--
src/llm_wiki/webapp/templates/inbox.html | 696 ++++++++++++++++++++++++++-----
tests/test_inbox_registration.py         |  36 ++
```

## Required check results

| Check | Result | Notes |
| --- | --- | --- |
| 1. 변경 범위 검사 | partial | Partial fix touched expected files plus `tests/test_inbox_registration.py`, which is acceptable for STAB-001 coverage. |
| 2. 영향 흐름 검사 | failed | SEC-001 fix test fails; route/test contract not validated. |
| 3. 기능 완성도 검사 | failed | Fix request not completed; fix evidence missing. |
| 4. 안정성 검사 | failed | Focused test suite has one failing test. |
| 5. 유지보수성 검사 | not blocking | No additional maintainability blocker beyond original notes. |
| 6. 보안/설정 검사 | failed | SEC-001 cannot be considered fixed until capped diagnostic behavior is validated by a passing test. |
| 7. 검증 증거 검사 | failed | No Phase 4 fix evidence file and focused pytest fails. |

## Validation executed

```text
.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v
```

Result:

```text
1 failed, 23 passed, 1 warning
```

Failing test:

```text
tests/test_phase4_review_failed_workbench.py::test_diagnostic_response_respects_size_cap
assert payload_large["truncated"] is True
E assert False is True
```

Additional checks:

```text
.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py tests/test_phase4_review_failed_workbench.py tests/test_inbox_registration.py
=> pass

git diff --check
=> pass
```

## Failure analysis

The current SEC-001 test likely has a fixture problem rather than proving the
route cap is broken:

- `_make_failed_item(...)` creates `small-diag.md` and `large-diag.md` with the
  same markdown content.
- Inbox registration has deduplication by content hash, so the second item can
  reuse the first item/source rather than producing a distinct failed item.
- The test then writes large content to `Inbox/_Failed/large-diag.md.diagnostic.md`,
  while the endpoint may read the deduped item's original diagnostic sidecar.
- A manual one-item reproduction using the real generated diagnostic path showed
  `truncated=True` and content length `16384`.

This still blocks approval because the repository test is red and no fix
evidence exists.

## User functional test

- Required: yes, UI/UX change.
- Status: pending.
- User previously selected "Fix Build 먼저 실행".
- User testing must wait until fix tests are green.

## Decision

`changes_requested`

## Required next Build/Fix actions

1. Keep or adjust the partial fixes only if they satisfy the original fix request.
2. Fix the SEC-001 test fixture so it is dedupe-safe:
   - use unique content per failed item, or
   - write the large diagnostic content to the exact `report_path` returned by
     `inbox.move_to_failed(...)`.
3. Produce `.code-planner/03-build/evidence/phase-4-fix-evidence.md`.
4. Re-run:

```text
.venv/bin/python -m pytest tests/test_phase4_review_failed_workbench.py tests/test_inbox_domain.py tests/test_inbox_registration.py -v
.venv/bin/python -m py_compile src/llm_wiki/inbox.py src/llm_wiki/webapp/routes/inbox.py tests/test_phase4_review_failed_workbench.py tests/test_inbox_registration.py
git diff --check
```

5. Run `/check phase-4` again.
