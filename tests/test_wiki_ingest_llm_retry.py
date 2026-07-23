from __future__ import annotations

import json
from pathlib import Path

import yaml

from llm_wiki.cli import build_parser


def _invoke(cli_args: list[str], path: Path) -> tuple[int, dict[str, object]]:
    argv = [*cli_args, "--path", str(path), "--json"]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _frontmatter(markdown: str) -> dict[str, object]:
    lines = markdown.splitlines()
    assert lines and lines[0].strip() == "---"
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return yaml.safe_load("\n".join(lines[1:index])) or {}
    raise AssertionError("missing closing frontmatter fence")


def test_wiki_ingest_llm_schema_failure_retries_with_errors(monkeypatch, workspace: Path, samples_dir: Path) -> None:
    from llm_wiki.pipeline import wiki_ingest_llm

    _invoke(["init"], workspace)
    calls: list[dict[str, str]] = []

    def fake_call_json_task(workspace_arg, *, model_id: str, system_prompt: str, user_prompt: str, max_tokens=None):
        calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if len(calls) == 1:
            return {
                "content": json.dumps({"candidates": [{"title": "LLM Page", "summary": "", "tags": [], "draft_body": ""}]}),
                "parsed_json": {"candidates": [{"title": "LLM Page", "summary": "", "tags": [], "draft_body": ""}]},
                "json_repair_applied": False,
                "http_response_size_bytes": 120,
                "api_key_present": True,
            }
        return {
            "content": json.dumps(
                {
                    "candidates": [
                        {
                            "title": "Retried LLM Page",
                            "summary": "A page candidate corrected after schema validation feedback.",
                            "tags": ["retry", "concept"],
                            "draft_body": "# Retried LLM Page\n\n## Definition\n\nCorrected body from retry.",
                        }
                    ]
                }
            ),
            "parsed_json": {
                "candidates": [
                    {
                        "title": "Retried LLM Page",
                        "summary": "A page candidate corrected after schema validation feedback.",
                        "tags": ["retry", "concept"],
                        "draft_body": "# Retried LLM Page\n\n## Definition\n\nCorrected body from retry.",
                    }
                ]
            },
            "json_repair_applied": False,
            "http_response_size_bytes": 220,
            "api_key_present": True,
        }

    monkeypatch.setattr(wiki_ingest_llm, "call_json_task", fake_call_json_task)

    exit_code, payload = _invoke(["ingest", str(samples_dir / "short-note.md"), "--llm"], workspace)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["llm_page_candidate_attempt"]["status"] == "retried"
    assert payload["llm_page_candidate_attempt"]["retry_reason"] == "schema_validation_failed"
    assert len(calls) == 2
    assert "validation errors" in calls[1]["user_prompt"].lower()
    assert "summary is required" in calls[1]["user_prompt"]

    page_text = (workspace / payload["wiki_pages"][0]["path"]).read_text(encoding="utf-8")
    fm = _frontmatter(page_text)
    assert fm["title"] == "Retried LLM Page"
    assert fm["source_ids"] == [payload["source_id"]]
    assert {"short-note", "concept"} <= set(fm["tags"])


def test_wiki_ingest_llm_parse_failure_retries_with_raw_response(monkeypatch, workspace: Path, samples_dir: Path) -> None:
    from llm_wiki.pipeline import wiki_ingest_llm

    _invoke(["init"], workspace)
    calls: list[dict[str, str]] = []

    def fake_call_json_task(workspace_arg, *, model_id: str, system_prompt: str, user_prompt: str, max_tokens=None):
        calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if len(calls) == 1:
            err = ValueError("LLM response JSON object is not balanced")
            err.content = '{"candidates": [{"title": "Broken"'
            raise err
        return {
            "content": '{"candidates": [{"title": "Parse Retry Page", "summary": "Recovered after parse error.", "tags": ["parse", "concept"], "draft_body": "# Parse Retry Page\\n\\nRecovered body."}]}',
            "parsed_json": {
                "candidates": [
                    {
                        "title": "Parse Retry Page",
                        "summary": "Recovered after parse error.",
                        "tags": ["parse", "concept"],
                        "draft_body": "# Parse Retry Page\n\nRecovered body.",
                    }
                ]
            },
            "json_repair_applied": False,
            "http_response_size_bytes": 200,
            "api_key_present": True,
        }

    monkeypatch.setattr(wiki_ingest_llm, "call_json_task", fake_call_json_task)

    exit_code, payload = _invoke(["ingest", str(samples_dir / "short-note.md"), "--llm"], workspace)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["llm_page_candidate_attempt"]["status"] == "retried"
    assert payload["llm_page_candidate_attempt"]["retry_reason"] == "parse_failed"
    assert len(calls) == 2
    assert "raw response" in calls[1]["user_prompt"].lower()
    assert '{"candidates": [{"title": "Broken"' in calls[1]["user_prompt"]
    assert "LLM response JSON object is not balanced" in calls[1]["user_prompt"]
    page_text = (workspace / payload["wiki_pages"][0]["path"]).read_text(encoding="utf-8")
    assert "# Parse Retry Page" in page_text


def test_wiki_ingest_llm_valid_first_response_does_not_retry(monkeypatch, workspace: Path, samples_dir: Path) -> None:
    from llm_wiki.pipeline import wiki_ingest_llm

    _invoke(["init"], workspace)
    calls: list[dict[str, str]] = []

    def fake_call_json_task(workspace_arg, *, model_id: str, system_prompt: str, user_prompt: str, max_tokens=None):
        calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return {
            "content": json.dumps(
                {
                    "candidates": [
                        {
                            "title": "First Pass Page",
                            "summary": "A valid first-pass candidate.",
                            "tags": ["first", "concept"],
                            "draft_body": "# First Pass Page\n\nValid body.",
                        }
                    ]
                }
            ),
            "parsed_json": {
                "candidates": [
                    {
                        "title": "First Pass Page",
                        "summary": "A valid first-pass candidate.",
                        "tags": ["first", "concept"],
                        "draft_body": "# First Pass Page\n\nValid body.",
                    }
                ]
            },
            "json_repair_applied": False,
            "http_response_size_bytes": 160,
            "api_key_present": True,
        }

    monkeypatch.setattr(wiki_ingest_llm, "call_json_task", fake_call_json_task)

    exit_code, payload = _invoke(["ingest", str(samples_dir / "short-note.md"), "--llm"], workspace)

    assert exit_code == 0
    assert payload["llm_page_candidate_attempt"]["status"] == "parsed"
    assert payload["llm_page_candidate_attempt"]["retry_reason"] is None
    assert len(calls) == 1
    page_text = (workspace / payload["wiki_pages"][0]["path"]).read_text(encoding="utf-8")
    assert "# First Pass Page" in page_text


def test_wiki_ingest_llm_falls_back_after_retry_failure(monkeypatch, workspace: Path, samples_dir: Path) -> None:
    from llm_wiki.pipeline import wiki_ingest_llm

    _invoke(["init"], workspace)
    calls: list[dict[str, str]] = []

    def fake_call_json_task(workspace_arg, *, model_id: str, system_prompt: str, user_prompt: str, max_tokens=None):
        calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if len(calls) == 1:
            return {
                "content": json.dumps({"candidates": []}),
                "parsed_json": {"candidates": []},
                "json_repair_applied": False,
                "http_response_size_bytes": 50,
                "api_key_present": True,
            }
        raise RuntimeError("retry LLM unavailable")

    monkeypatch.setattr(wiki_ingest_llm, "call_json_task", fake_call_json_task)

    exit_code, payload = _invoke(["ingest", str(samples_dir / "short-note.md"), "--llm"], workspace)

    assert exit_code == 0
    attempt = payload["llm_page_candidate_attempt"]
    assert attempt["status"] == "fallback"
    assert attempt["fallback_used"] is True
    assert attempt["retry_reason"] == "schema_validation_failed"
    assert len(calls) == 2
    assert payload["page_count"] >= 1
    page_text = (workspace / payload["wiki_pages"][0]["path"]).read_text(encoding="utf-8")
    assert "# Knowledge Pipeline" in page_text
