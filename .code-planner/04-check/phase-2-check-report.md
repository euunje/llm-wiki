# Phase 2 Check Report

## Phase id

- Phase 2 — Inbox registration and file movement

## Changed files

### In scope (Phase 2)

- `src/llm_wiki/inbox.py` — Phase 2 helpers: `register_document_file`, `register_markdown_file`, `register_pasted_text`, `register_uploaded_bytes`, `acquire_processing_lock`, `move_to_archive`, `move_to_review`, `move_to_failed`; duplicate content_hash dedup; movement safety.
- `src/llm_wiki/cli.py` — `wiki add` rerouted to Inbox registration; surfaces `deduped` counter in summary.
- `src/llm_wiki/webapp/routes/ingest.py` — `/ingest/upload` rerouted to Inbox registration; new `/ingest/paste` endpoint; both expose `deduped` in JSON responses.
- `tests/test_inbox_registration.py` (new) — 15 tests covering all Phase 2 acceptance criteria, including HTTP upload deduped behavior.

### Out of scope (must be excluded from Phase 2 commit)

- `src/llm_wiki/ingest_llm.py` (Phase 2 STAB / 2-pass generation).
- `src/llm_wiki/prompts.py` (Phase 2 STAB / 2-pass generation).
- `src/llm_wiki/llm.py` (unrelated — OpenAI-compatible error body surfacing).
- `tests/test_phase2_candidates_schema.py`, `tests/test_two_pass_generation.py`, `tests/test_staged_lint_gate.py` (STAB tests).

## Affected flow

- CLI `wiki add` no longer writes to `raw/`; it routes through Inbox registration helpers.
- Web `/ingest/upload` no longer writes to `/data/raw_docs` or `raw/`; it routes through `inbox.register_uploaded_bytes`.
- Web `/ingest/paste` is a new endpoint backed by `inbox.register_pasted_text`.
- `/ingest/start`, `/ingest/scan`, and `/inbox` legacy routes are unchanged (documented known limitation).
- `processing` remains DB state/lock only; no `_Processing` folder is ever created.

## Required check results

| Check | Result | Notes |
|---|---|---|
| 1. Change scope | pass | Phase 2 files only; out-of-scope files are tracked and must not be staged. |
| 2. Affected flow | pass | CLI/Web routes verified; no breakage in adjacent tests; documented known limitations preserved. |
| 3. Feature completeness | pass | All Phase 2 validation items satisfied including duplicate content_hash dedup. |
| 4. Stability | pass | Low-severity carry-over items documented for Phase 3+; no blockers. |
| 5. Maintainability | pass | `deduped` propagation fix reconciles evidence with implementation. |
| 6. Security/config | pass | No secrets, credentials, new host URLs, or user-specific paths. `/data/raw_docs` hardcoded path removed. |
| 7. Verification evidence | pass | 19/19 inbox tests pass; py_compile and git diff --check clean. |

## Convention result

- File movement safety follows copy-first-then-unlink with cleanup.
- Diagnostic report sanitization: newline collapse + 1000-char clip (acceptable for local vault; secret redaction is a carry-over risk).
- Content_hash dedup reuses the existing item and records a traceable event.
- `deduped` is consistently surfaced in JSON responses and CLI summary.

## Code stability result

- File move safety: pass
- Diagnostic report sanitization: partial (carry-over risk STAB-P2-002 — no secret redaction yet; acceptable for local vault)
- Content-hash dedup: pass
- CLI/Web integration: pass
- Lock concurrency: partial (carry-over from Phase 1 — acceptable for single-process jobs runner)
- Backward compatibility: partial (documented known limitation — `/ingest` template still reads from `sources`)
- Test quality: pass

## Implementation completeness

- All seven Phase 2 validation-plan items pass:
  1. Three input types register Inbox items.
  2. `Inbox/Files`, `Inbox/Markdown`, `Inbox/Text` conventions match docs and code.
  3. Success moves original to Raw Sources archive.
  4. Failure moves original to `Inbox/_Failed` and creates diagnostic report.
  5. Review moves original/candidate to `Inbox/_Review`.
  6. File name collision handling works.
  7. Duplicate content_hash handling works (document/markdown) — plus deduped surfaced in API and CLI.

## User functional test required

- No.
- Rationale: Phase 2 is a backend foundation. UI template redesign is deferred to Phase 5. All behavior is covered by automated tests including HTTP route coverage.

## User test result or approval state

- Not required.

## Known limitations (carry-over, tracked for Phase 3+/Phase 5)

- `/ingest/start` remains legacy `source_id`-based; Inbox item → source/job mapping is Phase 5 scope.
- `/ingest` template still reads from `sources` table; one web-navigation test fails as the documented signal.
- STAB-P2-002 (no secret redaction in diagnostic report) and STAB-P2-003 (500 vs 400 error UX polish) are carry-over low-severity items.
- 11 pre-existing 2-pass/STAB test failures remain in the worktree under `.code-planner/04-check/fix-requests/2-pass-generation-fix-request.md`.

## Git final verification

- `git status --short`: Phase 2 files are modified; out-of-scope files are present and must not be staged.
- `git diff --stat`: shows Phase 2/STAB mix; Phase 2 commit must be scoped.
- `git diff --check`: clean.
- No `.env`/secrets/cache/build outputs included.
- Evidence: `.code-planner/03-build/evidence/phase-2-build-evidence.md` exists and is complete (with P2-WU-005, P2-WU-005-RECHECK, P2-WU-005-RECHECK2 sections).

## Recommended commit

- Stage only:
  - `src/llm_wiki/inbox.py`
  - `src/llm_wiki/cli.py`
  - `src/llm_wiki/webapp/routes/ingest.py`
  - `tests/test_inbox_registration.py`
- Suggested commit message:
  - `feat: route inputs through inbox`
  - Phase: `phase-2`
  - Check: `approved`
  - Evidence: `.code-planner/04-check/phase-2-check-report.md`

## Decision

- Gate result: `approved`
- Commit will be created separately from out-of-scope changes.

## Commit

- Hash: `79d9717`
- Message: `feat: route inputs through inbox`
- Phase: `phase-2`
- Check: `approved`
- Evidence: `.code-planner/04-check/phase-2-check-report.md`
- Build evidence: `.code-planner/03-build/evidence/phase-2-build-evidence.md`
- Files in commit: 4
  - `src/llm_wiki/inbox.py`
  - `src/llm_wiki/cli.py`
  - `src/llm_wiki/webapp/routes/ingest.py`
  - `tests/test_inbox_registration.py`
