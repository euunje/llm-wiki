"""Regression tests for web navigation consistency."""

from __future__ import annotations

from fastapi.testclient import TestClient

from llm_wiki.scaffold import scaffold
from llm_wiki.webapp.main import create_app


def test_jobs_page_uses_shared_sidebar_navigation(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_WIKI_CONFIG", raising=False)
    paths = scaffold(tmp_path)
    client = TestClient(create_app(paths))

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "작업" in response.text
    for label in [
        "대시보드",
        "소스",
        "수신함",
        "수집",
        "작업",
        "질문",
        "검사",
        "그래프",
        "변경사항",
        "로그",
        "설정",
    ]:
        assert f">{label}<" in response.text
    assert "최근 작업" in response.text
