# Phase 6 — End-to-end validation checklist (manual)

## Purpose

This checklist is the **human-driven E2E matrix** that
`.code-planner/02-planning/validation/01-validation-plan.md` (Phase 6
section) requires:

> - qmd/Obsidian reset is documented as one-time test setup only.
> - Raw-to-Inbox test preparation is documented.
> - E2E validates document file, markdown scrape, pasted text, large
>   document, failed route, review route, archive move.
> - Successful ingest verifies both Wiki page create/update and Raw
>   archive movement.

The companion document is
`.code-planner/03-build/evidence/phase-6-test-reset-guide.md`, which must
be used to bring the test vault into the "Pending counts match §5.3"
starting state before any row below is ticked.

> **Read this first.** This checklist is intentionally exhaustive. Each
> row is one observation. Filling in the "Result" column is the
> tester's contribution; an empty "Result" means the row is still
> pending. Do not paraphrase results — paste the actual CLI / UI
> outcome or a one-line "pass / fail + why".

## Out of scope and pre-conditions

- This checklist does **not** drive a real-provider LLM call
  automatically. Each row that requires LLM inference marks
  `[LLM-call-required]` and assumes the operator has confirmed Ollama /
  configured endpoint availability per
  `.code-planner/03-build/phases/phase-6-execution-brief.md`
  ("Real provider LLM calls unless the user explicitly provides
  environment/approval").
- This checklist does **not** validate visual UX. Visual UX sign-off is
  the job of `.code-planner/04-check/phase-5B-user-test-checklist.md`
  (Phase 5B). Phase 6 reuses that sign-off as a precondition.
- This checklist is the **source of truth for the "manual E2E" gap** in
  `.code-planner/03-build/evidence/phase-6-build-evidence.md` §"Manual
  E2E status".

## Pre-condition checklist

| # | Pre-condition | Result |
| - | --- | --- |
| P-1 | Phase 5B source-validated (`phase-5B-build-evidence.md` final Ready = true) |  |
| P-2 | Phase 5B user test sign-off (`phase-5B-user-test-checklist.md`) passes or is explicitly deferred |  |
| P-3 | `phase-6-test-reset-guide.md` §5.3 reports expected pending counts |  |
| P-4 | `wiki status` exits 0 (LLM host reachable) — only required for `[LLM-call-required]` rows |  |
| P-5 | `git diff --check` is clean (no whitespace errors) — re-run from §"Pre-flight" of reset guide |  |

> Do not proceed past P-5 with any pending row. If a pre-condition is
> blocked, mark the entire E2E pass as **blocked** and route back to
> the relevant build/check evidence.

## E2E matrix

Each row uses the following shorthand:

- `[LLM]` — requires a real-provider LLM call (real Ollama endpoint or
  user-approved equivalent).
- `[no-LLM]` — verifiable without an LLM call (filesystem, DB state,
  routing, queue registration, dedup).
- Result: write **pass**, **fail**, or **skip-with-reason** plus a
  short note (CLI excerpt / file path / DB row).

### Row group A — Input registration matrix (Inbox pending)

These rows cover the three Inbox input types as registered by the
canonical paths. They verify registration, dedup, queue placement, and
that **no** LLM call has happened yet.

| # | Item | Path / API | Mode | Pass criteria | Result |
| - | --- | --- | --- | --- | --- |
| A-1 | Document file | `wiki add <pdf>` **or** Web `/ingest` upload | `[no-LLM]` | `Inbox/Files/<file>.pdf` exists; `inbox_items.state = 'pending'`; `input_type = 'document_file'`; `sources` row count unchanged |  |
| A-2 | Document file dedup | `wiki add <pdf>` twice | `[no-LLM]` | Second call returns `deduped = true`; only one `inbox_items` row; only one file on disk |  |
| A-3 | Markdown scrape | `wiki add <md>` **or** Web `/ingest` upload | `[no-LLM]` | `Inbox/Markdown/<file>.md` exists; `input_type = 'markdown_file'`; `state = 'pending'` |  |
| A-4 | Pasted text | Web `/ingest` paste form | `[no-LLM]` | `Inbox/Text/<slug>.md` exists; YAML frontmatter has `title`, `input_type: pasted_text`, optional `source_url`, `tags`; `state = 'pending'` |  |
| A-5 | Existing Raw Sources import before processing | Web `/ingest` → `Raw Sources에서 Inbox로 가져오기` button (calls `POST /ingest/scan`) | `[no-LLM]` | Each file under `raw/` becomes one `inbox_items` row with `state = 'pending'`, `relpath` under `Inbox/Files/` or `Inbox/Markdown/`; the `sources` table receives **no** row for these files before `/ingest/start` is invoked |  |
| A-6 | Large document registered for chunked path | `wiki add <large.pdf>` | `[no-LLM]` | Registration succeeds; `parsers.parse(...)` returns `ParsedDocument.chunks` non-empty (verified by `tests/test_chunked_extraction.py` for the parser layer) |  |

### Row group B — Routing matrix (failed / review / archive / chunked)

These rows cover the runtime routing outcomes after the operator clicks
**작업으로 보내기 →** (Web) or runs `wiki ingest` (CLI).

| # | Item | Trigger | Mode | Pass criteria | Result |
| - | --- | --- | --- | --- | --- |
| B-1 | Document file → success route | A-1 + `wiki ingest` or `/ingest/start` | `[LLM]` | `inbox_items.state = 'ingested'`; `sources.status = 'ingested'`; wiki pages created/updated under `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`; see also row C-1 |  |
| B-2 | Markdown scrape → success route | A-3 + `wiki ingest` or `/ingest/start` | `[LLM]` | Same as B-1 with `Inbox/Markdown/...` source relpath |  |
| B-3 | Pasted text → success route | A-4 + `wiki ingest` or `/ingest/start` | `[LLM]` | Same as B-1 with `Inbox/Text/...` source relpath |  |
| B-4 | Large document → chunked extraction | A-6 + `wiki ingest` or `/ingest/start` | `[LLM]` | `ParsedDocument.chunks` is consumed; `/jobs` shows `phase · NN%` per chunk; `jobs.events` contain `extraction_chunk_*` events; final job state is `done` (not `failed`) |  |
| B-5 | Failed route | A-1 with deliberately malformed fixture (e.g. `sample-bad.pdf`) + `wiki ingest` | `[LLM]` | `inbox_items.state = 'failed'`; `sources.status = 'error'`; file moved to `Inbox/_Failed/`; `Inbox/_Failed/<file>.diagnostic.md` written with non-empty diagnostic; `/inbox?state=failed` lists the item |  |
| B-6 | Review route | Trigger one of the documented Phase 4 review conditions (low confidence, ambiguous classification, source/canonical slug conflict, etc.) on a real LLM call | `[LLM]` | `inbox_items.state = 'review'`; candidate pages staged under `Inbox/_Review/`; `/inbox?state=review` lists the item with similar Wiki candidates and merge/create/classify actions; `wiki status` shows Review count + `/inbox?state=review` hint |  |
| B-7 | Archive move (success path) | After B-1/B-2/B-3 success | `[no-LLM]` after a successful ingest exists | Original file in `Inbox/{Files,Markdown,Text}/...` is **moved** into `raw/` (Raw archive); `inbox_event` of type `moved_to_archive` recorded; `wiki status` shows file in `raw/` count |  |
| B-8 | Existing Raw Sources import → processing | A-5 + per-item `wiki ingest` (CLI) or per-row `작업으로 보내기 →` (Web) | `[LLM]` | The previously-imported Raw file now has a `sources` row (`materialize_source_for_inbox_item`), a `ingest_jobs.source_id` link, and the same archive-move outcome as B-7 |  |

### Row group C — Successful ingest verification (create + update)

Per `phase-6-test-reset-validation.md` "성공한 ingest는 Wiki page
create/update와 Raw archive 이동을 모두 검증한다."

| # | Item | Mode | Pass criteria | Result |
| - | --- | --- | --- | --- |
| C-1 | Wiki page create | After any successful ingest (`B-1`/`B-2`/`B-3`/`B-4`/`B-8`) | `[LLM]` | New markdown file(s) appear under `wiki/sources/`, `wiki/entities/`, and/or `wiki/concepts/` with frontmatter; `wiki/index.md` references them; `wiki/log.md` records the run |  |
| C-2 | Wiki page update | Re-ingest a previously-ingested Inbox item | `[LLM]` | Existing markdown under `wiki/...` is **updated** (not duplicated); frontmatter timestamps increment; `wiki/log.md` records an "update" line |  |
| C-3 | Raw archive movement | After C-1 or C-2 | `[LLM]` | Original input file is no longer under `Inbox/{Files,Markdown,Text}/...`; it is present under `raw/` with a stable name (collision-safe variant if needed); `inbox_event` of type `moved_to_archive` recorded |  |

### Row group D — Operator-driven workbench actions (Phase 4 contract)

These rows are tied to Phase 4 review/failed workbench contracts but
are exercised as part of the Phase 6 matrix because the Inbox queue is
the entry point.

| # | Item | Mode | Pass criteria | Result |
| - | --- | --- | --- | --- |
| D-1 | `/inbox?state=failed` shows diagnostics, retry / open source / hold / archive / log delete | `[no-LLM]` after B-5 | All 5 actions render and dispatch to the matching `POST/DELETE` endpoint without 5xx |  |
| D-2 | `/inbox?state=review` shows similar Wiki candidates and merge / create new / classify / reprocess / hold actions | `[no-LLM]` after B-6 | All 5 actions render and dispatch to the matching endpoint; similarity preview is non-empty |  |
| D-3 | `wiki retry <inbox_item_id>` on a Failed item | `[no-LLM]` | Item moves `failed → pending`; diagnostic sidecar file removed; relpath restored under the original `Inbox/<type>/` folder |  |

### Row group E — Edge cases and out-of-scope confirmations

| # | Item | Mode | Pass criteria | Result |
| - | --- | --- | --- | --- |
| E-1 | Empty-Inbox render | `[no-LLM]` with empty `inbox_items` | `/ingest` shows `Inbox 대기 항목이 없습니다.` and the `Raw Sources에서 Inbox로 가져오기` CTA, not the legacy `Raw Sources 스캔` copy |  |
| E-2 | No `wiki reset` command exists | `[no-LLM]` | `wiki --help` and `wiki --help <sub>` do not list `reset`, `wipe`, `clean`, `purge`, or equivalent; matches `phase-6-test-reset-guide.md` §7 grep guard |  |
| E-3 | Legacy error sources still render in `/ingest` for retry visibility | `[no-LLM]` | `/ingest` merges legacy `sources.status = error` rows with the Inbox-pending rows; each carries the legacy `재시도 필요` badge and no `input_type` pill |  |
| E-4 | No real-vault destructive action ran without backup (if Path B was used) | `[no-LLM]` | `phase-6-build-evidence.md` §"Destructive test-setup performed" lists every `mv` and references the matching backup timestamp; no `rm -rf` log |  |

## Per-row results

> Tester fills this in. One row per matrix entry. Empty cell = pending.

| Row | Result | Note (CLI excerpt / file path / DB row) |
| --- | --- | --- |
| A-1 | pass | Disposable vault `/tmp/opencode/llm-wiki-phase6-e2e-20260716-234943`: CLI `wiki add` registered document fixtures as pending rows `#1 Inbox/Files/sample-bad.pdf`, `#2 Inbox/Files/sample-large.txt`, `#3 Inbox/Files/sample-doc.txt`; `source_status_counts []`. |
| A-2 | pending | Duplicate add was not executed in this run. |
| A-3 | pass | CLI `wiki add` registered `#4 Inbox/Markdown/sample-markdown.md` as `state=pending`, `input_type=markdown_file`; no sources rows before ingest. |
| A-4 | pass | Web/TestClient `/ingest/paste` returned status 200 and registered `#5 Inbox/Text/phase-6-pasted-text-fixture.md` as `state=pending`, `input_type=pasted_text`. |
| A-5 | pass | Web/TestClient `/ingest/scan` returned status 200, `scan_counts {'registered': 1, 'deduped': 0, 'skipped': 0, 'errors': 0, 'added': 1}` and registered `#6 Inbox/Markdown/existing-raw.md`; `source_status_counts []`. |
| A-6 | pass-registration-only | Large fixture registered as `#2 Inbox/Files/sample-large.txt`, `state=pending`, `input_type=document_file`; parser chunk consumption remains covered by automated parser tests and B-4 is blocked on LLM reachability. |
| B-1 | fail | Per operator instruction, skipped `/models`/`ensure_ready()` and sent a real ingest request using existing ENV from `~/.hermes/.env` (`LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_API_KEY`; secret value not printed). Auth header verified: `Authorization: Bearer <redacted>` (key length 35) was attached to the request and the endpoint returned `HTTP 200` with body `{"error":"Unexpected endpoint or method. (POST /chat/completions)"}`. The current OpenAI-compat client therefore reads an empty content payload, which the retry path also re-encounters. The LLM call itself did not produce JSON; the endpoint rejected the OpenAI-style chat-completion route. Result: `result_ok False`, `pages_created 0`, `pages_updated 0`; inbox item `#3` transitioned to `failed`, source `#1` status `error`, wiki markdown count remained 2. Logs: `/tmp/opencode/phase6-llm-ingest-small-send-without-model-check.log`, `/tmp/opencode/phase6-llm-raw-capture-md3.log`, `/tmp/opencode/phase6-llm-auth-header.log`. |
| B-2 | pass | Difference from the failing run identified: existing working code/test convention expects an OpenAI-compatible base URL ending in `/v1` (see `tests/test_phase4_local_llm_runtime.py`); raw diff test showed base host returned `{"error":"Unexpected endpoint or method. (POST /chat/completions)"}`, while `base + /v1` returned `content: "OK"`. Retested `#4 Inbox/Markdown/sample-markdown.md` with `/v1` suffix, `provider=openai-local`, existing model/key, thinking off. Result: `event extracted Phase 6 Markdown Fixture Overview`, 4 pages created, `inbox_items.state='ingested'`, `sources.status='ingested'`, wiki markdown count 6. Log: `/tmp/opencode/phase6-llm-ingest-md-v1.log`. |
| B-3 | pass | After archive-finalization fix, retested `#5 Inbox/Text/phase-6-pasted-text-fixture.md` with corrected `/v1` OpenAI-compatible host, existing model/key, thinking off. Result: extraction succeeded (`Phase 6 Pasted Text Fixture Overview`), 4 pages created, `inbox_items.state='ingested'`, `sources.status='ingested'`. Log: `/tmp/opencode/phase6-llm-ingest-paste-v1-archive-fix.log`. |
| B-4 |  |  |
| B-5 |  |  |
| B-6 |  |  |
| B-7 | pass | After archive-finalization fix, B-3 success moved original `Inbox/Text/phase-6-pasted-text-fixture.md` to `raw/phase-6-pasted-text-fixture.md`, removed the original Inbox file, recorded `moved_to_archive`, then finalized item state as `ingested`. `sources.relpath` also points to `raw/phase-6-pasted-text-fixture.md`. Log: `/tmp/opencode/phase6-llm-ingest-paste-v1-archive-fix.log`. |
| B-8 |  |  |
| C-1 | pass | After B-2 success, new pages exist: `wiki/concepts/job-progress-verification.md`, `wiki/concepts/raw-sources-import.md`, `wiki/concepts/inbox-first-ingestion.md`, `wiki/sources/phase-6-markdown-fixture.md`; `wiki/index.md` and `wiki/log.md` were updated. |
| C-2 |  |  |
| C-3 | pass | Verified with B-3/B-7: original pasted-text input no longer exists under `Inbox/Text/`; archived file exists under `raw/`; `inbox_events` tail includes `moved_to_archive` followed by final ingested completion event; `sources.relpath` matches the raw archive relpath. |
| D-1 |  |  |
| D-2 |  |  |
| D-3 |  |  |
| E-1 |  |  |
| E-2 |  |  |
| E-3 |  |  |
| E-4 |  |  |

## Decision inputs (blocking)

After all 24 rows are filled in, the operator chooses one:

1. **All rows pass** — Phase 6 manual E2E closes; commit gate per
   `.code-planner/03-build/phases/phase-6-execution-brief.md` reopens.
2. **Some rows fail** — open a `/fix phase-6` request, treating the
   failing rows as the bug list. The non-destructive reset guide in
   `phase-6-test-reset-guide.md` can be re-run after the fix lands.
3. **Operator defers LLM rows** — record the `[LLM]` rows as
   `skip-with-reason: deferred real-provider LLM approval` and route
   the deferred rows to a follow-up user-test checklist. The
   `[no-LLM]` rows must still pass for Phase 6 to be considered
   source-validated.

## Evidence paths

- **This checklist:** `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
  (this file).
- **Test setup:** `.code-planner/03-build/evidence/phase-6-test-reset-guide.md`.
- **Build evidence:** `.code-planner/03-build/evidence/phase-6-build-evidence.md`.
- **Check report:** `.code-planner/04-check/phase-6-check-report.md`
  (to be produced after the operator's per-row results are committed).
- **User test delegation:** `.code-planner/04-check/phase-5B-user-test-checklist.md`
  (visual UX — separate from this E2E).
