# Phase 1 Execution Brief

## Source planning docs

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/build-handoff/01-build-handoff-brief.md`
- `.code-planner/02-planning/build-handoff/02-build-start-gate.md`
- `.code-planner/02-planning/phases/01-phase-plan.md`
- `.code-planner/02-planning/phases/02-detailed-phase-tasks.md`
- `.code-planner/02-planning/validation/01-validation-plan.md`
- `.hermes/plans/2026-07-21_cli-wiki-generation-phase1.md` (user-requested scope supplement)

## Phase goal

Implement Phase 1 only for the active CLI `wiki ingest` path so it generates real wiki markdown pages from source documents through a shared service layer that Web can call later. Use section-aware chunk iteration instead of full-document truncation, generate ontology-aligned frontmatter/body/tags/source refs plus source summary, keep Web functional, avoid Web Phase 2 UI work, avoid OKF hardcoding, and preserve unrelated existing working-tree edits.

## Work units

### WU-001. Existing code discovery and live/dead path inventory
- Purpose: Confirm active CLI entrypoint, reusable pipeline/page-writer utilities, dead legacy paths, and duplicate-risk before mutation.
- Assigned agent: `codebase-explorer`
- Expected files: no source edits; evidence references only.
- Completion criteria: active `cli/__init__.py` path, current `pipeline/ingest.py`, `pipeline/chunk.py`, `cli/phase1_placeholders.py`, `ingest_llm.py`, tests, and truncation risks are mapped.
- Verification: discovery output cites concrete files/lines.

### WU-002. Shared wiki ingest pipeline foundation
- Purpose: Add/rework a shared service layer for section-aware chunk traversal, wiki page candidate modeling, merge/dedupe, markdown compile/write, source summary generation, and artifact logging.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/pipeline/**`, `src/llm_wiki/schema/**`, reusable helpers under `src/llm_wiki/**` only as needed.
- Completion criteria: pipeline can transform one normalized source into real wiki pages + summary without hardcoded OKF concepts; claims remain internal evidence/log support.
- Verification: focused unit tests for section chunking, candidate schema/merge, compile/write behavior.

### WU-003. Active CLI wiring and compatibility-preserving integration
- Purpose: Wire active `wiki ingest` to the shared pipeline, preserve Web functionality, and replace/avoid `source_text[:2500]` style extraction paths with section-aware iteration.
- Assigned agent: `build-core-dev`
- Expected files: `src/llm_wiki/cli/__init__.py`, `src/llm_wiki/cli/ingest.py`, `src/llm_wiki/cli/phase1_placeholders.py`, `src/llm_wiki/pipeline/ingest.py`, plus integration helpers.
- Completion criteria: `wiki ingest <file> --path <workspace> --json` writes actual markdown pages under the configured Wiki area and still leaves Web code operational.
- Verification: targeted CLI ingest acceptance against `testset/OKF SPEC.md` in a temp workspace.

### WU-004. Regression tests, focused validation, and evidence
- Purpose: Add/update tests for ingest acceptance and run real pytest + CLI verification with exact command output.
- Assigned agent: `build-test-validation`
- Expected files: `tests/**`, `.code-planner/03-build/evidence/phase-1-build-evidence.md`.
- Completion criteria: focused tests pass, acceptance command is executed against temp workspace, generated pages are inspected, and evidence captures real outputs.
- Verification: focused pytest command(s), acceptance CLI command, `git diff --check`, plus workspace artifact inspection.

## Out of scope

- Web Phase 2 review/mapping UI or any redesign.
- New dependency/technology changes not already approved in planning.
- OKF-specific hardcoded concept lists, frontmatter templates, or versioning text.
- Reverting unrelated existing working-tree changes.
- Unsafe git/destructive commands.

## Validation commands

- `.venv/bin/python -m pytest -q tests/test_section_chunking.py tests/test_wiki_page_candidate_schema.py tests/test_wiki_candidate_merge.py tests/test_wiki_compile.py tests/test_cli_wiki_ingest.py`
- `.venv/bin/python -m pytest -q tests/test_ingest_pipeline.py tests/test_normalize_chunk_embed.py`
- `.venv/bin/python -m llm_wiki.cli ingest "testset/OKF SPEC.md" --path <tmp-workspace> --json`
- `git status`
- `git diff --stat`
- `git diff --check`

## Git checkpoint plan

- Inspect `git status`, `git diff --stat`, and `git diff --check` before completion reporting.
- Do not revert unrelated edits already present in the working tree.
- Do not commit or push unless explicitly requested.

## Risks

- Existing codebase contains parallel legacy/new CLI and DB/config paths; integration must avoid breaking Web/runtime consumers.
- Shared service extraction may require small compatibility shims to keep placeholder/Web flows alive while removing truncation.
- LLM-backed paths may be blocked by environment/config; deterministic source-backed fallback must still generate structurally valid wiki pages.
- Acceptance uses real document structure; section detection must avoid code-fence pseudo headings and must surface frontmatter/conformance/versioning from source evidence rather than special-casing OKF.
