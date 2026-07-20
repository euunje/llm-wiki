# Phase 3 Normal Operation Check Report

## Phase

- Phase ID: `phase-3-normal-operation`
- Phase Name: Web Review UI — 상용화/안정화 (Normal Operation contracts A–F)
- Source plan: `.code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md`
- Execution brief: `.code-planner/03-build/phases/phase-3-execution-brief.md`
- Build evidence: `.code-planner/03-build/evidence/phase-3-normal-operation/build-evidence.md`

## Changed files (Phase 3 in-scope)

Tracked modified (M):

- `.env.sample` (placeholder only; `LLM_WIKI_WEB_ADMIN_PASSWORD`)
- `pyproject.toml` (FastAPI web stack)
- `src/llm_wiki/cli/__init__.py`
- `src/llm_wiki/cli/ops_cmds.py`
- `src/llm_wiki/cli/phase1_placeholders.py`
- `src/llm_wiki/config/settings.py`
- `src/llm_wiki/llm/models.py`
- `src/llm_wiki/pipeline/__init__.py`
- `src/llm_wiki/schema/prompts.py`
- `src/llm_wiki/schema/review.py`
- `src/llm_wiki/search/__init__.py`

Untracked new (??):

- `src/llm_wiki/cli/web_cmd.py`
- `src/llm_wiki/fs_helpers.py`
- `src/llm_wiki/pipeline/web_runtime.py`
- `src/llm_wiki/search/core.py`
- `src/llm_wiki/web/**` (app, templates, static)
- `tests/test_web_*.py` (multiple)

Build artifacts (evidence/notes):

- `.code-planner/03-build/phases/phase-3-execution-brief.md`
- `.code-planner/03-build/evidence/phase-3-normal-operation/build-evidence.md`

Out-of-scope tracked modifications (must NOT be staged — PROC-3-NO-01):

- `.code-planner/04-check/issue-list.md`
- `.code-planner/04-check/phase-2-check-report.md`
- `.code-planner/04-check/recheck/phase-1-recheck-report.md`

Secrets: `.env` not present in worktree; `.env.sample` uses placeholders; no API key/secret value seen in any inspected source or diff.

## Affected flow

- Web entry: `src/llm_wiki/cli/web_cmd.py` → `uvicorn.run(create_app(workspace.root))`.
- Setup status: `src/llm_wiki/web/app.py:setup_status_payload` returns explicit `needs_onboarding`, `setup_complete`, `components`, `llm.*`, `vault.*`, `db_*`. Nav/drawer hides Onboarding when `setup_complete`.
- Inbox processing: `api_inbox_upload` (multipart) → `ingest_markdown_file` → `api_inbox_process` invokes `process_inbox_source` (real synchronous pipeline) creating Job/AgentRun/artifacts; `api_inbox_retry` wraps `InboxProcessRequest`.
- Mapping: `api_mapping_decide` → `record_mapping_preview` (durable preview + metadata) → `confirm_mapping_decision` (apply/queue/blocked).
- Prompt: `test_prompt_version` produces `passed | failed | blocked` artifact; `confirm_prompt_version` checks latest test result.
- State visibility: Dashboard/Inbox/Mapping/Search/Ask/Vault use explicit state banners (no silent fallback).

## Required check results

| Check | Verdict | Note |
|---|---|---|
| 1. Change scope | partial | in-scope change set identified; out-of-scope tracked doc modifications remain — must be cleaned before commit (PROC-3-NO-01). |
| 2. Affected flow | pass | routing, pipeline, mapping, prompt chain connected; import graph clean. |
| 3. Feature completeness | partial | 6/6 WU implemented; 12 STAB findings remain (see Issue List). |
| 4. Stability | partial | High/medium STAB items remain: STAB-001..012 (see fix request). |
| 5. Maintainability | partial | one orphan helper surface noted (`llm/models.py` route labels referenced inconsistently). |
| 6. Security/config | partial | `.env` not staged; `.env.sample` is placeholder; unsafe URL scheme (STAB-011) and hidden/symlink (STAB-012) require fix. |
| 7. Verification evidence | partial | pytest focused: 6 passed, 78 skipped; full dynamic validation blocked by missing FastAPI in env. |

## Convention result

- FastAPI + Jinja2 + Vanilla JS stack unchanged.
- No new dependencies introduced beyond approved Phase 3 stack.
- `git diff --check`: pass.

## Code stability result

12 STAB findings (high/medium) recorded in `.code-planner/04-check/fix-requests/phase-3-normal-operation-fix-request.md`:

- STAB-001 Setup completion without verified connection
- STAB-002 Browser upload multipart field name mismatch
- STAB-003 Inbox process silently reports success on failures
- STAB-004 Add/Merge indistinguishable; Confirm bypass possible
- STAB-005 Prompt confirm without test artifact; spoofable bypass
- STAB-006 UI does not consume backend test_status/reason
- STAB-007 Web Ask lacks active prompt id; runners don't use prompt text
- STAB-008 Dashboard/Prompt API field mismatches; healthy-zero fallback
- STAB-009 Inbox detail/result/retry contracts
- STAB-010 Search/Ask/Vault operational states
- STAB-011 Markdown href unsafe URL scheme (security)
- STAB-012 Browse/Vault hidden entries + symlink handling

## Implementation completeness

- All 6 work units (WU-001..WU-006) implemented per build evidence.
- Focused pytest: 6 passed, 78 skipped (FastAPI runtime unavailable in this env).
- Manual browser verification not performed (per evidence).

## User functional test

- Required: **yes**
- Approval state: **not approved**
- Checklist: `.code-planner/04-check/phase-3-user-test-checklist.md` (must be aligned to gap-plan Scenarios A–D)
- Decision: per user instruction, route as `changes_requested` with full fix-request handoff.

## Git final verification

- `git status --short`: 14 tracked modified, ~30 untracked, 0 staged.
- `git diff --stat`: 14 files changed in scope; out-of-scope `.code-planner/04-check/**` modifications present.
- `git diff --check`: passed.
- Secrets: none in diff or untracked Phase 3 sources (`.env` not in tree; `.env.sample` uses placeholders).
- Process/port cleanup: not applicable (no server/runner started in this check).

## Commit hash

- Not committed in this check.

## Gate decision

**`changes_requested`**

Reasons:

1. 12 STAB high/medium findings across setup, inbox processing, mapping, prompt, state visibility, security (see fix request).
2. Out-of-scope tracked doc modifications (PROC-3-NO-01) must be cleaned before any Phase 3 commit.
3. User Tailnet/manual functional test (Scenarios A–D) remains unapproved.

Returned to Build with `phase-3-normal-operation-fix-request.md`.

## Next actions

1. Build implements the 12 fix-request items and PROC cleanup.
2. User runs the aligned user-test checklist (Scenarios A–D) and approves (or reports new gaps).
3. `git checkout` the three unrelated tracked docs before staging.
4. `/check phase-3-normal-operation` is rerun.