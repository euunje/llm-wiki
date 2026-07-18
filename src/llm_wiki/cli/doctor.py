from __future__ import annotations

import argparse
import sqlite3

from llm_wiki.common import mask_sensitive, read_env_file
from llm_wiki.config import load_settings
from llm_wiki.db import inspect_database
from llm_wiki.jobs import record_artifact
from llm_wiki.workspace import required_directories, resolve_workspace


def _status(ok: bool, warn: bool = False) -> str:
    if ok:
        return "ok"
    return "warn" if warn else "fail"


def _check_sqlite_vec() -> tuple[str, str]:
    conn = sqlite3.connect(":memory:")
    try:
        try:
            conn.execute("CREATE VIRTUAL TABLE temp.vec_probe USING vec0(embedding float[4])")
            return "ok", "sqlite-vec available"
        except sqlite3.DatabaseError as exc:
            return "warn", f"sqlite-vec unavailable: {exc}"
    finally:
        conn.close()


def run_doctor(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    workspace = resolve_workspace(args.path)
    path_checks = []
    for directory in required_directories(workspace):
        path_checks.append({
            "path": str(directory.relative_to(workspace.root)),
            "status": _status(directory.exists(), warn=True),
        })
    settings = load_settings(workspace.settings_file)
    db_info = inspect_database(workspace.db)
    env_values = read_env_file(workspace.env_file)
    vec_status, vec_message = _check_sqlite_vec()
    report = {
        "status": "ok",
        "workspace": str(workspace.root),
        "paths": path_checks,
        "settings": {
            "status": "ok",
            "path": str(workspace.settings_file.relative_to(workspace.root)),
            "value": mask_sensitive(settings),
        },
        "database": {
            "status": _status(bool(db_info["exists"])),
            **db_info,
        },
        "fts5": {
            "status": _status(bool(db_info["fts5"]), warn=True),
            "message": "FTS5 virtual table present" if db_info["fts5"] else "FTS5 virtual table missing",
        },
        "sqlite_vec": {
            "status": vec_status,
            "message": vec_message,
        },
        "env": {
            "status": _status(workspace.env_file.exists(), warn=True),
            "path": str(workspace.env_file.relative_to(workspace.root)),
            "values": mask_sensitive(env_values),
        },
        "models": {
            "status": "warn",
            "embedding_backend": settings.get("embedding", {}).get("backend"),
            "embedding_model": settings.get("embedding", {}).get("default_model"),
            "llm_endpoint_configured": bool(settings.get("llm", {}).get("endpoint")),
            "chat_model_configured": bool(settings.get("llm", {}).get("default_chat_model")),
            "embedding_model_configured": bool(settings.get("llm", {}).get("default_embedding_model")),
        },
    }
    artifact = record_artifact(
        workspace,
        artifact_type="doctor_report",
        task_type="doctor",
        payload=report,
        target_type="workspace",
        target_id="global",
    )
    report.update(artifact)
    return 0, report
