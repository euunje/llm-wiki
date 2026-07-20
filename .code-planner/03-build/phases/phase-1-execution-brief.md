# Phase 1 Execution Brief

## Source planning docs

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.code-planner/02-planning/features/feature-phase1-cli-behavior.md`
- `.code-planner/02-planning/features/feature-phase1-init-folder-structure.md`
- `.code-planner/02-planning/schemas/sqlite-schema-draft.md`
- `.code-planner/02-planning/schemas/llm-candidate-json-schema-draft.md`
- `.code-planner/02-planning/validation/cli-e2e-test-plan.md`

## Phase goal

Implement Phase 1 — CLI Foundation: Python CLI entrypoint, YAML settings/sample env, Vault/data/SQLite initialization, Source/Chunk/Embedding/Job/AgentRun/Artifact recording, Markdown ingest/normalize/chunk/embed pipeline, LLM connection test/artifact contract, operational CLI commands, and placeholder contracts for Phase 2 quality commands.

## Work units

### WU-001. Existing code discovery and duplicate-risk scan
- Purpose: Confirm project structure, existing code/tests/configs, and duplicate risks before implementation.
- Assigned agent: `codebase-explorer`
- Expected files: no source edits; discovery recorded in evidence.
- Completion criteria: Existing code and target-file recommendations are known.
- Verification: Discovery result references actual files and no edits are made.

### WU-002. Project bootstrap and CLI skeleton
- Purpose: Create safe Python package foundation and CLI entrypoint.
- Assigned agent: `build-core-dev`
- Expected files: `pyproject.toml`, `.gitignore`, `.env.sample`, `README.md`, `src/llm_wiki/__init__.py`, `src/llm_wiki/cli/__init__.py`, core CLI router files.
- Completion criteria: `wiki --help` or `python -m llm_wiki.cli --help` can run after install/path setup; real `.env` remains ignored and untouched.
- Verification: CLI help command exits successfully.

### WU-003. Settings, paths, SQLite schema, jobs/artifacts
- Purpose: Implement YAML settings, path resolution, initial SQLite schema/migration, and common job/artifact recording.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/config/**`, `src/llm_wiki/db/**`, `src/llm_wiki/jobs/**`.
- Completion criteria: Settings load/save works; `wiki init` can create DB schema; jobs/artifacts can be persisted.
- Verification: SQLite table inspection and JSON output from relevant commands.

### WU-004. Init/settings/doctor commands
- Purpose: Implement `wiki init`, `wiki settings get/set`, and `wiki doctor` according to Phase 1 contracts.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli/init_cmd.py`, `src/llm_wiki/cli/settings_cmd.py`, `src/llm_wiki/cli/doctor.py` or equivalent command modules.
- Completion criteria: Folder structure is created idempotently; settings sensitive output is masked; doctor reports paths/DB/FTS/env/model settings.
- Verification: Run `wiki init` twice in a temporary workspace and run `wiki settings get --json`, `wiki doctor --json`.

### WU-005. Markdown ingest pipeline and embedding
- Purpose: Implement Phase 1 Markdown-only ingest, ingest-text, inbox scan, normalize, chunk, and embed.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/pipeline/**`, command modules for `inbox`, `ingest`, `ingest-text`, `normalize`, `chunk`, `embed`.
- Completion criteria: Markdown sample creates Source row, raw/source refs, normalized Markdown, SourceChunk rows, and embedding metadata/vector rows.
- Verification: Run sample `ingest → normalize → chunk → embed`; unsupported PDF/URL returns explicit Phase 2 guidance.

### WU-006. LLM models/routing and candidate/placeholder commands
- Purpose: Implement configurable model list/test, route get/set, candidate JSON/artifact contract, and Phase 1 placeholders for ask/map/summarize/compile/link/extract-claims.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/llm/**`, `src/llm_wiki/schema/**`, placeholder command modules.
- Completion criteria: `wiki models test` records success/failure artifact; placeholder commands emit valid JSON/artifact contracts without claiming final Phase 2 quality.
- Verification: Run `wiki models list`, `wiki models test <model_id>`, `wiki extract-claims <source_id> --json`, and placeholder command smoke tests.

### WU-007. Operational commands
- Purpose: Implement `validate`, `lint`, `fix`, `retry`, `sync`, `status`, `search`, and minimal `healthcheck`/reporting contracts where Phase 1 requires CLI coverage.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli/validate.py`, `lint.py`, `fix.py`, `retry.py`, `sync.py`, `status.py`, `search.py`, `healthcheck.py` or equivalent.
- Completion criteria: Commands return clear exit codes, JSON reports, artifacts where required, and dry-run/apply policy for sync.
- Verification: Run command smoke tests and the Phase 1 sync dry-run.

### WU-008. Tests, real validation, and evidence readiness
- Purpose: Add fixtures/tests and execute Phase 1 validation commands with captured results.
- Assigned agent: `build-test-validation`
- Expected files: `samples/**`, `tests/**`, `.code-planner/03-build/evidence/phase-1-build-evidence.md`.
- Completion criteria: Required validation is executed; pass/fail/blocked states are recorded with command output; no dev/test processes remain.
- Verification: Run unit/E2E tests plus manual CLI E2E commands from the validation plan.

## Out of scope

- Web UI and approved Phase 3 mockup implementation.
- Actual LLM wiki prompt quality beyond Phase 1 candidate/artifact contract.
- PDF/Office/HTML/URL conversion support beyond explicit unsupported/Phase 2 guidance.
- Automatic file watcher sync.
- Git commit/push unless separately requested.
- Real secret generation or editing committed secret values.

## Validation commands

- `python3 --version`
- `python3 -m pytest tests -q`
- `python3 -m llm_wiki.cli --help`
- `python3 -m llm_wiki.cli init --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli init --path <tmp-workspace> --json` again for idempotency
- `python3 -m llm_wiki.cli settings get --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli doctor --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli ingest samples/rag.md --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli normalize <source_id> --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli chunk <source_id> --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli embed source:<source_id> --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli models list --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli models test <model_id> --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli extract-claims <source_id> --path <tmp-workspace> --json`
- `python3 -m llm_wiki.cli sync --path <tmp-workspace> --json`
- `git status`, `git diff --stat`, `git diff --check` when applicable.

## Git checkpoint plan

- Repository is currently not assumed to be initialized.
- Create safety `.gitignore` before any checkpoint consideration.
- Inspect `git status`, `git diff --stat`, and `git diff --check` before completion reporting.
- Do not commit or push unless explicitly requested by the user.

## Risks

- Greenfield implementation is broad; Phase 1 may finish as partial if dependency installation, fastembed model download, or LLM endpoint validation is unavailable.
- Existing `.env` may contain real secrets; it must remain ignored and must not be copied into `.env.sample` with real values.
- `fastembed`/model download may require network and disk availability.
- `sqlite-vec` may be unavailable; Phase 1 can record embedding vectors in SQLite and report sqlite-vec availability separately unless Planning requires otherwise.
