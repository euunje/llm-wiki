from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.workspace import resolve_workspace


def _client(workspace: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_wiki.web.app import create_app

    ensure_workspace(resolve_workspace(workspace))
    return TestClient(create_app(workspace))


def test_login_requires_configured_password(workspace: Path) -> None:
    client = _client(workspace)
    response = client.post("/login", data={"password": "anything"})
    assert response.status_code == 503
    assert "LLM_WIKI_WEB_ADMIN_PASSWORD" in response.text


def test_login_sets_signed_cookie_and_protects_dashboard(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = _client(workspace)

    protected = client.get("/dashboard", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/login"

    login = client.post("/login", data={"password": "admin-pass"}, follow_redirects=False)
    assert login.status_code == 303
    assert login.headers["location"] == "/onboarding"
    assert "llm_wiki_web_session" in login.cookies

    client.cookies.update(login.cookies)
    api = client.get("/api/dashboard/metrics")
    assert api.status_code == 200
    assert api.json()["status"] == "ok"


def test_authenticated_root_and_protected_pages_gate_to_onboarding_when_setup_incomplete(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = _client(workspace)
    login = client.post("/login", data={"password": "admin-pass"}, follow_redirects=False)
    client.cookies.update(login.cookies)

    root = client.get("/", follow_redirects=False)
    dashboard = client.get("/dashboard", follow_redirects=False)
    inbox = client.get("/inbox", follow_redirects=False)
    settings = client.get("/settings", follow_redirects=False)

    assert root.status_code == 303
    assert root.headers["location"] == "/onboarding"
    assert dashboard.status_code == 303
    assert dashboard.headers["location"] == "/onboarding"
    assert inbox.status_code == 303
    assert inbox.headers["location"] == "/onboarding"
    assert settings.status_code == 200


def test_logout_clears_cookie(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = _client(workspace)
    client.post("/login", data={"password": "admin-pass"})

    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_authenticated_pages_keep_onboarding_accessible_while_setup_is_incomplete(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_WIKI_WEB_ADMIN_PASSWORD", "admin-pass")
    client = _client(workspace)
    client.post("/login", data={"password": "admin-pass"})

    onboarding = client.get("/onboarding")
    wiki = client.get("/wiki", follow_redirects=False)

    assert onboarding.status_code == 200
    assert "Onboarding" in onboarding.text
    assert wiki.status_code == 303
    assert wiki.headers["location"] == "/onboarding"
