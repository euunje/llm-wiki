# Phase 1 — Check Fix Request

Check verdict: `changes_requested`. Resubmit via `/fix phase-1`.

This file lists actionable items discovered during check for Phase 1 — CLI Foundation. Items are grouped by severity. `Build` (`build-*` agents) owns the source fixes; `Check` continues to gate until the listed acceptance criteria pass and evidence is regenerated.

Reused planning sources:

- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`
- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`

---

## B-1 — Hardcoded `.env` key mapping leaked into reusable source

| Field | Value |
| --- | --- |
| id | B-1 |
| short title | Hardcoded `.env` key mapping leaked into source |
| problem target | `src/llm_wiki/llm/models.py` (the `_request_endpoint` helper constructed at the current Build layer introduced a chat-completions inference path), and any related diagnostic output that hardcodes environment variable names. The map from `LOCAL_LLM_*` to `LLM_WIKI_*` was performed as a one-shot operation against the local `.env`. The reusable `wiki` code path, however, must not depend on a fixed remapping layer that operators have to perform manually — it must consume the contract described in `.env.sample` and the planning docs directly. |
| reason | Reusable source must not silently assume that a non-planning key namespace exists in the operator's `.env`. Operators following `.env.sample` should not have to re-map `LOCAL_LLM_*` to `LLM_WIKI_*` for `wiki models test` or any other command. The current Build layer assumes such a remap exists. |
| improvement spec | 1. Update the default settings in `src/llm_wiki/config/settings.py` so the model catalog reads endpoint, model name, and capability from `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, and `LLM_WIKI_EMBEDDING_MODEL` (env overrides) when YAML values are empty, without requiring a manual mapping in `.env`. 2. Align `.env.sample` so every advertised key is consumed by reusable code. 3. Remove the implicit assumption that `LOCAL_LLM_*` keys will be present. 4. Make sure `wiki settings get` reflects the resolved endpoint/model name so the operator can verify without launching a chat request. 5. Re-run the secret-safe end-to-end with `LLM_WIKI_*` keys alone (no `LOCAL_LLM_*` present) and confirm `models test chat_default` still returns `status=ok`. |
| suggested build agent | build-core-dev |
| validation required | Run a fresh validation workspace where the project `.env` only contains `LLM_WIKI_*` keys (delete or skip `LOCAL_LLM_*`). Re-run the full Phase 1 E2E (`init → ingest → normalize → chunk → embed → models test → sync`) and confirm both chat and embedding succeed. |
| acceptance criteria | - Default settings or env overlay reads `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, `LLM_WIKI_EMBEDDING_MODEL` automatically when settings YAML leaves the relevant fields empty. - `wiki models test chat_default` and `wiki models test embedding_default` succeed in a workspace whose `.env` only has the `LLM_WIKI_*` keys. - `wiki settings get` shows the resolved endpoint/model_name fields. - Evidence file documents the new validation run. |

---

## BLOCKER items to fix before commit

These items must be fixed before re-running `/check phase-1`.

### BL-1 (security-config, blocker) — Credential leak via `Authorization` header

| Field | Value |
| --- | --- |
| id | BL-1 |
| short title | Credential leak via Authorization header on configured `models test` failure |
| problem target | `src/llm_wiki/llm/models.py` (lines building headers and the failure exception branch) and `src/llm_wiki/common.py` (`mask_sensitive` / `SENSITIVE_FRAGMENTS`). |
| reason | The Authorization header is constructed with the API key (`f"Bearer {api_key}"`). When the configured request fails, that header is passed through `mask_sensitive`, recorded into the artifact JSON, persisted into the artifact DB row, and returned to the CLI. The `mask_sensitive` heuristics only redact keys whose names contain `secret`, `token`, `password`, `api_key`, `apikey`, or `key`; the header name `Authorization` is not redacted, so the bearer token is emitted and persisted in plaintext. |
| improvement spec | 1. Never include `Authorization` (or any other header that carries the API key) in the artifact payload, DB row, job/agent error, or CLI response. 2. Treat every configured-failure branch (network error, non-OK HTTP, JSON decode failure, exception) as a credential-safe branch: only `api_key_present` (boolean) or an explicitly redacted representation is allowed. 3. Add a debug-only escape hatch (e.g., behind a developer flag) that is OFF by default. 4. Update `mask_sensitive` or add a separate `redact_headers` helper that explicitly strips `Authorization`, `Proxy-Authorization`, `X-Api-Key`, and any value carrying `Bearer ` regardless of key name. 5. Add an automated test that injects a synthetic API key, makes a configured request fail, and asserts the CLI payload, artifact file, artifact DB row, job error, and agent run error contain no bearer fragment. |
| suggested build agent | build-backend-script-dev |
| validation required | Run a new test (`test_models_test_configured_failure_does_not_leak_credentials`) against an endpoint that always returns HTTP 500 or refuses connections, with a synthetic non-empty API key. Assert no part of the resulting artifact / artifact DB row / job / agent_run contains the literal token or any substring that is recognisable as the bearer. |
| acceptance criteria | - No path under `models test` failure emits a real or synthetic API key value. - `mask_sensitive` (or a new helper) redacts `Authorization` and any header whose value contains `Bearer `. - New pytest + manual runner tests pass against the configured-failure path. - Evidence file documents the new test and output. |

### BL-2 (scope, blocker) — Phase 3 and Phase 2 docs staged in Phase 1 commit

| Field | Value |
| --- | --- |
| id | BL-2 |
| short title | Phase 3 / Phase 2 docs added to the Phase 1 commit |
| problem target | `docs/02_web_ui_features.md` (Phase 3 Web UI), `docs/04_llm_schema_guide.md` (Phase 2 LLM schema guide). |
| reason | These files document Phase 3 Web UI features and the Phase 2 LLM schema/prompt contract. They are out of Phase 1 scope and must not appear in the Phase 1 commit. The evidence file (`.code-planner/03-build/evidence/phase-1-build-evidence.md`) does not list `docs/` as modified, so the build agent introduced these without their plan. |
| improvement spec | Either remove `docs/02_web_ui_features.md` and `docs/04_llm_schema_guide.md` from this commit, or carve them into a clearly distinct commit. Re-confirm the planned Phase 1 docs baseline (`.code-planner/02-planning/`) does not designate these files as Phase 1 inputs. |
| suggested build agent | build-core-dev |
| validation required | `git status --short` must not list `docs/02_web_ui_features.md` or `docs/04_llm_schema_guide.md` for the Phase 1 commit, and the build evidence file must not list them as Phase 1 changes. |
| acceptance criteria | The Phase 1 commit / staged set no longer contains the two Phase-out-of-scope docs. (Phase 1 CLI features reference doc `docs/01_cli_features.md` and the cross-phase schema reference `docs/03_schema_and_ontology.md` are acceptable if clearly identified as project-wide docs that predate Phase 1.) |

---

## HIGH items

### HI-1 (stability, high) — Embedding timeout relies on `SIGALRM`

| Field | Value |
| --- | --- |
| id | HI-1 |
| short title | Embedding timeout is platform-dependent |
| problem target | `src/llm_wiki/pipeline/embed.py` (`_time_limit` and the embedder/inference call sites), and `src/llm_wiki/config/settings.py` (`embedding.fastembed_timeout_seconds`). |
| reason | The `_time_limit` context manager silently yields without enforcing a deadline when `SIGALRM` is unavailable or when the configured timeout is non-positive. Stalled `fastembed.TextEmbedding` construction or inference would therefore hang instead of falling back to `fallback-hash-v1`. |
| improvement spec | 1. Add a portable bounded mechanism: keep `SIGALRM` for POSIX, fall back to `threading.Timer` + thread cancellation or `concurrent.futures` with a wall-clock deadline on platforms without `SIGALRM`. 2. Reject `fastembed_timeout_seconds <= 0` and apply a sane minimum. 3. Ensure the timeout covers both `TextEmbedding(...)` construction and `embedder.embed(...)`. 4. Reset/cancel timers and clean up any background workers. 5. Add a test that fakes a stalled embedder to confirm fallback happens within the configured budget on a non-POSIX path (or document the supported platforms explicitly). |
| suggested build agent | build-backend-script-dev |
| validation required | Inject a stalled embedder object that sleeps past the configured timeout and confirm the embed command returns with `backend: fallback_hash` and `backend_detail.reason` referencing the timeout within the budget. |
| acceptance criteria | The fastembed path is bounded on the validation host (and a portable fallback is documented). The existing `tests/test_normalize_chunk_embed.py` fallback test continues to pass. New tests cover non-POSIX / non-positive timeout / stalled embedder scenarios. |

### HI-2 (stability, high) — Pipeline leaves jobs in `running` on failure

| Field | Value |
| --- | --- |
| id | HI-2 |
| short title | Pipeline raises after job `running` without marking the job failed |
| problem target | `src/llm_wiki/pipeline/normalize.py`, `src/llm_wiki/pipeline/chunk.py`, `src/llm_wiki/pipeline/embed.py`. |
| reason | Each pipeline creates a job in `running` state. If subsequent operations raise, there is no `try/except` that calls `update_job(..., status="failed", error_json=...)` before re-raising or returning the failure. The job stays in `running` indefinitely, which breaks `wiki status`, `wiki healthcheck`, and `wiki lint` counts. |
| improvement spec | 1. Wrap the post-creation code in a `try/except` that calls `update_job` (and agent_run if applicable) with `status="failed"` and a machine-readable error, then re-raise or surface a CLI-friendly error. 2. Update the negative-path tests to assert the job is terminal and carries an error blob. 3. Make sure the error encoding is `json.dumps`ed like other error blobs. |
| suggested build agent | build-backend-script-dev |
| validation required | Force a normalization failure (unknown source) and a chunk failure (read-only data dir or invalid UTF-8) and inspect the `jobs` table or `wiki status` output to confirm no job stays in `running`. |
| acceptance criteria | All pipelines created in Phase 1 transition to `succeeded` or `failed` and never leave a `running` row. Negative-path tests assert this. |

### HI-3 (stability, high) — Stale queued normalize job after explicit `wiki normalize`

| Field | Value |
| --- | --- |
| id | HI-3 |
| short title | Duplicate normalize jobs after explicit normalize call |
| problem target | `src/llm_wiki/pipeline/ingest.py` (creates a queued normalize job), `src/llm_wiki/pipeline/normalize.py` (creates another one). |
| reason | Ingest creates a queued normalize job. The explicit `wiki normalize` command creates a second normalize job for the same source and finishes successfully, leaving the first job still in `queued`. The full E2E shows `jobs_queued=1` after the entire pipeline is done. |
| improvement spec | 1. Pick a consistent ownership/correlation policy. Either (a) ingest does not pre-create a normalize job and lets `wiki normalize` create the canonical one, or (b) ingest's queued job references a correlation id that `wiki normalize` consumes and updates instead of creating a duplicate. 2. Update tests and evidence accordingly. |
| suggested build agent | build-backend-script-dev |
| validation required | Run the full ingest → normalize → chunk → embed pipeline on a fresh workspace and assert `SELECT COUNT(*) FROM jobs WHERE job_type='normalize' AND status='queued'` is zero. |
| acceptance criteria | After a successful end-to-end pipeline, no orphan `queued` jobs of type `normalize`, `chunk`, or `embed` remain. |

---

## MEDIUM items

### M-1 (stability, medium) — Embedder output validation missing

| Field | Value |
| --- | --- |
| id | M-1 |
| short title | No validation of fastembed output before marking success |
| problem target | `src/llm_wiki/pipeline/embed.py` (after `embedder.embed(...)`). |
| reason | Empty output, short output, or mismatched dimensions are recorded as success. `zip` silently truncates short output to the shorter list and persists an inconsistent state. |
| improvement spec | 1. Validate that the number of returned vectors equals the number of targets, that the dimension is non-zero and consistent, and that no vector is all-zero. 2. On validation failure, either fall back to `fallback-hash-v1` with an explicit reason, or surface a partial-success / failure. 3. Add tests for empty / short / mismatched / all-zero vector outputs. |
| suggested build agent | build-test-validation |
| validation required | Cover each shape in `tests/test_normalize_chunk_embed.py` (or a new test module) and assert the embed command never reports success on a malformed vector output. |
| acceptance criteria | Embed output is validated before persistence; malformed outputs trigger fallback or a documented failure; tests cover each shape. |

### M-2 (security-config, medium) — Artifact path traversal via `model_id`

| Field | Value |
| --- | --- |
| id | M-2 |
| short title | Artifact path containment is not enforced for `model_id` |
| problem target | `src/llm_wiki/jobs/records.py` (`record_artifact`), `src/llm_wiki/llm/models.py` (call sites passing `model_id`). |
| reason | Artifact directories are constructed from `target_id` / model id strings without containment checks. A model id like `../etc` could write outside the artifact root. |
| improvement spec | 1. Reject `target_id` / `model_id` values that contain path separators, `..`, absolute paths, or NUL bytes. 2. Apply canonical containment checks (resolve the candidate path, verify `path.is_relative_to(artifact_root)`). 3. Add tests for `../`, `/abs/path`, and Unicode separators if relevant. |
| suggested build agent | build-backend-script-dev |
| validation required | Inject malicious model ids and assert no file is written outside the workspace. |
| acceptance criteria | Malicious ids are rejected with a clear error; legitimate model ids continue to work; tests cover each shape. |

### M-3 (affected-flow, medium) — `.env.sample` does not match runtime contract

| Field | Value |
| --- | --- |
| id | M-3 |
| short title | `.env.sample` contract is not honored by reusable code |
| problem target | `.env.sample`, `src/llm_wiki/config/settings.py`, `src/llm_wiki/llm/models.py`, `README.md`. |
| reason | The sample advertises `LLM_WIKI_LLM_ENDPOINT`, `LLM_WIKI_CHAT_MODEL`, `LLM_WIKI_EMBEDDING_MODEL` but reusable code only reads `LLM_WIKI_API_KEY`. The successful E2E used an external `LOCAL_LLM_* → LLM_WIKI_*` remap that ran outside the reusable code. |
| improvement spec | 1. Either consume the advertised keys directly (preferred — see B-1) or explicitly document that they are for external integration only and that the actual configuration comes from `vault/90_Settings/settings.yaml`. 2. Make `wiki settings get` reflect the resolved values for endpoint and model name. 3. Update README to remove the impression that those keys are honored. |
| suggested build agent | build-core-dev |
| validation required | Run a workspace where the `.env` only contains `LLM_WIKI_*` keys and confirm `models test` works without any external remap step. |
| acceptance criteria | Operators using only the documented `.env.sample` do not need an external remap step. |

### M-4 (affected-flow, medium) — Inconsistent ingest/normalize evidence wording

| Field | Value |
| --- | --- |
| id | M-4 |
| short title | Build evidence contradicts itself about the real `.env` and test counts |
| problem target | `.code-planner/03-build/evidence/phase-1-build-evidence.md` (lines 5-6 claim the real `.env` was never read; lines 179-185 describe loading it; line 128 says the manual runner mirrors every pytest case; coverage differs between 29 pytest and 26 manual tests). |
| reason | The evidence claims both that the real `.env` was never read and that it was loaded; the manual runner does not mirror the mock-endpoint success test added later. This misleads reviewers and the future Check pass. |
| improvement spec | Reconcile the evidence: state that the real `.env` was loaded only into the test subprocesses' environment, never echoed, never persisted into the artifact directory, and explicitly mark the mock-endpoint success test as a pytest-only test that the manual runner does not mirror. |
| suggested build agent | build-test-validation |
| validation required | Re-run pytest and the manual runner side by side and update the evidence to reflect the actual distinct coverage. |
| acceptance criteria | The evidence statements are consistent with the actual validation procedure. |

---

## LOW / NOTE items

### L-1 (maintainability, note) — Evidence wording inconsistency

Item already covered in M-4.

---

## Summary of fix-request flow

1. Build picks up this file via `/fix phase-1` and addresses each item using the suggested build agent.
2. After Build completes the changes, regenerate `.code-planner/03-build/evidence/phase-1-build-evidence.md` with the new validation runs.
3. Re-run `/check phase-1` to inspect fix evidence and run gate verification. The recheck report should be created under `.code-planner/04-check/recheck/phase-1-recheck-report.md`.
