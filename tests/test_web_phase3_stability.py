from __future__ import annotations

import os
from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.config.settings import load_settings, save_settings
from llm_wiki.llm.models import effective_concurrency_for_provider
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
    client = TestClient(create_app(workspace), raise_server_exceptions=False)
    client.post("/login", data={"password": "admin-pass"})
    return client, paths


def test_unauthenticated_api_returns_401_not_redirect(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = TestClient(create_app(workspace), raise_server_exceptions=False)

    response = client.get("/api/dashboard/metrics", follow_redirects=False)

    assert response.status_code == 401
    assert response.headers.get("location") is None
    assert response.json()["detail"] == "Authentication required"


def test_setup_fs_browse_rejects_hidden_paths_and_hidden_symlink_targets(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    visible_dir = home_dir / "browse-visible"
    visible_dir.mkdir()
    hidden_dir = home_dir / ".hidden-target"
    hidden_dir.mkdir()
    if hasattr(os, "symlink"):
        (visible_dir / "linked-hidden").symlink_to(hidden_dir, target_is_directory=True)

    hidden_response = client.get("/api/setup/fs/browse", params={"path": ".hidden-target"})
    assert hidden_response.status_code == 422

    visible_response = client.get("/api/setup/fs/browse", params={"path": "~/browse-visible"})
    assert visible_response.status_code == 200
    assert {entry["name"] for entry in visible_response.json()["entries"]} == set()


def test_wiki_graph_known_concept_without_edges_still_returns_center_node(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, paths = _client(workspace, monkeypatch)
    (paths.wiki_concepts / "solo.md").write_text("# Solo\n\nKnown concept with no relations.\n", encoding="utf-8")

    response = client.get("/api/wiki/pages/solo/graph")

    assert response.status_code == 200
    payload = response.json()["graph"]
    assert payload["nodes"] == [{"id": "solo", "label": "Solo", "kind": "concept"}]
    assert payload["edges"] == []


def test_vault_tree_skips_symlink_cycles(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, paths = _client(workspace, monkeypatch)
    target = paths.vault / "cycle-root"
    target.mkdir()
    if not hasattr(os, "symlink"):
        pytest.skip("symlink not supported on this platform")
    try:
        (target / "loop").symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not available: {exc}")

    response = client.get("/api/vault/tree")

    assert response.status_code == 200
    tree = response.json()["tree"]
    cycle_node = next(child for child in tree["children"] if child["name"] == "cycle-root")
    assert cycle_node["children"] == []


def test_permission_denied_directory_returns_403_for_browse_and_vault_folder(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home_dir = _set_fake_home(workspace, monkeypatch)
    client, paths = _client(workspace, monkeypatch)
    blocked_workspace_dir = home_dir / "blocked-browse"
    blocked_workspace_dir.mkdir()
    blocked_vault_dir = paths.vault / "blocked-vault"
    blocked_vault_dir.mkdir()

    from llm_wiki import fs_helpers

    original_listdir = fs_helpers.os.listdir

    def deny_selected(path: str | os.PathLike[str]):
        resolved = Path(path).resolve()
        if resolved in {blocked_workspace_dir.resolve(), blocked_vault_dir.resolve()}:
            raise PermissionError("denied for test")
        return original_listdir(path)

    monkeypatch.setattr(fs_helpers.os, "listdir", deny_selected)

    browse_response = client.get("/api/setup/fs/browse", params={"path": "~/blocked-browse"})
    vault_response = client.get("/api/vault/folder", params={"path": "blocked-vault"})

    assert browse_response.status_code == 403
    assert vault_response.status_code == 403


def test_effective_concurrency_reads_web_saved_llm_concurrency(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client(workspace, monkeypatch)
    paths = resolve_workspace(workspace)
    settings = load_settings(paths.settings_file, resolve_env=False)
    settings.setdefault("llm", {})["concurrency"] = 2
    settings["llm"].pop("max_concurrent_requests", None)
    save_settings(paths.settings_file, settings)

    assert effective_concurrency_for_provider(paths, "any-provider") == 2


def test_app_js_contains_stability_guards() -> None:
    script = (Path(__file__).resolve().parents[1] / "src/llm_wiki/web/static/js/app.js").read_text(encoding="utf-8")

    assert 'res.redirected && responsePath === "/login"' in script
    assert 'API returned HTML instead of JSON' in script
    assert 'if (!edges.length)' in script
    assert 'saveConcurrencyBtn.onclick = async () => {' in script


def test_setup_fs_browse_hides_dot_prefixed_and_symlinks(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-3-NO-12: browse endpoint must hide dot-prefixed entries and reject symlinks."""
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app
    home_dir = _set_fake_home(workspace, monkeypatch)
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    (home_dir / ".hidden_dir").mkdir()
    (home_dir / ".hidden_dir" / "inside.md").write_text("# Hidden", encoding="utf-8")
    (home_dir / "normal").mkdir()
    (home_dir / "normal" / "visible.md").write_text("# Visible", encoding="utf-8")
    (home_dir / "evil_link").symlink_to("/etc/passwd")
    (home_dir / "cycle").symlink_to("cycle")
    client = TestClient(create_app(workspace))
    client.post("/login", data={"password": "admin-pass"})
    r = client.get("/api/setup/fs/browse")
    assert r.status_code == 200
    names = [entry["name"] for entry in r.json()["entries"]]
    assert ".hidden_dir" not in names
    assert "normal" in names
    assert "evil_link" not in names
    assert "cycle" not in names


def test_vault_search_hides_dot_prefixed_files(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-3-NO-12: vault search must not enumerate dot-prefixed files."""
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    root = workspace
    vault_dir = root / "vault"
    vault_dir.mkdir(exist_ok=True)
    (vault_dir / ".secret.md").write_text("# Secret keyword", encoding="utf-8")
    (vault_dir / "public.md").write_text("# Public keyword", encoding="utf-8")
    client = TestClient(create_app(root))
    client.post("/login", data={"password": "admin-pass"})
    r = client.get("/api/vault/search?q=secret")
    assert r.status_code == 200
    assert all(".secret" not in row["path"] for row in r.json()["results"])
    r = client.get("/api/vault/search?q=public")
    assert r.status_code == 200
    paths = [row["path"] for row in r.json()["results"]]
    assert "public.md" in paths
    assert ".secret.md" not in paths


def test_inbox_upload_accepts_single_file_field_only(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-3-NO-02: backend accepts only multipart field 'file'; .txt and missing field return 422."""
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = TestClient(create_app(workspace), raise_server_exceptions=False)
    client.post("/login", data={"password": "admin-pass"})
    # valid .md
    r = client.post("/api/inbox/upload", files={"file": ("note.md", b"# Note", "text/markdown")})
    assert r.status_code == 200
    assert r.json()["field_name"] == "file"
    # missing field
    r = client.post("/api/inbox/upload", files={"other": ("x.md", b"# x", "text/markdown")})
    assert r.status_code == 422
    # legacy 'files' field rejected
    r = client.post("/api/inbox/upload", files={"files": ("x.md", b"# x", "text/markdown")})
    assert r.status_code == 422
    # .txt rejected
    r = client.post("/api/inbox/upload", files={"file": ("note.txt", b"plain text", "text/plain")})
    assert r.status_code == 422


def test_inbox_upload_cleans_temp_files_on_non_markdown_error(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-3-NO-02: temp files written to inbox/files MUST be removed on any failure.

    The previous fix only cleaned up on UnsupportedInputError. This test forces
    a non-UnsupportedInputError failure during ingest_markdown_file and verifies
    that the temp files do not leak into the inbox folder.
    """
    from fastapi.testclient import TestClient
    import llm_wiki.web.app as web_app
    from llm_wiki.web.app import create_app

    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = TestClient(create_app(workspace), raise_server_exceptions=False)
    client.post("/login", data={"password": "admin-pass"})

    # Snapshot inbox_files before upload.
    before = set((workspace / "00_Inbox" / "files").glob("*")) if (workspace / "00_Inbox" / "files").exists() else set()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated DB / IO failure")

    monkeypatch.setattr(web_app, "ingest_markdown_file", boom)

    r = client.post(
        "/api/inbox/upload",
        files={"file": ("boom.md", b"# Boom", "text/markdown")},
    )
    assert r.status_code == 500

    # Temp files written before the failure must be cleaned up.
    after = set((workspace / "00_Inbox" / "files").glob("*")) if (workspace / "00_Inbox" / "files").exists() else set()
    leaked = after - before
    assert not leaked, f"Temp files leaked on non-UnsupportedInputError failure: {leaked}"
