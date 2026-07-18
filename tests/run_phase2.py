from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "samples"
TESTSET_DIR = REPO_ROOT / "testset"
RUNTIME_ROOT = Path("/tmp/opencode/phase2-runtime")


def _fresh_workspace(name: str) -> Path:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    target = RUNTIME_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


class Phase2TestCase(unittest.TestCase):
    workspace: Path

    def setUp(self) -> None:  # type: ignore[override]
        self.workspace = _fresh_workspace(self._testMethodName)

    def tearDown(self) -> None:  # type: ignore[override]
        if os.environ.get("PHASE2_KEEP_TMP") == "1":
            return
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _invoke(self, *cli_args: str) -> tuple[int, dict[str, object]]:
        from llm_wiki.cli import build_parser

        argv = [*cli_args, "--path", str(self.workspace), "--json"]
        parser = build_parser()
        args = parser.parse_args(argv)
        return args.handler(args)

    def _pipeline(self, source_path: Path) -> str:
        self.assertEqual(self._invoke("init")[0], 0)
        code, payload = self._invoke("ingest", str(source_path))
        self.assertEqual(code, 0, payload)
        source_id = str(payload["source_id"])
        self.assertEqual(self._invoke("normalize", source_id)[0], 0)
        self.assertEqual(self._invoke("chunk", source_id)[0], 0)
        return source_id


class SchemaQualityTests(Phase2TestCase):
    def test_candidate_schema_rejects_tags_and_forbidden_metadata(self) -> None:
        from llm_wiki.schema import validate_candidate_envelope

        envelope = {
            "task_type": "extract_claims",
            "source_id": "source_demo",
            "schema_version": "candidate.v1",
            "claim_candidates": [],
            "node_candidates": [
                {
                    "candidate_key": "node_01",
                    "node_type": "concept",
                    "title": "RAG",
                    "aliases": ["LLM"],
                    "summary": "RAG는 LLM 응답을 검색 근거로 보강한다.",
                    "evidence_claim_keys": ["claim_missing"],
                    "review_route": "normal_review",
                    "review_reason": "검토 필요",
                    "related_candidate_keys": [],
                    "tags": ["bad"],
                    "human_decision": {},
                }
            ],
            "relation_candidates": [],
            "mapping_candidates": [],
            "claim_conflict_candidates": [],
        }
        result = validate_candidate_envelope(envelope)
        self.assertFalse(result["ok"])
        errors = "\n".join(result["errors"])
        self.assertIn("tags", errors)
        self.assertIn("human_decision", errors)

    def test_candidate_schema_rejects_nested_forbidden_metadata(self) -> None:
        from llm_wiki.schema import validate_candidate_envelope

        envelope = {
            "task_type": "extract_claims",
            "source_id": "source_demo",
            "schema_version": "candidate.v1",
            "claim_candidates": [
                {
                    "candidate_key": "claim_01",
                    "statement": "RAG는 LLM 응답을 보강한다.",
                    "claim_relation_type": "describes",
                    "subject_ref": {"kind": "new_node", "candidate_key": "node_01", "human_decision": {}},
                    "object_ref": {"kind": "existing_node", "id": "concept_rag"},
                    "evidence": [{"source_id": "source_demo", "chunk_id": "chunk_01", "locator": {"char_start": 0, "char_end": 5, "quote": "RAG"}}],
                    "review_route": "normal_review",
                    "review_reason": "검토",
                    "related_candidate_keys": ["node_01"],
                }
            ],
            "node_candidates": [
                {
                    "candidate_key": "node_01",
                    "node_type": "concept",
                    "title": "RAG",
                    "aliases": ["LLM"],
                    "summary": "RAG는 LLM 응답을 검색 근거로 보강한다.",
                    "evidence_claim_keys": ["claim_01"],
                    "review_route": "normal_review",
                    "review_reason": "검토",
                    "related_candidate_keys": ["claim_01"],
                }
            ],
            "relation_candidates": [],
            "mapping_candidates": [],
            "claim_conflict_candidates": [],
        }
        result = validate_candidate_envelope(envelope)
        self.assertFalse(result["ok"])
        self.assertIn("payload.claim_candidates[0].subject_ref.human_decision", "\n".join(result["errors"]))

    def test_language_policy_preserves_english_terms(self) -> None:
        from llm_wiki.quality import evaluate_language_policy

        result = evaluate_language_policy(
            "이 문서는 Claude Code와 OpenCode의 token overhead를 비교한다.",
            expected_terms=["Claude Code", "OpenCode", "token"],
        )
        self.assertTrue(result["ok"], result)


class CliQualityFlowTests(Phase2TestCase):
    def test_extract_map_retry_summary_compile_flow(self) -> None:
        from llm_wiki.db.schema import connect

        source_id = self._pipeline(SAMPLES_DIR / "rag.md")
        code, extract = self._invoke("extract-claims", source_id)
        self.assertEqual(code, 0, extract)
        self.assertTrue(extract["validation"]["ok"])
        self.assertGreaterEqual(extract["candidate_count"], 2)
        self.assertGreater(extract["quality_evaluation"]["scores"]["summary_quality"], 0)

        code, mapping = self._invoke("map", source_id)
        self.assertEqual(code, 0, mapping)
        self.assertTrue(mapping["validation"]["ok"])
        self.assertEqual(mapping["quality_evaluation"]["scores"]["mapping_quality"], 1.0)

        candidate_id = mapping["persisted_candidates"][0]["id"]
        code, retry = self._invoke("retry", candidate_id, "--instruction", "RAG와 Agentic RAG를 구분")
        self.assertEqual(code, 0, retry)
        self.assertEqual(retry["target_kind"], "candidate")
        self.assertTrue(retry["superseded_by"])

        code, summary = self._invoke("summarize", "source:" + source_id)
        self.assertEqual(code, 0, summary)
        self.assertIn("RAG", json.dumps(summary, ensure_ascii=False))

        code, compile_payload = self._invoke("compile", "source:" + source_id)
        self.assertEqual(code, 0, compile_payload)
        self.assertTrue((self.workspace / compile_payload["preview_path"]).exists())

        conn = connect(self.workspace / "data" / "wiki.sqlite")
        try:
            old = conn.execute("SELECT status, superseded_by FROM review_candidates WHERE id = ?", (candidate_id,)).fetchone()
            retry_row = conn.execute("SELECT consumed_run_id FROM retry_instructions WHERE target_candidate_id = ?", (candidate_id,)).fetchone()
            prompt_count = conn.execute("SELECT COUNT(*) FROM prompt_versions WHERE state = 'confirmed'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(old["status"], "superseded")
        self.assertIsNotNone(old["superseded_by"])
        self.assertEqual(retry_row["consumed_run_id"], retry["consumed_run_id"])
        self.assertGreaterEqual(prompt_count, 6)

    def test_html_conversion_and_testset_markdown_quality_smoke(self) -> None:
        html = self.workspace / "input.html"
        html.write_text("<h1>RAG</h1><p>LLM retrieval와 ontology mapping을 설명한다.</p>", encoding="utf-8")
        self.assertEqual(self._invoke("init")[0], 0)
        code, payload = self._invoke("ingest", str(html))
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(self._invoke("normalize", str(payload["source_id"]))[0], 0)

        if TESTSET_DIR.exists():
            for name in ["AlexsJones-Ilmfit.md", "OKF SPEC.md", "systima-claude-code-vs-opencode-token-overhead.md"]:
                source_id = self._pipeline(TESTSET_DIR / name)
                code, extract = self._invoke("extract-claims", source_id)
                self.assertEqual(code, 0, extract)
                self.assertTrue(extract["validation"]["ok"])
                self.assertGreater(extract["quality_evaluation"]["overall_score"], 0)

    def test_url_ingest_records_failure_artifact(self) -> None:
        from llm_wiki.cli import main

        self.assertEqual(self._invoke("init")[0], 0)
        exit_code = main(["ingest", "https://example.invalid/article", "--path", str(self.workspace), "--json"])
        self.assertEqual(exit_code, 2)
        artifact_dir = self.workspace / "data" / "artifacts" / "ingest"
        artifacts = list(artifact_dir.rglob("*.json"))
        self.assertTrue(artifacts)
        payloads = [json.loads(path.read_text(encoding="utf-8")) for path in artifacts]
        self.assertTrue(any(payload.get("type") == "url_unsupported" for payload in payloads))


if __name__ == "__main__":
    unittest.main(verbosity=2)
