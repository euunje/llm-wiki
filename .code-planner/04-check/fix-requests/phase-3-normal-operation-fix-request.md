# Phase 3 Normal Operation — Fix Request

## Phase

- Phase ID: `phase-3-normal-operation`
- Build evidence: `.code-planner/03-build/evidence/phase-3-normal-operation/build-evidence.md`
- Source plan: `.code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md`
- Gate result: `changes_requested`
- Reason: 12 STAB high/medium findings plus unrelated tracked doc cleanup. User-tailnet manual functional test remains unapproved.

## Process cleanup (PROC-3-NO-01)

| Field | Value |
|---|---|
| id | PROC-3-NO-01 |
| short title | Unrelated tracked docs must not be staged |
| problem target | `.code-planner/04-check/issue-list.md`, `.code-planner/04-check/phase-2-check-report.md`, `.code-planner/04-check/recheck/phase-1-recheck-report.md` |
| reason | Phase 1/2/4 check bookkeeping tracked modifications are outside Phase 3 normal-operation scope and must be reverted with `git checkout -- <path>` before staging any Phase 3 commit. |
| improvement spec | Before staging, run `git checkout -- .code-planner/04-check/issue-list.md .code-planner/04-check/phase-2-check-report.md .code-planner/04-check/recheck/phase-1-recheck-report.md`. Do not include these files in the Phase 3 normal-operation commit. |
| suggested build agent | build-core-dev |
| validation required | `git status --short` shows only intended files; `git diff --stat` does not include those three paths. |
| acceptance criteria | After cleanup, those three paths are not modified and not staged. |

## FR-3-NO-01 — Setup completion must reflect real LLM connection test (STAB-001)

| Field | Value |
|---|---|
| id | FR-3-NO-01 |
| short title | Setup completion should require verified LLM connection, not just configured fields |
| problem target | `src/llm_wiki/web/app.py:1326-1394` and `src/llm_wiki/config/settings.py` web settings; `src/llm_wiki/web/static/js/app.js:545-547` (model pick buttons only toast). |
| reason | `setup_complete` currently flips on configuration presence (`llm_endpoint`, `llm_api_key`, `llm_chat_model`, `llm_embedding_model`, `vault`, etc.). Onboarding model pick buttons do not persist selection. Saving basic Settings omits model fields, causing backend defaults to overwrite existing models with empty strings. This lets the system report a green Setup state without a real connection test. |
| improvement spec | 1) Run a real LLM connection test (chat + embedding) during Onboarding and expose `components.llm_connection.test_status` (passed/failed/blocked) plus reason. 2) `setup_complete` requires `components.llm_connection.test_status == "passed"`. If LLM is intentionally disabled, expose a distinct `configuration_only` state. 3) Onboarding model pick buttons must POST selected chat/embedding model ids and persist. 4) Settings basic form must submit retained model fields or accept partial updates; do not clobber existing model ids with empty strings. |
| suggested build agent | build-core-dev |
| validation required | Focused pytest for `setup_status_payload` (passed connection flips `setup_complete`), new regression test for partial settings save, JS contract check that model pick POSTs and refreshes status. |
| acceptance criteria | (a) Saved endpoint+key without models does NOT yield `setup_complete=true`. (b) Saved models without connection test does NOT yield `setup_complete=true`. (c) Successful Onboarding test yields `setup_complete=true` and persists models. (d) Updating endpoint/key alone preserves existing model selections. |

## FR-3-NO-02 — Browser upload must use a single multipart field name (STAB-002)

| Field | Value |
|---|---|
| id | FR-3-NO-02 |
| short title | Align browser and backend multipart field name |
| problem target | `src/llm_wiki/web/static/js/app.js:1127-1132` sends `files`; `src/llm_wiki/web/app.py:2152-2154` reads `file`. `src/llm_wiki/web/templates/inbox.html` may advertise `.txt` although endpoint is Markdown-only. |
| reason | Field name mismatch causes upload path to fail before ingestion. Users see silent failure or repeated scans of leftover temp files. |
| improvement spec | Pick one contract (recommended `file`, single-file with size limit). Update JS to append that field. Update backend accordingly. Remove `.txt` advertising if Markdown-only. After failure, delete temp files and emit explicit 4xx with phase-2 hint. |
| suggested build agent | build-core-dev |
| validation required | Focused pytest for `api_inbox_upload` (success path + unsupported extension path + missing field 422). Manual or browser-level upload confirmation. |
| acceptance criteria | One and multiple Markdown uploads create Source rows; non-Markdown returns 422 with phase-2 hint; temp files removed on failure. |

## FR-3-NO-03 — Inbox process must surface failed/blocked states honestly (STAB-003)

| Field | Value |
|---|---|
| id | FR-3-NO-03 |
| short title | Propagate extract/map failures to Job status and UI |
| problem target | `src/llm_wiki/cli/phase1_placeholders.py:229-297`, `src/llm_wiki/pipeline/web_runtime.py:30-171`, `src/llm_wiki/web/app.py:2178-2202`, `src/llm_wiki/web/static/js/app.js:1182-1192`. |
| reason | LLM/map exceptions can be replaced with empty envelopes and `_placeholder_report` always marks Job/AgentRun succeeded. UI treats every non-null 200 response as success. |
| improvement spec | Extract/map/normalize/chunk/embed failures must mark the orchestrator Job `failed` or `blocked` and record an `inbox_process_error` artifact with reason. UI must distinguish success vs partial vs failed vs blocked. If deterministic fallback is intentional, expose `status="degraded"` with reason. |
| suggested build agent | build-backend-script-dev |
| validation required | Focused pytest with injected failures; UI contract test asserting non-success messaging. |
| acceptance criteria | Forced extract failure produces failed Job + error artifact + non-success UI; retry works. |

## FR-3-NO-04 — Mapping Add/Merge must be distinct and Confirm must match preview (STAB-004)

| Field | Value |
|---|---|
| id | FR-3-NO-04 |
| short title | Distinct Add vs Merge; preview-bound Confirm |
| problem target | `src/llm_wiki/web/static/js/app.js:1599-1723`, `src/llm_wiki/web/app.py:998-1172` and `2331-2342`. |
| reason | Add and Merge send `action: "merge"` differing only by ignored `mapping_intent`. Confirm derives action from current radio instead of the recorded preview, so a previewed Add/Merge can confirm as create-new. Step-3 buttons may bypass Confirm. |
| improvement spec | Add and Merge send distinct actions (`add`, `merge`). Preview records a durable preview id; Confirm must reference that preview id and apply the exact previewed action and target. Only Confirm may apply or enqueue. Add/Merge/Create/Edit remain preview-only at every step. |
| suggested build agent | build-core-dev |
| validation required | Focused pytest for preview/confirm chain (preview id, distinct actions, Apply-only-on-confirm); UI snapshot test confirming preview-then-confirm gating. |
| acceptance criteria | (a) Preview Add and Preview Merge produce distinct effects on confirm. (b) Confirm without preview id returns 4xx. (c) Vault markdown does not exist until Confirm. |

## FR-3-NO-05 — Prompt confirm must require latest passed test and use non-spoofable bypass (STAB-005)

| Field | Value |
|---|---|
| id | FR-3-NO-05 |
| short title | Prompt confirm requires passed test artifact and audited bypass |
| problem target | `src/llm_wiki/schema/prompts.py:222-294`, `src/llm_wiki/web/app.py:2444-2452`. |
| reason | When no test artifact exists, confirm falls through. Bypass is inferred from user-controllable `version_label` or `change_note` ("phase2-default-v1", "rollback_from:..."). Web creation accepts arbitrary labels/notes, so the bypass is spoofable. |
| improvement spec | Require latest `prompt_test_result` artifact to exist and be `passed`. Maintain a small internal allow-list of bypass ids (seeded defaults and server-initiated rollbacks), not user-controllable strings. Confirm returns 422 with reason otherwise. |
| suggested build agent | build-backend-script-dev |
| validation required | Focused pytest for confirm with no test (422), failed/blocked test (422), passed test (200), spoofed label (422). |
| acceptance criteria | No-test, failed, and blocked versions cannot confirm; seeded default/rollback bypass is audited and cannot be spoofed by user-controlled label or note. |

## FR-3-NO-06 — Settings/Onboarding test buttons must consume real backend test result (STAB-006)

| Field | Value |
|---|---|
| id | FR-3-NO-06 |
| short title | UI test buttons consume canonical test_status and reason |
| problem target | `src/llm_wiki/web/app.py:2449-2488`, `2553-2577`; `src/llm_wiki/web/static/js/app.js:503-525`, `2227-2232`, `2491-2500`. |
| reason | Backend returns `test_status` plus reason. UI tests outer `status === "passed"` or uses nonexistent fields on status/configuration endpoints. So pass/fail/blocked differentiation is lost. |
| improvement spec | Call the selected model test endpoint; render `test_status` and reason/message distinctly. Render prompt `test_status`, validation type, reason, and schema errors. Never show outer transport status as test result. |
| suggested build agent | build-ui-dev |
| validation required | Focused pytest/JS contract test for passed/failed/blocked fixtures. |
| acceptance criteria | Distinct UI states for passed/failed/blocked; configuration presence is not shown as test pass. |

## FR-3-NO-07 — Active prompt id and prompt text usage in Web Ask and runners (STAB-007)

| Field | Value |
|---|---|
| id | FR-3-NO-07 |
| short title | Route Web Ask through runner with prompt id and use prompt text |
| problem target | `src/llm_wiki/web/app.py:1924-1937` (ask), `src/llm_wiki/cli/phase1_placeholders.py:188-408` (map/link/summarize/compile/ask). |
| reason | CLI records active prompt ids, but runners don't necessarily use the prompt text as system/input prompt. Web Ask bypasses the recorded runner path entirely. |
| improvement spec | Route Web Ask through the same runner used by CLI. All task runners (`extract_claims`, `summarize`, `map`, `link`, `compile`, `ask`) must use the active prompt text and record `prompt_version_id` on AgentRun and artifact payload. |
| suggested build agent | build-backend-script-dev |
| validation required | Focused pytest: change prompt, run each task, assert new prompt_version_id on AgentRun/artifact and that prompt text was used. |
| acceptance criteria | Confirmed prompt change is reflected in next run's AgentRun/artifact and used as execution prompt. |

## FR-3-NO-08 — Dashboard/Prompt UI must consume exact API fields (STAB-008)

| Field | Value |
|---|---|
| id | FR-3-NO-08 |
| short title | Align Dashboard/Prompt UI field names and avoid healthy-zero fallback |
| problem target | `src/llm_wiki/web/app.py:1998-2008`, `2037-2049`; `src/llm_wiki/web/static/js/app.js:289-365`, `2418-2429`. |
| reason | Field names differ between backend and frontend (e.g., `stage_counts` vs `sources.counts`, `pending_by_review_route` vs `review.by_route`). Null responses default to empty collections, leading to all-normal messages on failure. |
| improvement spec | Align exact API field names. Treat missing critical responses as failure/unknown and surface an explicit error banner; never silently render zero/healthy. |
| suggested build agent | build-ui-dev |
| validation required | Focused pytest/UI contract test using fixture with failing Dashboard API. |
| acceptance criteria | Failed Dashboard requests show an error banner; valid nonzero data reaches cards; failed Prompt API load never renders a synthetic green confirmed pill. |

## FR-3-NO-09 — Inbox detail/result/retry contracts (STAB-009)

| Field | Value |
|---|---|
| id | FR-3-NO-09 |
| short title | Align inbox detail/result fields and retry request body |
| problem target | `src/llm_wiki/web/app.py:2076-2142`, `2205-2210`; `src/llm_wiki/web/static/js/app.js:991-1074`. |
| reason | API returns `raw_path`, `preview`, `processing_log`. UI reads `source_path`, `content`, `error`, inline `result_record`. Result-record endpoint exists but is never called. Retry UI POSTs without JSON while backend requires `InboxRetryRequest`. |
| improvement spec | Render the fields actually returned. Fetch the result-record endpoint for completed items. Expose the latest failure artifact/reason. Send a valid retry body. |
| suggested build agent | build-ui-dev |
| validation required | Focused pytest for retry request body and detail field rendering. |
| acceptance criteria | Preview text, processing detail, final record, error reason, and retry work end-to-end. |

## FR-3-NO-10 — Search/Ask/Vault operational states (STAB-010)

| Field | Value |
|---|---|
| id | FR-3-NO-10 |
| short title | Distinct empty/index/blocked/error states for Search/Ask/Vault |
| problem target | `src/llm_wiki/web/static/js/app.js:1952-2137`, `2735-2902`; `src/llm_wiki/web/app.py` related endpoints. |
| reason | Search ignores setup `db_vec_status`; absent vector index shows "no results". Ask does not check response status. Vault folder failures become empty folder. Empty root produces blank HTML. |
| improvement spec | Add explicit no-index/blocked/failure/empty branches with backend reasons preserved. Distinguish index-missing vs no matches; failed/blocked Ask must not render as answer; empty Vault shows action hint; any folder listing failure shows path and error. |
| suggested build agent | build-ui-dev |
| validation required | Focused pytest/UI contract tests for each state. |
| acceptance criteria | Each operational state has a distinct message and next action; no silent fallback. |

## FR-3-NO-11 — Markdown renderer must disallow unsafe URL schemes (STAB-011)

| Field | Value |
|---|---|
| id | FR-3-NO-11 |
| short title | Block javascript:/data:/vbscript: and encoded variants in Markdown href |
| problem target | `src/llm_wiki/web/static/js/app.js:143-178` (link replacement), used for Wiki, Vault, Inbox, Ask views. |
| reason | Text is escaped but `<a href="$2">` is inserted without scheme allow-list. Stored/user-generated content can carry `javascript:` and similar active links. |
| improvement spec | Validate link destinations and allow only safe relative links plus explicitly approved schemes (http/https/mailto). Render unsafe links as inert text or sanitized blocks. |
| suggested build agent | build-ui-dev |
| validation required | Focused tests with javascript:/data:/vbscript: and encoded variants; ensure safe relative and HTTPS links still work. |
| acceptance criteria | Unsafe schemes do not produce active links; safe relative and HTTPS links still render. |

## FR-3-NO-12 — Browse/Vault search must hide dot-prefixed entries and reject symlinks (STAB-012)

| Field | Value |
|---|---|
| id | FR-3-NO-12 |
| short title | Hide dot-prefixed browse entries; reject or constrain symlinks in Vault search |
| problem target | `src/llm_wiki/web/app.py:1893-1903` (browse entries), `2396-2408` (Vault search). |
| reason | Hidden-entry filter missing at API boundary; Vault search follows file symlinks without rejection. |
| improvement spec | Filter names beginning with `.` at the API boundary. Reject or safely constrain symlinks before resolving/listing/reading. Keep all returned paths under the configured root. |
| suggested build agent | build-core-dev |
| validation required | Focused tests: hidden names not enumerated; external and cyclic symlinks neither leak match info nor crash traversal; in-root files still browsable. |
| acceptance criteria | Hidden entries not enumerated; external/cyclic symlinks handled safely; normal files browsable. |

## Validation required overall

- Run focused pytest suites with FastAPI and its test dependencies installed; require zero dependency skips.
- Update stale prompt fixtures.
- Add negative flow coverage for upload, unsupported input, pipeline failure/retry, mapping preview/confirm/Add/Merge, no-test prompt confirmation, real test statuses, active prompt provenance, unauthorized JSON, hidden/symlink paths, and operational states.

## Out of scope for this fix request

- Changing approved UX direction.
- React/Vite/Next/Tailwind build pipeline.
- Multi-user auth/roles.
- Web-based unrestricted Vault editing.

## User functional test

- Required: yes (Scenarios A..D in `.code-planner/02-planning/handoff/phase-3-normal-operation-gap-plan.md`).
- Approval state: not approved.
- Checklist: `.code-planner/04-check/phase-3-user-test-checklist.md` (must be aligned to gap plan scenarios by Build).
## Fix status (post-fix-main)

| id | status | assignedAgent | fixedBy | fixedAt | buildEvidence |
|---|---|---|---|---|---|
| PROC-3-NO-01 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-01 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-02 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-03 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-04 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-05 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-06 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-07 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-08 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-09 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-10 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-11 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
| FR-3-NO-12 | fixed | fix-main | fix-main | 2026-07-20T00:00:00Z | .code-planner/03-build/evidence/phase-3-normal-operation/fix-evidence.md |
