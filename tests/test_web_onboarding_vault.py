from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.config.settings import load_settings, save_settings
from llm_wiki.workspace import resolve_workspace


def _set_fake_home(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home_dir = workspace.parent / f"{workspace.name}-home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    return home_dir


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


def test_detect_structure_finds_known_roles_and_rejects_unsafe_paths(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    home_vault = home_dir / "vault"
    for folder in [
        home_vault / "00_Inbox",
        home_vault / "10_Wiki",
        home_vault / "20_Review",
        home_vault / "30. Queries",
        home_vault / "90_Settings",
    ]:
        folder.mkdir(parents=True, exist_ok=True)
    client, paths = _client(workspace, monkeypatch)

    response = client.get("/api/setup/vault/detect-structure", params={"path": "~/vault"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["role_map"]["inbox"] == "~/vault/00_Inbox"
    assert payload["role_map"]["wiki"] == "~/vault/10_Wiki"
    assert payload["role_map"]["review"] == "~/vault/20_Review"
    assert payload["role_map"]["queries"] == "~/vault/30. Queries"
    assert payload["role_map"]["settings"] == "~/vault/90_Settings"
    root_response = client.get("/api/setup/vault/detect-structure", params={"path": "."})
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "ok"
    assert client.get("/api/setup/vault/detect-structure", params={"path": "../etc"}).status_code == 422
    hidden = home_dir / ".hidden-vault"
    hidden.mkdir()
    assert client.get("/api/setup/vault/detect-structure", params={"path": ".hidden-vault"}).status_code == 422
    assert client.get("/api/setup/vault/detect-structure", params={"path": str(paths.root / 'vault')}).status_code == 422


def test_create_vault_builds_standard_structure_and_updates_config(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    (home_dir / "vaults").mkdir()

    response = client.post("/api/setup/vault/create", json={"parent_path": "~/vaults", "vault_name": "project-a"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["parent_path"] == "~/vaults"
    assert payload["vault_path"] == "~/vaults/project-a"
    assert (home_dir / "vaults/project-a/00_Inbox/files").is_dir()
    assert (home_dir / "vaults/project-a/10_Wiki/concepts").is_dir()
    assert (home_dir / "vaults/project-a/30. Queries").is_dir()
    assert (home_dir / "vaults/project-a/90_Settings").is_dir()
    settings = load_settings(paths.settings_file, resolve_env=False)
    assert settings["paths"]["vault"] == "~/vaults/project-a"
    assert settings["vault"]["role_map"]["queries"] == "~/vaults/project-a/30. Queries"
    assert settings["vault"]["role_map"]["review"] == "~/vaults/project-a/20_Review"


def test_onboarding_existing_vault_ui_maps_core_roles_from_browser_and_keeps_wiki_subfolders_advanced(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _paths = _client(workspace, monkeypatch)

    response = client.get("/onboarding")
    assert response.status_code == 200
    body = response.text
    assert 'id="vault-browser-existing"' in body
    assert 'id="vault-wiki-advanced"' in body
    assert 'data-quick-assign-role="inbox"' in body
    assert 'data-quick-assign-role="raws"' in body
    assert 'data-quick-assign-role="wiki"' in body
    assert "Assign current folder" not in body
    assert "data-assign-current-label" in body
    assert "Wiki 세부 폴더명" in body
    assert 'id="wiki-subfolder-concepts"' in body
    assert 'id="wiki-subfolder-sources"' in body
    assert 'id="wiki-subfolder-claims"' in body
    assert 'id="wiki-subfolder-pages"' in body

    app_js = Path("src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")
    assert "quick-assign-role" in app_js
    assert "buildWikiSubfolderRoleMap" in app_js
    save_handler_start = app_js.index('btn-save-vault-mapping')
    save_handler = app_js[save_handler_start: app_js.index("// Initialize vault browsers", save_handler_start)]
    assert 'goToStep("pipeline")' not in save_handler


def test_mapping_saves_role_map_and_rejects_outside_paths(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    custom_vault = home_dir / "vault"
    for folder in [
        custom_vault / "00_Inbox",
        custom_vault / "10_Wiki",
        custom_vault / "20_Review",
        custom_vault / "30. Queries",
        custom_vault / "80_Raws",
        custom_vault / "90_Settings",
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    response = client.post(
        "/api/setup/vault/mapping",
        json={
            "vault_path": str(custom_vault),
            "role_map": {
                "inbox": "~/vault/00_Inbox",
                "wiki": "~/vault/10_Wiki",
                "review": "~/vault/20_Review",
                "queries": "~/vault/30. Queries",
                "raws": "~/vault/80_Raws",
                "settings": "~/vault/90_Settings",
                "concepts": "~/vault/10_Wiki/Knowledge",
                "sources": "~/vault/10_Wiki/References",
                "claims": "~/vault/10_Wiki/Claims",
                "pages": "~/vault/10_Wiki/Pages",
            },
        },
    )

    assert response.status_code == 200
    settings = load_settings(paths.settings_file, resolve_env=False)
    assert settings["paths"]["vault"] == "~/vault"
    assert settings["paths"]["data"] == "data"
    assert settings["paths"]["artifacts"] == "data/artifacts"
    assert settings["vault"]["role_map"]["wiki"] == "~/vault/10_Wiki"
    assert settings["vault"]["role_map"]["queries"] == "~/vault/30. Queries"
    assert settings["vault"]["role_map"]["concepts"] == "~/vault/10_Wiki/Knowledge"
    assert settings["vault"]["role_map"]["sources"] == "~/vault/10_Wiki/References"

    invalid = client.post(
        "/api/setup/vault/mapping",
        json={
            "vault_path": "~/vault",
            "role_map": {"wiki": "~/other"},
        },
    )
    assert invalid.status_code == 422
    invalid_wiki_subfolder = client.post(
        "/api/setup/vault/mapping",
        json={
            "vault_path": "~/vault",
            "role_map": {"wiki": "~/vault/10_Wiki", "concepts": "~/vault/80_Raws/concepts"},
        },
    )
    assert invalid_wiki_subfolder.status_code == 422


def test_operational_status_and_vault_tree_use_configured_home_vault(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    human_vault = home_dir / "vault"
    for folder in [
        human_vault / "00. Inbox",
        human_vault / "20. Wiki",
        human_vault / "30. Queries",
        human_vault / "90. Settings" / "LLM Wiki",
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    settings = load_settings(paths.settings_file, resolve_env=False)
    settings["workspace"] = {"human_vault": "~/vault", "system_data": "data"}
    settings.setdefault("paths", {})["vault"] = "~/vault"
    settings["vault"] = {
        "vault_path": "~/vault",
        "role_map": {
            "queries": "~/vault/30. Queries",
        },
    }
    save_settings(paths.settings_file, settings)

    status_response = client.get("/api/setup/status")
    assert status_response.status_code == 200
    assert status_response.json()["vault_path"] == str(human_vault)

    tree_response = client.get("/api/vault/tree")
    assert tree_response.status_code == 200
    children = {child["name"] for child in tree_response.json()["tree"]["children"]}
    assert {"00. Inbox", "20. Wiki", "30. Queries", "90. Settings"} <= children
