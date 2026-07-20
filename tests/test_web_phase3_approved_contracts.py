"""Focused contracts for the user-approved revised Phase 3 Web UI and APIs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.common import new_id, utc_now
from llm_wiki.db.schema import connect
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import resolve_workspace


API_KEY_VALUE = "phase3-secret-value-never-expose"


def _client(workspace: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setenv("LLM_WIKI_API_KEY", API_KEY_VALUE)
    paths = resolve_workspace(workspace)
    ensure_workspace(paths)
    client = TestClient(create_app(workspace))
    login = client.post("/login", data={"password": "admin-pass"})
    assert login.status_code == 200
    return client, paths


def _complete_setup(client, paths) -> None:
    cfg = client.post(
        "/api/settings/llm/config",
        json={
            "endpoint": "https://llm.example.test/v1",
            "api_key_env": "LLM_WIKI_API_KEY",
            "chat_model_name": "phase3-chat-model",
            "embedding_model_name": "phase3-embedding-model",
        },
    )
    assert cfg.status_code == 200
    for model_id in ("chat_default", "embedding_default"):
        record_artifact(
            paths,
            artifact_type="model_test_report",
            task_type="model_test",
            payload={"status": "ok", "result": "ok", "test_status": "passed", "reason": None, "model_id": model_id},
            target_type="model",
            target_id=model_id,
            metadata={"status": "ok", "result": "ok", "test_status": "passed", "reason": None, "model_id": model_id},
        )


def _insert_candidate(
    db_path: Path,
    *,
    candidate_key: str,
    payload: dict[str, Any],
    review_route: str = "normal_review",
) -> str:
    candidate_id = new_id("candidate")
    now = utc_now()
    conn = connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO review_candidates (
              id, candidate_type, candidate_key, source_id, run_id, payload_json,
              review_route, review_reason, related_candidate_keys_json, status,
              superseded_by, created_at, updated_at
            ) VALUES (?, 'mapping', ?, NULL, NULL, ?, ?, 'Phase 3 approved contract test',
                      '[]', 'pending', NULL, ?, ?)
            """,
            (
                candidate_id,
                candidate_key,
                json.dumps(payload, ensure_ascii=False),
                review_route,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return candidate_id


def test_approved_top_navigation_is_exact_and_ordered(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/dashboard")
    assert response.status_code == 200
    match = re.search(r'<nav[^>]+id="main-nav"[^>]*>(.*?)</nav>', response.text, re.DOTALL)
    assert match is not None
    nav = match.group(1)

    expected_labels = [
        "Dashboard",
        "Inbox",
        "Mapping",
        "Vault",
        "Wiki",
        "Settings",
    ]
    assert re.findall(r'aria-label="([^"]+)"', nav) == expected_labels
    for path in ("/dashboard", "/inbox", "/mapping", "/vault", "/wiki", "/settings"):
        assert re.search(rf'href="(?:http://testserver)?{re.escape(path)}"', nav)
    assert "/logout" not in nav
    assert "Review / Mapping" not in nav
    assert "Error" not in nav

    utility_match = re.search(
        r'<a[^>]+class="[^"]*utility-link[^"]*"[^>]+href="(?:http://testserver)?/search"[^>]+aria-label="Search / Ask"[^>]*>\s*🔍 Search / Ask\s*</a>',
        response.text,
    )
    assert utility_match is not None
    assert response.text.index('<nav class="pc-nav" role="navigation" aria-label="Main navigation" id="main-nav">') < response.text.index("utility-link")


@pytest.mark.parametrize(
    ("route", "landmarks"),
    [
        ("/dashboard", ('id="dashboard-metrics"', 'id="dashboard-attention"', 'id="dashboard-system"', 'id="dashboard-activity"')),
        ("/inbox", ('id="inbox-item-list"', 'id="inbox-detail"', 'id="inbox-queue"', 'id="btn-inbox-process"')),
        ("/mapping", ('class="mapping-stepbar"', 'id="mapping-candidate-queue"', 'id="mapping-pane-1"', 'id="mapping-pane-2"', 'id="mapping-pane-3"', 'id="mapping-pane-errors"', 'id="btn-mapping-confirm"')),
        ("/vault", ('id="vault-folder-tree"', 'id="vault-file-list"', 'id="vault-viewer"')),
        ("/wiki", ('id="wiki-page-list"', 'id="wiki-detail"', 'id="wiki-toc-drawer"')),
        ("/settings?tab=llm", ('class="settings-tab active" data-tab="llm"', 'id="settings-pane-llm"', 'id="settings-advanced-options"', 'id="settings-concurrency"')),
        ("/settings?tab=prompt", ('class="settings-tab active" data-tab="prompt"', 'id="settings-pane-prompt"', 'id="settings-prompt-top-tabs"', 'id="settings-prompt-workspace"')),
        ("/onboarding", ('class="wizard-rail"', 'data-step="provider"', 'data-step="test"', 'data-step="models"', 'data-step="vault"', 'data-step="pipeline"', 'data-step="finish"', 'id="setup-checklist"')),
    ],
)
def test_approved_page_routes_render_landmarks(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    landmarks: tuple[str, ...],
) -> None:
    client, paths = _client(workspace, monkeypatch)
    if not route.startswith("/onboarding") and not route.startswith("/settings"):
        _complete_setup(client, paths)

    response = client.get(route)
    assert response.status_code == 200
    for landmark in landmarks:
        assert landmark in response.text, f"{route} missing approved landmark: {landmark}"


def test_dashboard_summary_exposes_approved_card_groups(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    _complete_setup(client, paths)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert {"inbox", "mapping", "wiki", "vault", "issues", "system"} <= set(payload)
    assert {"new", "processing", "failed", "needs_mapping", "completed", "total"} <= set(payload["inbox"])
    assert {"new", "in_review", "errors"} <= set(payload["mapping"])
    assert {"concept_count", "page_count", "recently_updated"} <= set(payload["wiki"])
    assert {"ready", "root_folder_count", "path"} <= set(payload["vault"])
    assert {"count", "failed_jobs", "retry_needed"} <= set(payload["issues"])


def test_inbox_text_upload_scan_process_retry_log_and_result_record_contracts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths = _client(workspace, monkeypatch)

    text_response = client.post(
        "/api/inbox/text",
        json={
            "title": "Phase 3 direct text",
            "text": "A focused Inbox API contract source.",
            "tags": ["phase3"],
            "source_note": "web-test",
        },
    )
    assert text_response.status_code == 200
    text_payload = text_response.json()
    assert text_payload["status"] == "ok"
    item_id = text_payload["item"]["source_id"]

    upload_response = client.post(
        "/api/inbox/upload",
        files={"file": ("phase3-upload.md", b"# Uploaded\n\nInbox upload contract.\n", "text/markdown")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["item"]["source_id"]

    items_response = client.get("/api/inbox/items")
    assert items_response.status_code == 200
    items = items_response.json()["items"]
    text_item = next(item for item in items if item["id"] == item_id)
    assert text_item["status"] == "new"
    assert text_item["kind"] == "text"
    assert text_item["available_actions"]["process"] is True

    detail_response = client.get(f"/api/inbox/items/{item_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["item"]
    assert detail["id"] == item_id
    assert "focused Inbox API contract source" in detail["preview"]
    assert detail["processing_log"][0]["event"] == "source registered"

    scan_response = client.post("/api/inbox/scan")
    assert scan_response.status_code == 200
    scan = scan_response.json()
    assert scan["status"] == "ok"
    assert {"new_candidate_count", "duplicate_count", "skipped_count", "scanned_paths"} <= set(scan)

    process_response = client.post("/api/inbox/process", json={"item_ids": [item_id]})
    assert process_response.status_code == 200
    process = process_response.json()
    assert process["execution_mode"] == "synchronous"
    assert process["acceptance_status"] == "processed"
    assert process["processed_count"] == 1
    if "queued_count" in process:
        assert process["queued_count"] == process["processed_count"]
    assert process["items"][0]["item_id"] == item_id
    assert process["items"][0]["status"] == "ok"
    assert process["items"][0]["final_state"] in {"needs_mapping", "completed"}

    retry_response = client.post(
        f"/api/inbox/items/{item_id}/retry",
        json={"note": "Retry from focused contract test"},
    )
    assert retry_response.status_code == 200
    retry_payload = retry_response.json()
    assert retry_payload["execution_mode"] == "synchronous"
    assert retry_payload["acceptance_status"] == "processed"
    assert retry_payload["processed_count"] == 1
    if "queued_count" in retry_payload:
        assert retry_payload["queued_count"] == retry_payload["processed_count"]
    assert retry_payload["note"] == "Retry from focused contract test"

    status_response = client.get("/api/inbox/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["needs_mapping_count"] >= 1 or status_payload["counts"].get("completed", 0) >= 1

    log_response = client.get(f"/api/inbox/items/{item_id}/log")
    assert log_response.status_code == 200
    log_payload = log_response.json()
    assert log_payload["count"] >= 3
    assert any(event["event"] in {"running", "succeeded", "failed"} for event in log_payload["events"])

    record_response = client.get(f"/api/inbox/items/{item_id}/result-record")
    assert record_response.status_code == 200
    record = record_response.json()["record"]
    assert record["source"]["id"] == item_id
    assert record["source"]["final_state"] in {"needs_mapping", "completed", "failed"}
    assert {"generated_candidates_count", "decisions_count", "approved_count", "retry_count"} <= set(record["results"])
    artifact_types = {artifact["artifact_type"] for artifact in record["artifacts"]}
    assert "ingest_text_report" in artifact_types
    assert "inbox_process_request" in artifact_types


def test_vault_tree_folder_file_and_path_safety_contracts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    document = paths.wiki_concepts / "phase3-vault.md"
    document.write_text(
        "---\ntags: [phase3]\n---\n# Vault Contract\n\nRead-only Markdown body.\n",
        encoding="utf-8",
    )
    hidden_dir = paths.vault / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.md").write_text("must stay hidden", encoding="utf-8")

    tree_response = client.get("/api/vault/tree")
    assert tree_response.status_code == 200
    tree_payload = tree_response.json()
    assert tree_payload["tree"]["kind"] == "folder"
    assert ".hidden" not in json.dumps(tree_payload, ensure_ascii=False)

    folder_response = client.get("/api/vault/folder", params={"path": "10_Wiki/concepts"})
    assert folder_response.status_code == 200
    folder = folder_response.json()
    assert folder["path"] == "10_Wiki/concepts"
    assert any(item["name"] == "phase3-vault.md" for item in folder["files"])

    file_response = client.get("/api/vault/file", params={"path": "10_Wiki/concepts/phase3-vault.md"})
    assert file_response.status_code == 200
    file_payload = file_response.json()["file"]
    assert file_payload["preview_type"] == "markdown"
    assert file_payload["read_only"] is True
    assert file_payload["metadata"]["tags"] == "[phase3]"
    assert file_payload["content"].startswith("# Vault Contract")
    assert not file_payload["content"].startswith("---")

    assert client.get("/api/vault/file", params={"path": "../settings.yaml"}).status_code == 422
    assert client.get("/api/vault/file", params={"path": str(document)}).status_code == 422
    assert client.get("/api/vault/file", params={"path": ".hidden/secret.md"}).status_code == 404


def test_setup_fs_browse_contracts_hide_dotfiles_and_block_unsafe_paths(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = workspace.parent / f"{workspace.name}-home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    client, paths = _client(workspace, monkeypatch)
    visible_dir = home_dir / "browse-visible"
    visible_dir.mkdir()
    (home_dir / "vault").mkdir()
    (visible_dir / "child").mkdir()
    (visible_dir / ".secret-folder").mkdir()
    (home_dir / ".env").write_text('SHOULD_NOT_BE_LISTED="x"\n', encoding="utf-8")

    root_response = client.get("/api/setup/fs/browse")
    assert root_response.status_code == 200
    root_payload = root_response.json()
    assert root_payload["status"] == "ok"
    assert root_payload["path"] == "~"
    assert root_payload["root"] == "~"
    assert root_payload["can_go_parent"] is False
    assert root_payload["parent_path"] is None
    names = {entry["name"] for entry in root_payload["entries"]}
    assert "browse-visible" in names
    assert "vault" in names
    assert ".env" not in names

    child_response = client.get("/api/setup/fs/browse", params={"path": "~/browse-visible"})
    assert child_response.status_code == 200
    child_payload = child_response.json()
    assert child_payload["path"] == "~/browse-visible"
    assert child_payload["can_go_parent"] is True
    assert child_payload["parent_path"] == "~"
    assert child_payload["entries"] == [
        {
            "name": "child",
            "path": "~/browse-visible/child",
            "is_dir": True,
            "kind": "folder",
        }
    ]

    assert client.get("/api/setup/fs/browse", params={"path": "../etc"}).status_code == 422
    assert client.get("/api/setup/fs/browse", params={"path": str(paths.root)}).status_code == 422
    assert client.get("/api/setup/fs/browse", params={"path": str(home_dir.parent)}).status_code == 422
    assert client.get("/api/setup/fs/browse", params={"path": "~/.ssh"}).status_code == 422


def test_mapping_candidates_matches_decide_and_retry_contracts(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nRetrieval-Augmented Generation.\n", encoding="utf-8")
    decision_candidate_id = _insert_candidate(
        paths.db,
        candidate_key="phase3_mapping_decide",
        payload={
            "candidate_key": "phase3_mapping_decide",
            "title": "RAG",
            "summary": "Candidate overlaps the existing RAG concept.",
            "current_step": "relationship_validate",
            "existing_node_id": "rag",
        },
    )
    retry_candidate_id = _insert_candidate(
        paths.db,
        candidate_key="phase3_mapping_retry",
        payload={
            "candidate_key": "phase3_mapping_retry",
            "title": "Agentic RAG",
            "summary": "Candidate needs a narrower retry.",
            "current_step": "errors",
        },
        review_route="needs_retry",
    )

    candidates_response = client.get("/api/mapping/candidates")
    assert candidates_response.status_code == 200
    candidates_payload = candidates_response.json()
    assert candidates_payload["count"] == 2
    assert candidates_payload["new_count"] == 2
    candidate = next(item for item in candidates_payload["candidates"] if item["id"] == decision_candidate_id)
    assert [step["id"] for step in candidate["steps"]] == [
        "page_validate",
        "page_mapping",
        "relationship_validate",
        "errors",
    ]

    detail_response = client.get(f"/api/mapping/candidates/{decision_candidate_id}")
    assert detail_response.status_code == 200
    wizard = detail_response.json()["candidate"]["wizard"]
    assert wizard["current_step"] == "relationship_validate"
    assert wizard["steps"][0]["actions"] == ["reject", "edit", "next"]
    assert wizard["steps"][2]["actions"] == ["reject", "edit", "confirm"]

    matches_response = client.get(
        "/api/mapping/wiki-matches",
        params={"candidate_id": decision_candidate_id},
    )
    assert matches_response.status_code == 200
    assert any(match["concept_id"] == "rag" for match in matches_response.json()["matches"])

    preview_response = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": decision_candidate_id,
            "action": "merge",
            "note": "Preview merge after Relationship validation",
            "metadata": {"step": "page_mapping", "target_concept_id": "rag"},
        },
    )
    assert preview_response.status_code == 200
    preview_decision_id = preview_response.json()["decision_id"]

    decide_response = client.post(
        "/api/mapping/decide",
        json={
            "candidate_id": decision_candidate_id,
            "action": "merge",
            "note": "Confirmed after Relationship validation",
            "metadata": {
                "step": "relationship_validate",
                "target_concept_id": "rag",
                "preview_decision_id": preview_decision_id,
            },
        },
    )
    assert decide_response.status_code == 200
    assert decide_response.json()["action"] == "merge"
    assert decide_response.json()["effect"]["target_concept_id"] == "rag"

    invalid_retry = client.post(
        f"/api/mapping/candidates/{retry_candidate_id}/retry",
        json={"reason": "Too broad", "instruction": ""},
    )
    assert invalid_retry.status_code == 422

    retry_response = client.post(
        f"/api/mapping/candidates/{retry_candidate_id}/retry",
        json={
            "reason": "Too broad",
            "instruction": "Separate Agentic RAG from baseline RAG.",
            "metadata": {"step": "errors"},
        },
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["retry_instruction_id"]

    conn = connect(paths.db)
    try:
        decided_status = conn.execute(
            "SELECT status FROM review_candidates WHERE id = ?",
            (decision_candidate_id,),
        ).fetchone()["status"]
        retry_status = conn.execute(
            "SELECT status FROM review_candidates WHERE id = ?",
            (retry_candidate_id,),
        ).fetchone()["status"]
        retry_instruction = conn.execute(
            "SELECT reason, instruction FROM retry_instructions WHERE target_candidate_id = ?",
            (retry_candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    assert decided_status == "approved"
    assert retry_status == "retry_requested"
    assert retry_instruction["reason"] == "Too broad"
    assert retry_instruction["instruction"] == "Separate Agentic RAG from baseline RAG."


def test_wiki_page_graph_route_returns_nodes_edges_and_404_for_unknown_concept(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "rag.md").write_text("# RAG\n\nRetrieval-Augmented Generation.\n", encoding="utf-8")
    _insert_candidate(
        paths.db,
        candidate_key="phase3_graph_candidate",
        payload={
            "candidate_key": "phase3_graph_candidate",
            "title": "Retriever note",
            "existing_node_id": "rag",
            "incoming_ref": {"candidate_key": "phase3_graph_related"},
            "mapping_action": "supports",
        },
    )

    response = client.get("/api/wiki/pages/rag/graph")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert {"nodes", "edges"} <= set(payload["graph"])
    assert any(node["id"] == "rag" for node in payload["graph"]["nodes"])
    assert any(edge == {"source": "phase3_graph_related", "target": "rag", "label": "supports"} for edge in payload["graph"]["edges"])

    unknown = client.get("/api/wiki/pages/unknown-concept/graph")
    assert unknown.status_code == 404


def test_prompt_active_and_rollback_create_a_new_confirmed_copy(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)

    active_before_response = client.get(
        "/api/settings/prompts/active",
        params={"task_type": "map"},
    )
    assert active_before_response.status_code == 200
    active_before = active_before_response.json()
    source_version = active_before["active"]
    assert source_version["state"] == "confirmed"
    assert source_version["version_label"] == "phase2-default-v1"
    assert active_before["default"]["is_phase2_default"] is True

    custom_response = client.post(
        "/api/settings/prompts/test",
        json={
            "task_type": "map",
            "version_label": "phase3-custom-map-v1",
            "prompt_text": (
                "Return JSON mapping candidate output for map tasks with candidate, "
                "existing_node_id, mapping decisions, and JSON structure."
            ),
            "change_note": "Make custom prompt active before rollback",
        },
    )
    assert custom_response.status_code == 200
    assert custom_response.json()["test_status"] == "passed"
    custom_id = custom_response.json()["prompt_id"]
    confirm_response = client.post(f"/api/settings/prompts/{custom_id}/confirm")
    assert confirm_response.status_code == 200

    rollback_response = client.post(
        f"/api/settings/prompts/{source_version['id']}/rollback",
        json={"reason": "Restore the approved Phase 2 default", "created_by": "phase3-test"},
    )
    assert rollback_response.status_code == 200
    rollback = rollback_response.json()
    new_version_id = rollback["new_version_id"]
    assert new_version_id not in {source_version["id"], custom_id}
    assert rollback["source_version_id"] == source_version["id"]
    assert rollback["archived_version_id"] == custom_id

    active_after_response = client.get(
        "/api/settings/prompts/active",
        params={"task_type": "map"},
    )
    assert active_after_response.status_code == 200
    active_after = active_after_response.json()
    assert active_after["active"]["id"] == new_version_id
    assert active_after["active"]["state"] == "confirmed"
    assert active_after["default"]["is_rollback_restored"] is True
    assert active_after["default"]["visible"] is True

    conn = connect(paths.db)
    try:
        rows = {
            row["id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM prompt_versions WHERE id IN (?, ?, ?)",
                (source_version["id"], custom_id, new_version_id),
            ).fetchall()
        }
    finally:
        conn.close()
    assert rows[source_version["id"]]["state"] == "archived"
    assert rows[custom_id]["state"] == "archived"
    assert rows[new_version_id]["state"] == "confirmed"
    assert rows[new_version_id]["prompt_text"] == rows[source_version["id"]]["prompt_text"]
    assert f"rollback_from:{source_version['id']}" in rows[new_version_id]["change_note"]


def test_llm_concurrency_defaults_to_one_and_is_bounded_to_three(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths = _client(workspace, monkeypatch)

    initial_response = client.get("/api/settings/llm/concurrency")
    assert initial_response.status_code == 200
    assert initial_response.json() == {
        "status": "ok",
        "value": 1,
        "default": 1,
        "min": 1,
        "max": 3,
        "warning": None,
    }

    high_response = client.post("/api/settings/llm/concurrency", json={"value": 9})
    assert high_response.status_code == 200
    assert high_response.json()["value"] == 3
    assert high_response.json()["warning"]

    low_response = client.post("/api/settings/llm/concurrency", json={"value": 0})
    assert low_response.status_code == 200
    assert low_response.json()["value"] == 1
    assert low_response.json()["warning"] is None


def test_settings_status_and_config_responses_never_expose_api_key_values(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths = _client(workspace, monkeypatch)

    responses = [
        client.get("/api/setup/status"),
        client.get("/api/settings/models"),
        client.get("/api/settings/llm/status"),
        client.post(
            "/api/settings/llm/config",
            json={
                "endpoint": "https://llm.example.test/v1",
                "api_key_env": "LLM_WIKI_API_KEY",
                "default_chat_model": "chat_default",
                "default_embedding_model": "embedding_default",
                "chat_model_name": "phase3-chat",
                "embedding_model_name": "phase3-embedding",
            },
        ),
    ]
    for response in responses:
        assert response.status_code == 200
        assert API_KEY_VALUE not in response.text

    setup = responses[0].json()
    assert setup["llm"]["api_key_configured"] is True

    models = responses[1].json()
    assert "api_key" not in models["settings"]

    status_payload = responses[2].json()
    assert status_payload["settings"]["api_key_env"] == "LLM_WIKI_API_KEY"
    assert "api_key" not in status_payload["settings"]
    assert status_payload["missing"]["api_key_missing"] is False

    config_payload = responses[3].json()
    assert config_payload["settings"]["api_key_env"] == "LLM_WIKI_API_KEY"
    assert "api_key" not in config_payload["settings"]


def test_llm_config_persists_api_key_to_workspace_env_without_exposing_secret(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)

    response = client.post(
        "/api/setup/llm",
        json={
            "endpoint": "https://llm.example.test/v1",
            "api_key_env": "PHASE3_WEB_KEY",
            "api_key": "phase3-web-only-secret",
            "default_chat_model": "chat_default",
            "default_embedding_model": "embedding_default",
            "chat_model_name": "phase3-chat",
            "embedding_model_name": "phase3-embedding",
        },
    )
    assert response.status_code == 200
    assert "phase3-web-only-secret" not in response.text

    env_text = paths.env_file.read_text(encoding="utf-8")
    assert 'PHASE3_WEB_KEY="phase3-web-only-secret"' in env_text
    assert "LLM_WIKI_API_KEY=" not in env_text

    status_payload = client.get("/api/settings/llm/status").json()
    assert status_payload["settings"]["api_key_env"] == "PHASE3_WEB_KEY"
    assert status_payload["missing"]["api_key_missing"] is False
    assert "phase3-web-only-secret" not in json.dumps(status_payload)


def test_reusable_app_js_avoids_localhost_literals_and_uses_supported_mapping_actions() -> None:
    script = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    assert "localhost" not in script
    assert "127.0.0.1" not in script
    assert "/api/mapping/candidates/${encodeURIComponent(id)}/retry" in script
    assert 'settingsLlmConcurrency: "/api/settings/llm/concurrency"' in script
    assert 'body: JSON.stringify({ value: val })' in script
    assert 'action = decision === "keep_new" ? "create_new" : decision === "defer" ? "edit" : decision' in script
    assert 'metadata = { step: "relationship_validate" }' in script


def test_inbox_detail_renders_result_record_via_separate_endpoint(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3-NO-09: inbox detail must surface result-record fields via the
    dedicated result-record endpoint, retry must accept JSON body, and
    process failures must propagate failed/blocked statuses.
    """
    client, paths = _client(workspace, monkeypatch)

    text_resp = client.post(
        "/api/inbox/text",
        json={"title": "Phase 3 retry result", "text": "Sample body for FR-3-NO-09 contract."},
    )
    assert text_resp.status_code == 200
    item_id = text_resp.json()["item"]["source_id"]

    process = client.post("/api/inbox/process", json={"item_ids": [item_id]})
    assert process.status_code == 200
    process_payload = process.json()
    assert {"status", "processed_count", "failed_count", "blocked_count", "items"} <= set(process_payload)

    # Retry with JSON body.
    retry = client.post(
        f"/api/inbox/items/{item_id}/retry",
        json={"note": "FR-3-NO-09 retry"},
    )
    assert retry.status_code == 200
    assert retry.json().get("note") == "FR-3-NO-09 retry"

    # Detail must expose preview/content/source_path/processing_log/error fields.
    detail = client.get(f"/api/inbox/items/{item_id}").json()["item"]
    assert "preview" in detail
    assert "content" in detail
    assert "source_path" in detail
    assert "processing_log" in detail
    assert "status" in detail

    # Result-record endpoint exists and returns nested fields.
    record = client.get(f"/api/inbox/items/{item_id}/result-record").json()
    assert record["status"] == "ok"
    assert "record" in record
    assert {"source", "model_run", "results", "artifacts"} <= set(record["record"])
