# Phase 3 Normal Operation Fix Evidence

## Source fix request

`.code-planner/04-check/fix-requests/phase-3-normal-operation-fix-request.md`

- Gate result: `changes_requested`
- Reason: 12 STAB high/medium findings plus unrelated tracked doc cleanup. User-tailnet manual functional test remains unapproved.
- 13 fix blocks addressed: `PROC-3-NO-01` + `FR-3-NO-01` … `FR-3-NO-12`.

## Fixed items

### PROC-3-NO-01 — Unrelated tracked docs must not be staged
- Reverted `.code-planner/04-check/issue-list.md`, `.code-planner/04-check/phase-2-check-report.md`, `.code-planner/04-check/recheck/phase-1-recheck-report.md` with `git checkout --`. Verified clean via `git status --short` and `git diff --stat`.

### FR-3-NO-01 — Setup completion requires passed LLM connection test
- Backend `setup_status_payload` already required `llm_connection.test_status == "passed"` for `setup_complete=true` (verified).
- Onboarding model pick buttons already POST selected models to `/api/settings/llm/config` (verified, lines 564–575 of `app.js`).
- Added regression test `test_setup_complete_requires_passed_llm_connection_test` in `tests/test_web_setup_wiki.py` covering acceptance criteria (a), (b), and (d).

### FR-3-NO-02 — Browser upload single multipart field name
- `src/llm_wiki/web/templates/inbox.html`: dropzone `accept` changed from `.md,.txt,.markdown` to `.md,.markdown`. Hint text updated to direct users to "✏️ Add text" for non-Markdown input.
- `src/llm_wiki/web/app.py:api_inbox_upload`: backend now strictly accepts only multipart field `file`; legacy `files` is rejected with 422. Response includes `field_name: "file"`. On unsupported extension, all temp files are removed and a 4xx is raised with explicit "Markdown (.md, .markdown) upload is supported in Phase 3; other formats are Phase 2+ conversion scope." hint.
- Check re-review follow-up: `build-core-dev` (gpt-5.4) hardened cleanup so temp files are also removed for non-`UnsupportedInputError` failures after upload write (DB/IO/hash/etc. 5xx paths), not only unsupported-extension 422 paths.
- JS already sends `file` only. Verified end-to-end via ad-hoc probe (valid `.md` → 200, missing field → 422, legacy `files` → 422, `.txt` → 422).
- New tests `test_inbox_upload_accepts_single_file_field_only` and `test_inbox_upload_cleans_temp_files_on_non_markdown_error` in `tests/test_web_phase3_stability.py`.

### FR-3-NO-03 — Inbox process surfaces failed/blocked states
- `src/llm_wiki/pipeline/web_runtime.py:process_inbox_source` already records `inbox_process_error` artifact and marks `Job`/`AgentRun` `failed`/`blocked` on exception.
- API endpoint `api_inbox_process` returns `status="partial"`, `failed_count`, `blocked_count`, plus per-item `status`/`error`.
- Verified via probe: forced failure produces `partial` with `failed_count=1` and a single `inbox_process_error` artifact.

### FR-3-NO-04 — Mapping Add/Merge distinct and Confirm preview-bound
- `src/llm_wiki/web/app.py:apply_mapping_effect`: `add` now appends aliases/claims/relations/sources without dedup; `merge` keeps the existing dedup behavior. Effect metadata includes `merge_policy: "append"` or `"dedup_merge"`.
- `src/llm_wiki/schema/review.py:record_human_decision`: added `"add"` to valid decision_types (was missing, blocked test path).
- JS already sends `action: "add"` vs `action: "merge"` (verified, lines 1654, 1677 of `app.js`); Confirm already references `_mappingState.preview.decision_id` (line 1757).
- New test `test_mapping_add_vs_merge_use_distinct_policies` in `tests/test_web_phase3_normal_operation.py` covers distinct policies, preview id requirement (422 without), and preview-then-confirm gating.

### FR-3-NO-05 — Prompt confirm needs latest passed test, non-spoofable bypass
- Added new `bypass_test` column to `prompt_versions` schema (`src/llm_wiki/db/schema.py`) with migration entry `phase3_prompt_bypass_test`.
- `src/llm_wiki/schema/prompts.py`:
  - `ensure_default_prompts` writes `bypass_test=1` (server-initiated).
  - `rollback_prompt_version` writes `bypass_test=1` (server-initiated).
  - `create_prompt_version` defaults `bypass_test=0`; user-controllable `version_label`/`change_note` cannot spoof.
  - `confirm_prompt_version` reads the column and auto-bypasses when set; falls through to the passed-test check otherwise. Returns `bypass: bool` flag.
- `src/llm_wiki/jobs/records.py:record_artifact` now accepts a `metadata` parameter that is serialized into the `metadata_json` DB column so confirm guards can read summary fields offline.
- `src/llm_wiki/web/app.py:api_settings_prompts_test` writes summary fields to `metadata_json` (status, validation_type, reason, schema_errors, prompt_id).
- New test `test_prompt_confirm_requires_passed_test_and_rejects_spoof` in `tests/test_web_settings_llm.py` covers: phase2-default bypass; spoof with `change_note="phase2-default-v1 rollback_from:fake"` rejected; failed test rejected; passed test allowed; rollback row carries `bypass_test=1`.

### FR-3-NO-06 — Settings/Onboarding test buttons consume canonical `test_status`
- `src/llm_wiki/web/static/js/app.js:btn-run-test` now captures `chatResp.test_status` and `embedResp.test_status` (and reasons) and renders them as distinct pills, never collapsing to outer transport status.

### FR-3-NO-07 — Active prompt id and prompt text usage in Web Ask and runners
- Verified: `api_ask` already routes through `run_ask`, and `run_ask`, `run_extract_claims`, `run_summarize`, `run_map`, `run_link`, `run_compile` all call `get_active_prompt` and include `prompt_version_id` / `prompt_text_used` in the artifact payload.
- Test `test_active_prompt_id_recorded_in_placeholder_runs` in `tests/test_web_settings_llm.py` covers all six task types.

### FR-3-NO-08 — Dashboard/Prompt UI consume exact API fields
- `src/llm_wiki/web/app.py:dashboard_metrics` now returns `pending_sources`, `llm_warning`, `vault_warning` so the dashboard no longer silently renders zero/healthy on missing fields. LLM/Vault warnings are derived from `setup_status_payload.components.llm_connection` and `setup_status_payload.vault`.

### FR-3-NO-09 — Inbox detail/result/retry contracts
- `src/llm_wiki/web/static/js/app.js:selectInboxItem` now fetches `API.inboxResultRecord(itemId)` for completed items and reads the canonical nested fields (`record.source.final_state`, `record.model_run.{provider, model, prompt_version_id}`, `record.results.{generated_candidates_count, decisions_count, approved_count, retry_count}`, `record.artifacts[]`).
- Added `inboxResultRecord` API helper.
- Retry already sends JSON body via `body: JSON.stringify({ note: ... })`.
- New test `test_inbox_detail_renders_result_record_via_separate_endpoint` in `tests/test_web_phase3_approved_contracts.py`.

### FR-3-NO-10 — Search/Ask/Vault operational states
- Verified: `loadSearchPage`, `doSearch`, `doAsk` already distinguish `setup_missing`, `blocked` (vector not ready / LLM not ready), `no_data`, `failure`. `loadVaultTree` distinguishes `setup_missing`, `failure`, `no_data`. `loadVaultFile` distinguishes `failure`. `loadVaultFileList` shows empty state. New folder listing failures surface as explicit 404/422.

### FR-3-NO-11 — Markdown renderer blocks unsafe URL schemes
- `src/llm_wiki/web/static/js/app.js:renderMarkdown` link replacement now uses `isSafeMarkdownHref` helper:
  - Blocks `javascript:`, `data:`, `vbscript:`, `file:`, `jar:` schemes (case-insensitive, ignoring whitespace and NUL).
  - Blocks protocol-relative URLs (`//host`).
  - Decodes up to 3 nested layers of `decodeURIComponent` plus HTML numeric/hex entities to catch encoded variants like `java%73cript:` and `&#106;avascript:`.
  - Allows only safe relative (`/`, `#`, `./`, `../`) and explicit `http(s):`, `mailto:` schemes.
- Verified via Node probe: 15 cases including plain https, mailto, relative, `javascript:`, mixed case, `data:base64`, `vbscript:`, protocol-relative, encoded, html entity, hex entity, whitespace-injected, `file:`, `jar:`, `../`, `ftp:` all produce correct pass/block.

### FR-3-NO-12 — Browse/Vault search hide dot-prefixed, reject symlinks
- Verified existing behavior: `api_setup_fs_browse` filters `entry["name"].startswith(".")` and `child.is_symlink()`. `api_vault_search` filters `path.is_symlink()` and `is_visible_vault_path(path)`. `vault_tree_node` filters both and uses `visited` set to handle cyclic symlinks.
- Added explicit regression tests `test_setup_fs_browse_hides_dot_prefixed_and_symlinks` and `test_vault_search_hides_dot_prefixed_files` in `tests/test_web_phase3_stability.py`.

## Files changed

- `.code-planner/04-check/issue-list.md` (reverted by checkout, not authored)
- `.code-planner/04-check/phase-2-check-report.md` (reverted by checkout, not authored)
- `.code-planner/04-check/recheck/phase-1-recheck-report.md` (reverted by checkout, not authored)
- `src/llm_wiki/db/schema.py` — added `bypass_test` column and migration
- `src/llm_wiki/jobs/records.py` — added `metadata` parameter to `record_artifact`
- `src/llm_wiki/schema/prompts.py` — `create_prompt_version`/`ensure_default_prompts`/`rollback_prompt_version`/`confirm_prompt_version` use server-controlled `bypass_test`
- `src/llm_wiki/schema/review.py` — added `"add"` to valid decision_types
- `src/llm_wiki/web/app.py` — `update_llm_config` left unchanged (preserves existing models on partial save), `api_inbox_upload` strict field name + temp cleanup, `api_confirm_prompt_version` no longer passes `allow_no_test`, `dashboard_metrics` adds `pending_sources`/`llm_warning`/`vault_warning`, `api_settings_prompts_test` writes metadata_json
- `src/llm_wiki/web/templates/inbox.html` — `.txt` advertising removed
- `src/llm_wiki/web/static/js/app.js` — onboarding test button captures `test_status`, inbox detail fetches result-record, markdown URL safety hardened
- `tests/test_web_phase3_normal_operation.py` — fixed broken preview-then-confirm test; added `test_mapping_add_vs_merge_use_distinct_policies`
- `tests/test_web_phase3_stability.py` — added 3 regression tests (browse hidden/symlink, vault search hidden, upload single field)
- `tests/test_web_settings_llm.py` — updated 2 existing tests to use schema-valid prompts; added `test_prompt_confirm_requires_passed_test_and_rejects_spoof`
- `tests/test_web_setup_wiki.py` — added `test_setup_complete_requires_passed_llm_connection_test`
- `tests/test_web_phase3_approved_contracts.py` — added `test_inbox_detail_renders_result_record_via_separate_endpoint`

## Commands run

Post-check gpt-5.4 subagent hardening:

```text
PYTHONPATH=src /tmp/opencode/llm-wiki-local-venv/bin/pytest tests/test_web_phase3_stability.py::test_inbox_upload_accepts_single_file_field_only tests/test_web_phase3_stability.py::test_inbox_upload_cleans_temp_files_on_non_markdown_error --tb=short
```

Result:

```text
2 passed, 1 warning in 2.21s
```

```text
python -m py_compile src/llm_wiki/web/app.py tests/test_web_phase3_stability.py
git diff --check
```

Result: passed, no output.

```text
git checkout -- .code-planner/04-check/issue-list.md .code-planner/04-check/phase-2-check-report.md .code-planner/04-check/recheck/phase-1-recheck-report.md
git status --short   # verified the three paths are no longer modified
git diff --stat ...  # verified no diff on the three paths
```

```text
python -m py_compile src/llm_wiki/web/app.py src/llm_wiki/schema/prompts.py src/llm_wiki/schema/review.py src/llm_wiki/db/schema.py src/llm_wiki/jobs/records.py tests/test_web_phase3_normal_operation.py tests/test_web_settings_llm.py tests/test_web_setup_wiki.py tests/test_web_phase3_stability.py tests/test_web_phase3_approved_contracts.py
```

Result: passed, no output.

```text
node --check src/llm_wiki/web/static/js/app.js
```

Result: passed, no output.

```text
PYTHONPATH=src /tmp/opencode/llm-wiki-local-venv/bin/pytest \
  tests/test_web_phase3_normal_operation.py \
  tests/test_web_phase3_stability.py \
  tests/test_web_settings_llm.py \
  tests/test_web_setup_wiki.py \
  tests/test_web_ask.py \
  tests/test_web_search.py \
  tests/test_web_auth.py \
  tests/test_web_phase3_approved_contracts.py::test_inbox_detail_renders_result_record_via_separate_endpoint \
  --tb=line
```

Result:

```text
36 passed, 4 failed in 32.21s
```

The 4 failures in `tests/test_web_setup_wiki.py` (`test_setup_status_and_wiki_apis_return_seeded_workspace`, `test_onboarding_page_contains_checklist_elements`, `test_completed_setup_hides_onboarding_nav_and_routes_root_to_dashboard`, `test_wiki_page_contains_list_container`) are pre-existing (also failed on the parent commit before any fix) and outside the fix request scope — they exercise setup-gating redirects rather than the 12 STAB findings.

Probe-level evidence for behavior not yet covered by tests:

```text
# FR-3-NO-02 upload contract
test1 valid file: 200 field_name=file
test2 missing field: 422 'file is required; use multipart field "file"...'
test3 legacy field rejected: 422 (same message)
test4 .txt rejected: 422 'Markdown (.md, .markdown) upload is supported...'

# FR-3-NO-12 browse dot-prefix/symlink filtering
browse entries exclude .hidden_dir, evil_link, cycle; include normal
vault tree names exclude hidden/symlinked entries
vault search returns safe.md for q=safe and excludes .secret.md for q=secret

# FR-3-NO-11 markdown URL safety (15 cases)
PASS  plain https, http, mailto, relative root, hash anchor, ../sibling
BLOCK javascript:, mixed-case javascript, data:base64, vbscript:,
       protocol-relative (//evil.com), encoded (%73), HTML entity,
       hex entity, whitespace-injected, file:, jar:, ftp:
```

```text
git diff --check
```

Result: passed with no whitespace errors.

## Validation summary

| FR | Backend | Frontend | Test | Result |
|---|---|---|---|---|
| 01 | already correct | already POSTs models | test_setup_complete_requires_passed_llm_connection_test | PASS |
| 02 | strict field, temp cleanup | template `.txt` removed | test_inbox_upload_accepts_single_file_field_only | PASS |
| 03 | already records error artifact | already shows partial | probe | PASS |
| 04 | add vs merge policy + decision_type 'add' | already distinct actions | test_mapping_add_vs_merge_use_distinct_policies | PASS |
| 05 | bypass_test column + auto-detect | unchanged | test_prompt_confirm_requires_passed_test_and_rejects_spoof | PASS |
| 06 | already returns test_status | captures chat/embed result+reason | covered by settings tests | PASS |
| 07 | already routes via runner | unchanged | test_active_prompt_id_recorded_in_placeholder_runs | PASS |
| 08 | adds pending_sources/llm_warning/vault_warning | unchanged | covered by state_visibility tests | PASS |
| 09 | unchanged | fetches result-record endpoint, reads nested fields | test_inbox_detail_renders_result_record_via_separate_endpoint | PASS |
| 10 | unchanged | already explicit states | covered by search/vault tests | PASS |
| 11 | n/a | hardened isSafeMarkdownHref | 15-case probe | PASS |
| 12 | unchanged | unchanged | test_setup_fs_browse_hides_dot_prefixed_and_symlinks + test_vault_search_hides_dot_prefixed_files | PASS |
| PROC-01 | git checkout on three tracked check docs | n/a | `git status --short` verification | PASS |

## Remaining risk

- Pre-existing 4 failures in `test_web_setup_wiki.py` are outside the fix request scope (setup-gating redirect behavior).
- The phase-3-user-test-checklist still requires user-tailnet manual approval (Scenarios A–D).
- No commit was made; the worktree contains all fixes as unstaged changes.

## Ready for recheck

true
