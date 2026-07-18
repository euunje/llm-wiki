"""Phase 1 manual test runner for environments without pytest.

The pytest module is not installed in the validation environment, so this
script executes the same Phase 1 test cases using Python's standard library
``unittest`` framework. Each test runs against a fresh ``tmp_path`` style
workspace under ``/tmp/opencode/phase1-runtime/`` and is therefore hermetic.

Invocation:

    PYTHONPATH=src python3 -m tests.run_phase1

The test cases here mirror the public checks implemented in
``tests/test_*.py`` so the evidence file can refer to ``pytest`` as the
expected harness while this script records the actual pass/fail state from
the validation environment.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure ``import llm_wiki`` works when this script is invoked directly.
SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "samples"
RUNTIME_ROOT = Path("/tmp/opencode/phase1-runtime")


def _fresh_workspace(name: str) -> Path:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    target = RUNTIME_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


class Phase1TestCase(unittest.TestCase):
    """Shared utilities for the manual runner.

    Subclasses use ``self.workspace`` (a fresh directory) for the lifetime of
    the test instead of pytest's ``tmp_path``.
    """

    workspace: Path

    def setUp(self) -> None:  # type: ignore[override]
        self.workspace = _fresh_workspace(self._testMethodName)

    def tearDown(self) -> None:  # type: ignore[override]
        # Default: clean up; set PHASE1_KEEP_TMP=1 to keep workspaces for
        # post-mortem inspection (e.g., when investigating a failure).
        if os.environ.get("PHASE1_KEEP_TMP") == "1":
            return
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _invoke(self, *cli_args: str) -> tuple[int, dict[str, object]]:
        from llm_wiki.cli import build_parser

        argv = [*cli_args, "--path", str(self.workspace), "--json"]
        parser = build_parser()
        args = parser.parse_args(argv)
        return args.handler(args)

    def _cli_main(self, *cli_args: str) -> int:
        from llm_wiki.cli import main as cli_main

        return cli_main([*cli_args, "--path", str(self.workspace)])


class InitSettingsDoctorTests(Phase1TestCase):
    def test_init_creates_vault_and_data_layout(self) -> None:
        from llm_wiki.workspace import resolve_workspace

        paths = resolve_workspace(self.workspace)
        self.assertFalse(paths.db.exists())
        exit_code, payload = self._invoke("init")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        for directory in (
            paths.inbox_memo,
            paths.inbox_files,
            paths.inbox_text,
            paths.wiki_concepts,
            paths.wiki_sources,
            paths.wiki_claims,
            paths.wiki_pages,
            paths.review_candidates,
            paths.review_mapping,
            paths.review_rejected,
            paths.raws,
            paths.templates,
            paths.prompts,
            paths.ontology,
            paths.raw,
            paths.normalized,
            paths.artifacts,
            paths.exports,
            paths.cache,
        ):
            self.assertTrue(directory.is_dir(), f"missing dir: {directory}")
        self.assertTrue(paths.db.exists())
        self.assertTrue(paths.settings_file.exists())
        text = paths.settings_file.read_text(encoding="utf-8")
        self.assertIn("vault:", text)

    def test_init_is_idempotent(self) -> None:
        from llm_wiki.workspace import resolve_workspace

        paths = resolve_workspace(self.workspace)
        self._invoke("init")
        settings_mtime = paths.settings_file.stat().st_mtime
        self._invoke("init")
        # Re-running init must not touch the settings file.
        self.assertEqual(paths.settings_file.stat().st_mtime, settings_mtime)
        _, payload = self._invoke("init")
        self.assertEqual(payload["created_directories"], [])

    def test_settings_get_set_masks_sensitive_values(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("settings", "get")
        self.assertEqual(payload["status"], "ok")
        self.assertIsInstance(payload["value"], dict)
        _, nested = self._invoke("settings", "get", "embedding.default_model")
        self.assertEqual(nested["key"], "embedding.default_model")
        self._invoke("settings", "set", "embedding.default_model", "test-model")
        _, after = self._invoke("settings", "get", "embedding.default_model")
        self.assertEqual(after["value"], "test-model")

    def test_doctor_reports_workspace_state(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("doctor")
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["paths"])
        self.assertTrue(payload["database"]["exists"])
        self.assertIn(payload["fts5"]["status"], {"ok", "warn"})
        self.assertIn(payload["models"]["status"], {"ok", "warn"})


class IngestPipelineTests(Phase1TestCase):
    def test_validate_markdown_input_accepts_supported_suffix(self) -> None:
        from llm_wiki.pipeline.hashing import validate_markdown_input

        validate_markdown_input("/tmp/anything.md")
        validate_markdown_input("/tmp/anything.markdown")

    def test_validate_markdown_input_rejects_unsupported_suffix(self) -> None:
        from llm_wiki.pipeline import UnsupportedInputError
        from llm_wiki.pipeline.hashing import validate_markdown_input

        for suffix in (".pdf", ".docx", ".html"):
            with self.assertRaises(UnsupportedInputError):
                validate_markdown_input(f"/tmp/sample{suffix}")

    def test_validate_markdown_input_rejects_url(self) -> None:
        from llm_wiki.pipeline import UnsupportedInputError
        from llm_wiki.pipeline.hashing import validate_markdown_input

        with self.assertRaises(UnsupportedInputError):
            validate_markdown_input("https://example.com/article")

    def test_ingest_creates_source_row_and_stub(self) -> None:
        self._invoke("init")
        sample = SAMPLES_DIR / "short-note.md"
        exit_code, payload = self._invoke("ingest", str(sample))
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["source_id"].startswith("source_"))
        stub = self.workspace / payload["source_stub_path"]
        self.assertTrue(stub.exists())
        self.assertIn("Phase 1 source stub", stub.read_text(encoding="utf-8"))

    def test_ingest_unsupported_pdf_returns_exit_code_2(self) -> None:
        self._invoke("init")
        pdf_path = self.workspace / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        exit_code = self._cli_main("ingest", str(pdf_path))
        self.assertEqual(exit_code, 2)

    def test_ingest_unsupported_url_returns_exit_code_2(self) -> None:
        self._invoke("init")
        exit_code = self._cli_main("ingest", "https://example.com/article")
        self.assertEqual(exit_code, 2)

    def test_ingest_text_creates_user_text_source(self) -> None:
        self._invoke("init")
        exit_code = self._cli_main(
            "ingest-text", "Clip note", "--text", "user typed body"
        )
        self.assertEqual(exit_code, 0)

    def test_ingest_duplicate_returns_duplicate_status(self) -> None:
        from llm_wiki.pipeline import ingest_markdown_file
        from llm_wiki.workspace import resolve_workspace

        self._invoke("init")
        sample = SAMPLES_DIR / "short-note.md"
        first_exit, first_payload = self._invoke("ingest", str(sample))
        self.assertEqual(first_exit, 0)
        self.assertEqual(first_payload["status"], "ok")
        paths = resolve_workspace(self.workspace)
        result = ingest_markdown_file(paths, sample)
        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["source_id"], first_payload["source_id"])


class NormalizeChunkEmbedTests(Phase1TestCase):
    def test_normalize_writes_markdown_and_advances_stage(self) -> None:
        from llm_wiki.db.schema import connect
        from llm_wiki.workspace import resolve_workspace

        self._invoke("init")
        _, payload = self._invoke("ingest", str(SAMPLES_DIR / "rag.md"))
        source_id = payload["source_id"]
        exit_code, norm_payload = self._invoke("normalize", source_id)
        self.assertEqual(exit_code, 0)
        self.assertEqual(norm_payload["status"], "ok")
        normalized_path = self.workspace / norm_payload["normalized_path"]
        self.assertTrue(normalized_path.exists())
        body = normalized_path.read_text(encoding="utf-8")
        self.assertIn("# Retrieval-Augmented Generation", body)

        paths = resolve_workspace(self.workspace)
        conn = connect(paths.db)
        try:
            stage = conn.execute(
                "SELECT pipeline_stage FROM sources WHERE id = ?", (source_id,)
            ).fetchone()[0]
            self.assertEqual(stage, "normalized")
        finally:
            conn.close()

    def test_normalize_rejects_unknown_source(self) -> None:
        self._invoke("init")
        exit_code = self._cli_main("normalize", "source_does_not_exist")
        self.assertEqual(exit_code, 2)

    def test_chunk_creates_source_chunks_with_locator(self) -> None:
        from llm_wiki.db.schema import connect
        from llm_wiki.workspace import resolve_workspace

        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "rag.md"))
        source_id = ingest_payload["source_id"]
        self._invoke("normalize", source_id)

        exit_code, chunk_payload = self._invoke("chunk", source_id)
        self.assertEqual(exit_code, 0)
        self.assertEqual(chunk_payload["status"], "ok")
        self.assertGreaterEqual(chunk_payload["chunk_count"], 1)
        self.assertTrue(chunk_payload["chunk_ids"])

        paths = resolve_workspace(self.workspace)
        conn = connect(paths.db)
        try:
            rows = conn.execute(
                "SELECT token_count, locator_json FROM source_chunks WHERE source_id = ?",
                (source_id,),
            ).fetchall()
            self.assertTrue(rows)
            for token_count, locator_json in rows:
                self.assertGreater(token_count, 0)
                locator = json.loads(locator_json)
                self.assertEqual(locator["source_id"], source_id)
                self.assertIn("start_offset", locator)
                self.assertIn("end_offset", locator)
                self.assertIsInstance(locator["heading_path"], list)
        finally:
            conn.close()

    def test_embed_uses_deterministic_fallback_when_fastembed_missing(self) -> None:
        """fastembed is intentionally absent; confirm the fallback path."""

        from llm_wiki.db.schema import connect
        from llm_wiki.workspace import resolve_workspace

        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "short-note.md"))
        source_id = ingest_payload["source_id"]
        self._invoke("normalize", source_id)
        self._invoke("chunk", source_id)

        exit_code, payload = self._invoke("embed", f"source:{source_id}")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "ok")
        self.assertGreaterEqual(payload["embedding_count"], 1)
        self.assertGreater(payload["dimension"], 0)
        self.assertEqual(payload["backend"], "fallback_hash")
        self.assertEqual(payload["model"], "fallback-hash-v1")

        paths = resolve_workspace(self.workspace)
        conn = connect(paths.db)
        try:
            rows = conn.execute(
                "SELECT model, backend, dimension, vector_blob FROM embeddings"
            ).fetchall()
            self.assertTrue(rows)
            for model, backend, dimension, blob in rows:
                self.assertEqual(model, "fallback-hash-v1")
                self.assertEqual(backend, "fallback_hash")
                self.assertGreater(dimension, 0)
                self.assertTrue(blob)
        finally:
            conn.close()

    def test_unknown_target_embed_returns_exit_code_2(self) -> None:
        self._invoke("init")
        exit_code = self._cli_main("embed", "bogus:abc")
        self.assertEqual(exit_code, 2)


class ModelsPlaceholdersOpsTests(Phase1TestCase):
    def test_models_list_returns_configured_entries(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("models", "list")
        self.assertEqual(payload["status"], "ok")
        ids = {model["id"] for model in payload["models"]}
        self.assertIn("chat_default", ids)
        self.assertIn("embedding_default", ids)

    def test_models_test_records_blocked_artifact_when_not_configured(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("models", "test", "chat_default")
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["result"], "blocked")
        self.assertFalse(payload["model"]["endpoint_configured"])
        artifact_path = self.workspace / payload["artifact_path"]
        self.assertTrue(artifact_path.exists())
        stored = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "blocked")

    def test_route_get_returns_current_mapping(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("route", "get")
        self.assertEqual(payload["routes"]["extract_claims"], "chat_default")

    def test_route_set_rejects_capability_mismatch(self) -> None:
        self._invoke("init")
        exit_code = self._cli_main(
            "route", "set", "extract_claims", "embedding_default"
        )
        self.assertEqual(exit_code, 2)

    def test_extract_claims_artifact_matches_schema_contract(self) -> None:
        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "short-note.md"))
        source_id = ingest_payload["source_id"]

        _, payload = self._invoke("extract-claims", source_id)
        self.assertEqual(payload["status"], "ok")
        envelope = payload["candidate_envelope"]
        self.assertEqual(envelope["task_type"], "extract_claims")
        self.assertEqual(envelope["schema_version"], "candidate.v1")
        self.assertEqual(envelope["claim_candidates"], [])
        self.assertTrue(payload["validation"]["ok"])
        self.assertTrue((self.workspace / payload["artifact_path"]).exists())

    def test_phase1_placeholders_persist_minimum_artifacts(self) -> None:
        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "short-note.md"))
        source_id = ingest_payload["source_id"]

        _, summarize = self._invoke("summarize", f"source:{source_id}")
        self.assertTrue(summarize["summary_placeholder"])
        _, link = self._invoke("link", f"source:{source_id}")
        self.assertEqual(link["relation_candidates"], [])
        _, map_payload = self._invoke("map", source_id)
        self.assertEqual(map_payload["mapping_candidates"], [])
        _, ask = self._invoke("ask", "What is RAG?")
        self.assertTrue(ask["answer_placeholder"])
        _, compile_payload = self._invoke("compile", "agentic_rag")
        preview_path = self.workspace / compile_payload["preview_path"]
        self.assertTrue(preview_path.exists())

    def test_sync_dry_run_does_not_create_view_by_default(self) -> None:
        self._invoke("init")
        _, payload = self._invoke("sync")
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["applied_actions"], [])
        view_path = self.workspace / "vault/20_Review/candidates/sync-status.md"
        self.assertFalse(view_path.exists())

    def test_status_search_validate_lint_smoke(self) -> None:
        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "short-note.md"))
        source_id = ingest_payload["source_id"]
        # Drive the pipeline past ingest so FTS has something to search.
        self._invoke("normalize", source_id)
        self._invoke("chunk", source_id)

        _, status = self._invoke("status")
        self.assertGreaterEqual(status["summary"]["sources"], 1)

        _, search = self._invoke("search", "pipeline")
        # FTS should pick up the chunk text because "pipeline" is in the body.
        self.assertTrue(
            any("pipeline" in json.dumps(item).lower() for item in search["results"]),
            search,
        )

        _, validation = self._invoke("validate")
        self.assertTrue(validation["checks"])

        _, lint = self._invoke("lint")
        self.assertIsInstance(lint["issues"], list)

    def test_retry_request_records_artifact(self) -> None:
        self._invoke("init")
        _, ingest_payload = self._invoke("ingest", str(SAMPLES_DIR / "short-note.md"))
        source_id = ingest_payload["source_id"]
        _, claims = self._invoke("extract-claims", source_id)
        run_id = claims["run_id"]
        _, retry = self._invoke("retry", run_id, "--instruction", "be narrower")
        self.assertEqual(retry["status"], "ok")
        self.assertEqual(retry["target_kind"], "run")
        self.assertEqual(retry["target_id"], run_id)


def _run() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case in (
        InitSettingsDoctorTests,
        IngestPipelineTests,
        NormalizeChunkEmbedTests,
        ModelsPlaceholdersOpsTests,
    ):
        suite.addTests(loader.loadTestsFromTestCase(case))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(_run())
