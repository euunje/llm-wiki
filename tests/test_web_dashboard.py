from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.config.settings import load_settings, save_settings
from llm_wiki.db.schema import connect
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def _set_fake_home(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home_dir = workspace.parent / f"{workspace.name}-home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    return home_dir


def test_dashboard_metrics_report_db_and_workspace_status(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nGrounded generation.\n", encoding="utf-8")

    conn = connect(paths.db)
    try:
        now = utc_now()
        conn.execute(
            "INSERT INTO sources (id, source_type, title, origin, raw_path, normalized_path, content_hash, pipeline_stage, review_status, metadata_json, created_at, updated_at) VALUES (?, 'user_text', 'Source A', NULL, NULL, NULL, 'hash-a', 'created', 'pending', '{}', ?, ?)",
            (new_id("source"), now, now),
        )
        conn.execute(
            "INSERT INTO jobs (id, job_type, target_type, target_id, status, input_refs_json, output_refs_json, error_json, retry_count, created_at, started_at, finished_at) VALUES (?, 'extract_claims', 'source', 'source_x', 'queued', '[]', '[]', NULL, 0, ?, NULL, NULL)",
            (new_id("job"), now),
        )
        conn.execute(
            "INSERT INTO jobs (id, job_type, target_type, target_id, status, input_refs_json, output_refs_json, error_json, retry_count, created_at, started_at, finished_at) VALUES (?, 'extract_claims', 'source', 'source_y', 'failed', '[]', '[]', '{\"reason\":\"boom\"}', 0, ?, NULL, ?)",
            (new_id("job"), now, now),
        )
        conn.execute(
            "INSERT INTO review_candidates (id, candidate_type, candidate_key, source_id, run_id, payload_json, review_route, review_reason, related_candidate_keys_json, status, superseded_by, created_at, updated_at) VALUES (?, 'node', 'node_01', 'source_x', NULL, '{}', 'normal_review', '', '[]', 'pending', NULL, ?, ?)",
            (new_id("candidate"), now, now),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_pending"] == 1
    assert payload["pending_jobs"] == 1
    assert payload["errors"] == 1
    assert payload["wiki_count"] == 1
    assert payload["db_status"]["exists"] is True
    assert payload["system_status"]["auth"]["configured"] is True

    setup = client.get("/api/setup/status")
    assert setup.status_code == 200
    assert setup.json()["workspace_initialized"] is True
    assert setup.json()["counts"]["sources"] == 1

    sources = client.get("/api/dashboard/sources")
    assert sources.status_code == 200
    assert sources.json()["stage_counts"]["created"] == 1

    jobs = client.get("/api/dashboard/jobs")
    assert jobs.status_code == 200
    assert jobs.json()["status_counts"]["queued"] == 1
    assert jobs.json()["status_counts"]["failed"] == 1

    errors = client.get("/api/dashboard/errors")
    assert errors.status_code == 200
    assert errors.json()["count"] == 1
    assert "boom" in str(errors.json()["errors"][0]["error_summary"])

    review = client.get("/api/dashboard/review")
    assert review.status_code == 200
    assert review.json()["pending_by_candidate_type"]["node"] == 1

    wiki = client.get("/api/dashboard/wiki")
    assert wiki.status_code == 200
    assert wiki.json()["concept_count"] == 1


def test_dashboard_summary_uses_configured_home_vault(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    human_vault = home_dir / "vault"
    for folder in [
        human_vault / "00. Inbox",
        human_vault / "20. Wiki",
        human_vault / "30. Queries",
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    settings = load_settings(paths.settings_file, resolve_env=False)
    settings["workspace"] = {"human_vault": "~/vault", "system_data": "data"}
    settings.setdefault("paths", {})["vault"] = "~/vault"
    settings["vault"] = {"vault_path": "~/vault", "role_map": {"queries": "~/vault/30. Queries"}}
    save_settings(paths.settings_file, settings)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["vault"]["path"] == str(human_vault)
    assert payload["vault"]["root_folder_count"] == 3
    assert payload["system"]["vault_path"] == str(human_vault)
