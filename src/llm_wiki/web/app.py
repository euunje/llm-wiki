from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import time
import uuid
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from llm_wiki.bootstrap import ensure_workspace
from llm_wiki.cli.phase1_placeholders import run_ask
from llm_wiki.common import mask_sensitive, new_id, utc_now
from llm_wiki.config import load_settings, save_settings
from llm_wiki.db.schema import connect, inspect_database
from llm_wiki.jobs.records import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.llm.models import ALLOWED_ROUTE_TASKS, get_route_map, list_models, set_route_model, test_model_connection
from llm_wiki.pipeline import ingest_markdown_file, ingest_text, process_inbox_source, scan_inbox
from llm_wiki.pipeline.errors import UnsupportedInputError
from llm_wiki.schema.prompts import (
    confirm_prompt_version,
    create_prompt_version,
    ensure_default_prompts,
    get_active_prompt,
    list_prompt_versions,
    rollback_prompt_version,
    test_prompt_version,
)
from llm_wiki.schema.review import list_pending_candidates, record_human_decision, record_retry_instruction
from llm_wiki.search import SEARCH_MODES, ask_workspace, search_workspace
from llm_wiki.workspace import WorkspacePaths, resolve_workspace

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency at runtime
    load_dotenv = None

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from llm_wiki.fs_helpers import DirectoryPermissionError, is_path_under_directory, safe_list_dir


class ReviewDecisionRequest(BaseModel):
    candidate_id: str | None = None
    action: str
    candidate_ids: list[str] = Field(default_factory=list)
    note: str | None = None
    reason: str | None = None
    instruction: str | None = None
    decision_type: str | None = None
    edited_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptVersionCreateRequest(BaseModel):
    task_type: str
    version_label: str | None = None
    prompt_text: str
    change_note: str | None = None
    created_by: str = "admin"


class RouteUpdateRequest(BaseModel):
    task_type: str
    model_id: str


class LlmConfigUpdateRequest(BaseModel):
    endpoint: str = ""
    api_key_env: str = "LLM_WIKI_API_KEY"
    api_key: str | None = None
    default_chat_model: str = ""
    default_embedding_model: str = ""
    chat_model_name: str = ""
    embedding_model_name: str = ""


class VaultConfigUpdateRequest(BaseModel):
    vault_path: str = "vault"
    data_path: str = "data"
    create_missing: bool = True


class AskRequest(BaseModel):
    query: str = ""


class VaultCreateRequest(BaseModel):
    parent_path: str = ""
    vault_name: str = "llm-wiki"


class VaultMappingRequest(BaseModel):
    vault_path: str
    role_map: dict[str, str] = Field(default_factory=dict)


class InboxTextRequest(BaseModel):
    title: str
    text: str
    tags: list[str] = Field(default_factory=list)
    source_note: str | None = None


class InboxProcessRequest(BaseModel):
    item_ids: list[str] = Field(default_factory=list)
    item_id: str | None = None


class InboxRetryRequest(BaseModel):
    note: str | None = None


class LlmConcurrencyUpdateRequest(BaseModel):
    value: int = 1


class PromptRollbackRequest(BaseModel):
    reason: str | None = None
    created_by: str = "admin"


class MappingRetryRequest(BaseModel):
    reason: str
    instruction: str
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_VALUE = "admin"


def create_app(workspace_path: str | Path | None = None) -> FastAPI:
    workspace = resolve_workspace(workspace_path)
    if load_dotenv is not None and workspace.env_file.exists():
        load_dotenv(workspace.env_file, override=False)
    ensure_workspace(workspace)
    ensure_default_prompts(workspace.db)
    settings = load_settings(workspace.settings_file)
    web_settings = settings.get("web") or {}
    app = FastAPI(title="LLM Wiki Local Web")
    app.state.workspace = workspace
    app.state.settings = settings
    app.state.web_settings = web_settings
    app.state.templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def admin_password() -> str:
        env_name = str(web_settings.get("admin_password_env") or "LLM_WIKI_WEB_ADMIN_PASSWORD")
        return os.environ.get(env_name, "")

    def session_cookie_name() -> str:
        return str(web_settings.get("session_cookie_name") or "llm_wiki_web_session")

    def session_ttl_seconds() -> int:
        raw = web_settings.get("session_ttl_seconds") or 43200
        try:
            return max(60, int(raw))
        except (TypeError, ValueError):
            return 43200

    def sign_session(expires_at: int) -> str:
        secret = admin_password().encode("utf-8")
        data = f"{SESSION_VALUE}:{expires_at}:{workspace.root}".encode("utf-8")
        signature = hmac.new(secret, data, hashlib.sha256).hexdigest()
        return f"{SESSION_VALUE}:{expires_at}:{signature}"

    def is_authenticated(request: Request) -> bool:
        password = admin_password()
        if not password:
            return False
        raw = request.cookies.get(session_cookie_name(), "")
        parts = raw.split(":", 2)
        if len(parts) != 3:
            return False
        user_value, expires_raw, actual_sig = parts
        if user_value != SESSION_VALUE:
            return False
        try:
            expires_at = int(expires_raw)
        except ValueError:
            return False
        if expires_at < int(time.time()):
            return False
        expected = sign_session(expires_at)
        return hmac.compare_digest(expected, raw)

    def auth_setup_status() -> dict[str, Any]:
        env_name = str(web_settings.get("admin_password_env") or "LLM_WIKI_WEB_ADMIN_PASSWORD")
        configured = bool(admin_password())
        return {
            "configured": configured,
            "env_name": env_name,
            "message": "Web admin password is configured" if configured else f"Set {env_name} in the environment or .env before logging in",
        }

    def require_auth(request: Request) -> None:
        if is_authenticated(request):
            return
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    def list_dir_or_403(path: Path, *, relative_to: Path) -> list[dict[str, Any]]:
        try:
            return safe_list_dir(path, relative_to, raise_on_permission=True)
        except DirectoryPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    def render_page(request: Request, template_name: str, context: dict[str, Any] | None = None, *, status_code: int = 200) -> HTMLResponse:
        ctx = context or {}
        setup_status = ctx.get("setup") if isinstance(ctx.get("setup"), dict) else setup_status_payload()
        return app.state.templates.TemplateResponse(
            request=request,
            name=template_name,
            context={
                "request": request,
                "auth": auth_setup_status(),
                "setup_status": setup_status,
                "workspace": str(workspace.root),
                "active_nav": ctx.get("page", ""),
                **ctx,
            },
            status_code=status_code,
        )

    def load_runtime_settings(*, resolve_env: bool = True) -> dict[str, Any]:
        return load_settings(workspace.settings_file, resolve_env=resolve_env)

    def save_runtime_settings(settings_data: dict[str, Any]) -> None:
        save_settings(workspace.settings_file, settings_data)

    def read_json_value(raw: str | None, fallback: Any) -> Any:
        try:
            return json.loads(raw or "null") if raw is not None else fallback
        except json.JSONDecodeError:
            return fallback

    def latest_artifact_payload(*, artifact_type: str, target_type: str, target_id: str) -> dict[str, Any] | None:
        conn = connect(workspace.db)
        try:
            row = conn.execute(
                """
                SELECT metadata_json FROM artifacts
                WHERE artifact_type = ? AND target_type = ? AND target_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (artifact_type, target_type, target_id),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        payload = read_json_value(row["metadata_json"], {})
        return payload if isinstance(payload, dict) else None

    def latest_model_test_status(model_id: str) -> dict[str, Any]:
        payload = latest_artifact_payload(artifact_type="model_test_report", target_type="model", target_id=model_id)
        if not payload:
            return {"test_status": "blocked", "reason": "model connection test has not passed"}
        status = str(payload.get("status") or payload.get("result") or "failed")
        return {
            "test_status": "passed" if status == "ok" else status,
            "reason": payload.get("reason"),
            "artifact_id": payload.get("artifact_id"),
        }

    def source_job_rows(conn: sqlite3.Connection, source_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE target_id = ? OR target_id IN (
                SELECT id FROM agent_runs WHERE job_id = jobs.id
            )
            ORDER BY created_at DESC
            """,
            (source_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def source_run_rows(conn: sqlite3.Connection, source_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT ar.*
            FROM agent_runs ar
            LEFT JOIN review_candidates rc ON rc.run_id = ar.id
            WHERE rc.source_id = ? OR EXISTS (
                SELECT 1 FROM jobs j WHERE j.id = ar.job_id AND j.target_id = ?
            )
            ORDER BY ar.started_at DESC
            """,
            (source_id, source_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def source_artifact_rows(conn: sqlite3.Connection, source_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE target_id = ? ORDER BY created_at DESC",
            (source_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def public_inbox_status(source: dict[str, Any], jobs: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
        if any(job.get("status") == "blocked" for job in jobs):
            return "blocked"
        if any(job.get("status") == "failed" for job in jobs):
            return "failed"
        if any(job.get("status") in {"queued", "running", "needs_review"} for job in jobs):
            return "processing"
        if any(candidate.get("status") == "pending" for candidate in candidates):
            return "needs_mapping"
        if source.get("pipeline_stage") in {"synced", "mapped", "candidate_generated", "embedded", "chunked", "normalized"}:
            return "completed"
        return "new"

    def inbox_progress_line(source: dict[str, Any], jobs: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> str:
        stage = str(source.get("pipeline_stage") or "created")
        if any(job.get("status") == "blocked" for job in jobs):
            return "processing blocked · check artifact and retry"
        if any(job.get("status") == "failed" for job in jobs):
            return "processing failed · retry available"
        if any(job.get("status") in {"queued", "running"} for job in jobs):
            return f"raw saved ✓ · {stage}…"
        if any(candidate.get("status") == "pending" for candidate in candidates):
            return "mapping candidates ready"
        if stage in {"embedded", "candidate_generated", "mapped", "synced"}:
            return f"{stage} ✓"
        return "not processed yet"

    def source_origin_label(source: dict[str, Any], metadata: dict[str, Any]) -> str:
        source_type = str(source.get("source_type") or "")
        origin = str(source.get("origin") or "")
        if source_type == "user_text":
            return "text"
        if "00_Inbox" in origin:
            return origin.split("vault/")[-1] if "vault/" in origin else origin
        return metadata.get("original_name") or origin or source_type or "upload"

    def source_kind(source: dict[str, Any]) -> str:
        return "text" if source.get("source_type") == "user_text" else "file"

    def build_inbox_item(source: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
        metadata = read_json_value(source.get("metadata_json"), {}) or {}
        jobs = [dict(row) for row in conn.execute("SELECT * FROM jobs WHERE target_id = ? ORDER BY created_at DESC", (source["id"],)).fetchall()]
        candidates = [dict(row) for row in conn.execute("SELECT * FROM review_candidates WHERE source_id = ? ORDER BY created_at DESC", (source["id"],)).fetchall()]
        status_value = public_inbox_status(source, jobs, candidates)
        return {
            "id": source["id"],
            "title": source.get("title") or source["id"],
            "kind": source_kind(source),
            "status": status_value,
            "origin": source_origin_label(source, metadata),
            "source_type": source.get("source_type"),
            "pipeline_stage": source.get("pipeline_stage"),
            "review_status": source.get("review_status"),
            "raw_path": source.get("raw_path"),
            "normalized_path": source.get("normalized_path"),
            "created_at": source.get("created_at"),
            "updated_at": source.get("updated_at"),
            "metadata": metadata,
            "candidate_count": len(candidates),
            "progress": inbox_progress_line(source, jobs, candidates),
            "available_actions": {
                "process": status_value in {"new", "failed"},
                "retry": status_value == "failed",
                "open_mapping": status_value == "needs_mapping",
                "view_log": status_value in {"processing", "failed", "completed"},
                "view_result_record": status_value == "completed",
            },
        }

    def build_processing_log(source_id: str, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        source = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if not source:
            raise HTTPException(status_code=404, detail=f"Unknown inbox item: {source_id}")
        timeline = [{"at": source["created_at"], "event": "source registered", "detail": source["title"]}]
        if source["raw_path"]:
            timeline.append({"at": source["created_at"], "event": "raw saved", "detail": source["raw_path"]})
        for job in conn.execute("SELECT * FROM jobs WHERE target_id = ? ORDER BY created_at", (source_id,)).fetchall():
            event = str(job["status"] or "queued")
            detail = str(job["job_type"] or "job")
            if job["error_json"]:
                error = read_json_value(job["error_json"], {})
                reason = error.get("reason") if isinstance(error, dict) else str(error)
                if reason:
                    detail = f"{detail} · {reason}"
            timeline.append({"at": job["started_at"] or job["created_at"], "event": event, "detail": detail})
        for row in conn.execute("SELECT id, status, candidate_type, created_at FROM review_candidates WHERE source_id = ? ORDER BY created_at", (source_id,)).fetchall():
            timeline.append({"at": row["created_at"], "event": "candidate", "detail": f"{row['candidate_type']} · {row['status']} · {row['id']}"})
        return timeline

    def current_concurrency() -> int:
        llm_settings = load_runtime_settings(resolve_env=False).get("llm") or {}
        try:
            return min(3, max(1, int(llm_settings.get("concurrency") or 1)))
        except (TypeError, ValueError):
            return 1

    def update_concurrency(value: int) -> dict[str, Any]:
        bounded = min(3, max(1, int(value)))
        settings_data = load_runtime_settings(resolve_env=False)
        settings_data.setdefault("llm", {})["concurrency"] = bounded
        save_runtime_settings(settings_data)
        record_artifact(
            workspace,
            artifact_type="settings_change",
            task_type="web_settings_llm_concurrency_update",
            payload={"status": "ok", "concurrency": bounded},
            target_type="settings",
            target_id="llm_concurrency",
        )
        return {
            "value": bounded,
            "default": 1,
            "min": 1,
            "max": 3,
            "warning": "Higher concurrency may increase local LLM load" if bounded > 1 else None,
        }

    def concurrency_payload() -> dict[str, Any]:
        value = current_concurrency()
        return {
            "value": value,
            "default": 1,
            "min": 1,
            "max": 3,
            "warning": "Higher concurrency may increase local LLM load" if value > 1 else None,
        }

    ROUTE_LABELS = {
        "page_validate": {"task_type": "extract_claims", "label": "Page 검증", "capability": "chat"},
        "page_mapping": {"task_type": "map", "label": "Page Mapping", "capability": "chat"},
        "relationship_validate": {"task_type": "link", "label": "Relationship 검증", "capability": "chat"},
        "retry_instruction": {"task_type": "summarize", "label": "Retry instruction", "capability": "chat"},
        "prompt_test": {"task_type": "ask", "label": "Prompt test", "capability": "chat"},
        "embedding": {"task_type": "compile", "label": "Embedding/Search", "capability": "embedding"},
    }

    def route_rows() -> list[dict[str, Any]]:
        llm = masked_llm_status()
        models = {model["id"]: model for model in llm.get("models") or []}
        raw_routes = llm.get("routes") or {}
        settings_llm = load_runtime_settings(resolve_env=False).get("llm") or {}
        default_chat_model = settings_llm.get("default_chat_model") or "chat_default"
        default_embedding_model = settings_llm.get("default_embedding_model") or "embedding_default"
        rows = []
        for route_id, cfg in ROUTE_LABELS.items():
            internal_task = cfg["task_type"]
            fallback_model = default_embedding_model if cfg["capability"] == "embedding" else default_chat_model
            model_id = raw_routes.get(internal_task) or fallback_model
            model = models.get(model_id) or {"id": model_id, "capability": "unknown", "configured": False}
            rows.append(
                {
                    "route_id": route_id,
                    "task_type": internal_task,
                    "label": cfg["label"],
                    "required_capability": cfg["capability"],
                    "model_id": model_id,
                    "status": "default" if raw_routes.get(internal_task) in {None, default_chat_model, default_embedding_model} else "custom",
                    "model": model,
                    "save_label": "Use this model",
                }
            )
        return rows

    def sanitize_vault_relative_path(raw_path: str | None, *, allow_root: bool = True) -> Path:
        raw_value = (raw_path or "").strip()
        if not raw_value and allow_root:
            return workspace.vault
        rel = Path(raw_value)
        if rel.is_absolute() or any(part in {"..", ""} for part in rel.parts if part != "."):
            raise HTTPException(status_code=422, detail="Invalid vault path")
        resolved = (workspace.vault / rel).resolve()
        if not is_path_under_directory(resolved, workspace.vault):
            raise HTTPException(status_code=422, detail="Path traversal blocked")
        return resolved

    browse_root = Path.home().resolve()

    def _validate_non_hidden_relative_path(path: Path, *, detail: str) -> None:
        parts = [part for part in path.parts if part not in {"", "."}]
        if any(part == ".." for part in parts):
            raise HTTPException(status_code=422, detail="Path traversal blocked")
        if any(part.startswith(".") for part in parts):
            raise HTTPException(status_code=422, detail=detail)

    def _has_symlink_component(path: Path, *, root: Path) -> bool:
        try:
            rel = path.relative_to(root)
        except ValueError:
            return False
        cursor = root
        for part in rel.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return True
        return False

    def home_relative_str(path: Path) -> str:
        resolved = path.resolve()
        if resolved == browse_root:
            return "~"
        return f"~/{resolved.relative_to(browse_root).as_posix()}"

    def sanitize_workspace_browse_path(raw_path: str | None) -> tuple[Path, str]:
        raw_value = (raw_path or "").strip()
        if raw_value in {"", ".", "~"}:
            return browse_root, "~"

        if raw_value.startswith("~/"):
            rel = Path(raw_value[2:])
            if any(part in {"..", ""} for part in rel.parts if part != "."):
                raise HTTPException(status_code=422, detail="Invalid browse path")
            _validate_non_hidden_relative_path(rel, detail="Hidden browse path is not allowed")
            candidate = browse_root / rel
        else:
            provided = Path(raw_value)
            if provided.is_absolute():
                candidate = provided
                try:
                    rel = candidate.relative_to(browse_root)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail="Browse path must stay under HOME") from exc
                _validate_non_hidden_relative_path(rel, detail="Hidden browse path is not allowed")
            else:
                if any(part in {"..", ""} for part in provided.parts if part != "."):
                    raise HTTPException(status_code=422, detail="Invalid browse path")
                _validate_non_hidden_relative_path(provided, detail="Hidden browse path is not allowed")
                rel = provided
                candidate = browse_root / rel

        if _has_symlink_component(candidate, root=browse_root):
            raise HTTPException(status_code=422, detail="Symlink browse path is not allowed")
        resolved = candidate.resolve()
        if not is_path_under_directory(resolved, browse_root):
            raise HTTPException(status_code=422, detail="Path traversal blocked")
        resolved_rel = resolved.relative_to(browse_root)
        _validate_non_hidden_relative_path(resolved_rel, detail="Hidden browse path is not allowed")
        return resolved, home_relative_str(resolved)

    def sanitize_workspace_relative_path(raw_path: str | None, *, allow_root: bool = False) -> tuple[Path, str]:
        resolved, rel_path = sanitize_workspace_browse_path(raw_path)
        if not allow_root and rel_path == "~":
            raise HTTPException(status_code=422, detail="Root path is not allowed")
        return resolved, rel_path

    def detect_vault_role_map(selected_path: Path) -> tuple[dict[str, str], list[str]]:
        candidates: dict[str, Path] = {}

        def remember(role: str, candidate: Path) -> None:
            if role not in candidates and candidate.exists() and candidate.is_dir() and is_path_under_directory(candidate.resolve(), browse_root):
                candidates[role] = candidate.resolve()

        for child in sorted(selected_path.iterdir(), key=lambda item: item.name.lower()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            normalized = "".join(ch.lower() for ch in child.name if ch.isalnum())
            if "inbox" in normalized:
                remember("inbox", child)
            if "wiki" in normalized:
                remember("wiki", child)
            if "review" in normalized:
                remember("review", child)
            if normalized in {"raw", "raws"} or "raw" in normalized:
                remember("raws", child)
            if "setting" in normalized:
                remember("settings", child)
            if normalized == "data" or normalized.endswith("data"):
                remember("data", child)
                remember("artifacts", child / "artifacts")
            if "artifact" in normalized:
                remember("artifacts", child)

        if selected_path.parent == workspace.root and is_path_under_directory(workspace.root, browse_root):
            remember("data", workspace.root / "data")
            remember("artifacts", workspace.root / "data" / "artifacts")

        role_map = {role: home_relative_str(path) for role, path in candidates.items()}
        missing_roles = [role for role in ["inbox", "wiki", "review", "raws", "settings"] if role not in role_map]
        return role_map, missing_roles

    def apply_vault_role_mapping(vault_rel: str, role_map: dict[str, str]) -> dict[str, Any]:
        settings_data = load_runtime_settings(resolve_env=False)
        paths = settings_data.setdefault("paths", {})
        workspace_settings = settings_data.setdefault("workspace", {})
        workspace_settings["human_vault"] = vault_rel
        paths["vault"] = vault_rel
        if "data" in role_map:
            data_rel = role_map["data"]
            paths["data"] = data_rel
            workspace_settings["system_data"] = data_rel
            paths["db"] = f"{data_rel.rstrip('/')}/wiki.sqlite"
            paths["raw"] = f"{data_rel.rstrip('/')}/raw"
            paths["normalized"] = f"{data_rel.rstrip('/')}/normalized"
            paths["exports"] = f"{data_rel.rstrip('/')}/exports"
            paths["cache"] = f"{data_rel.rstrip('/')}/cache"
            if "artifacts" not in role_map:
                paths["artifacts"] = f"{data_rel.rstrip('/')}/artifacts"
        if "artifacts" in role_map:
            paths["artifacts"] = role_map["artifacts"]
        settings_root = role_map.get("settings") or f"{vault_rel.rstrip('/')}/90_Settings"
        paths["settings"] = f"{settings_root.rstrip('/')}/settings.yaml"
        inbox_root = role_map.get("inbox") or f"{vault_rel.rstrip('/')}/00_Inbox"
        settings_data.setdefault("inbox", {})["paths"] = {
            "files": f"{inbox_root.rstrip('/')}/files",
            "memo": f"{inbox_root.rstrip('/')}/memo",
            "text": f"{inbox_root.rstrip('/')}/text",
        }
        settings_data["vault"] = {"vault_path": vault_rel, "role_map": dict(role_map)}
        save_runtime_settings(settings_data)
        return settings_data

    def is_visible_vault_path(path: Path) -> bool:
        return not any(part.startswith(".") for part in path.relative_to(workspace.vault).parts if part)

    def relative_vault_path(path: Path) -> str:
        if path == workspace.vault:
            return ""
        return str(path.relative_to(workspace.vault))

    def strip_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---\n"):
            return {}, text
        parts = text.split("\n---\n", 1)
        if len(parts) != 2:
            return {}, text
        frontmatter: dict[str, Any] = {}
        for line in parts[0].splitlines()[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()
        return frontmatter, parts[1]

    def vault_tree_node(path: Path, *, visited: set[Path] | None = None) -> dict[str, Any]:
        visited = visited or set()
        resolved = path.resolve()
        if resolved in visited:
            return {"name": path.name if path != workspace.vault else "vault", "path": relative_vault_path(path), "kind": "folder", "children": []}
        visited = {resolved, *visited}
        children = []
        for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if not is_visible_vault_path(child):
                continue
            if child.is_symlink():
                continue
            if child.is_dir():
                children.append(vault_tree_node(child, visited=visited))
        return {"name": path.name if path != workspace.vault else "vault", "path": relative_vault_path(path), "kind": "folder", "children": children}

    def folder_listing(path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_dir():
            raise HTTPException(status_code=404, detail="Vault folder not found")
        folders = []
        files = []
        for entry in list_dir_or_403(path, relative_to=workspace.vault):
            child = path / entry["name"]
            if not is_visible_vault_path(child):
                continue
            stat = child.stat()
            item = {
                "name": entry["name"],
                "path": relative_vault_path(child),
                "kind": "folder" if entry["is_dir"] else "file",
                "size": stat.st_size if not entry["is_dir"] else None,
                "modified_at": stat.st_mtime,
            }
            if entry["is_dir"]:
                folders.append(item)
            else:
                files.append(item)
        return {"path": relative_vault_path(path), "folders": folders, "files": files}

    def vault_file_payload(path: Path) -> dict[str, Any]:
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Vault file not found")
        if not is_visible_vault_path(path):
            raise HTTPException(status_code=404, detail="Vault file not found")
        suffix = path.suffix.lower()
        stat = path.stat()
        text = path.read_text(encoding="utf-8", errors="replace")
        metadata, body = strip_frontmatter(text) if suffix == ".md" else ({}, text)
        preview_type = "markdown" if suffix == ".md" else ("json" if suffix == ".json" else "text")
        return {
            "name": path.name,
            "path": relative_vault_path(path),
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "preview_type": preview_type,
            "content": body,
            "metadata": metadata,
            "raw_content": text,
            "read_only": True,
        }

    def dashboard_summary() -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            source_rows = [dict(row) for row in conn.execute("SELECT * FROM sources ORDER BY updated_at DESC").fetchall()]
            inbox_items = [build_inbox_item(row, conn) for row in source_rows]
            inbox_counts = Counter(item["status"] for item in inbox_items)
            review_pending = [json_for_candidate(dict(row)) for row in conn.execute("SELECT * FROM review_candidates WHERE status = 'pending' ORDER BY created_at DESC").fetchall()]
            decisions = [dict(row) for row in conn.execute("SELECT decision_type, decided_at, candidate_id FROM human_decisions ORDER BY decided_at DESC LIMIT 10").fetchall()]
            failed_jobs = [dict(row) for row in conn.execute("SELECT id, target_type, target_id, error_json, created_at FROM jobs WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10").fetchall()]
        finally:
            conn.close()
        wiki = api_dashboard_wiki()
        vault_roots = [path for path in sorted(workspace.vault.iterdir()) if path.is_dir() and is_visible_vault_path(path)] if workspace.vault.exists() else []
        llm = masked_llm_status()
        issues_count = len(failed_jobs) + sum(1 for item in review_pending if item.get("review_route") == "needs_retry")
        return {
            "inbox": {
                "new": inbox_counts.get("new", 0),
                "processing": inbox_counts.get("processing", 0),
                "failed": inbox_counts.get("failed", 0),
                "needs_mapping": inbox_counts.get("needs_mapping", 0),
                "completed": inbox_counts.get("completed", 0),
                "total": len(inbox_items),
            },
            "mapping": {
                "new": len(review_pending),
                "in_review": len(decisions),
                "errors": sum(1 for item in failed_jobs if item.get("target_type") in {"candidate", "source"}),
            },
            "wiki": {
                "concept_count": wiki["concept_count"],
                "page_count": wiki["page_count"],
                "recently_updated": 0,
            },
            "vault": {
                "ready": workspace.vault.exists(),
                "root_folder_count": len(vault_roots),
                "path": str(workspace.vault),
            },
            "issues": {
                "count": issues_count,
                "failed_jobs": len(failed_jobs),
                "retry_needed": sum(1 for item in review_pending if item.get("review_route") == "needs_retry"),
            },
            "system": {
                "llm": {
                    "endpoint_configured": not llm["missing"]["endpoint_missing"],
                    "chat_model_missing": llm["missing"]["chat_model_missing"],
                    "embedding_model_missing": llm["missing"]["embedding_model_missing"],
                    "concurrency": current_concurrency(),
                },
                "db": inspect_database(workspace.db),
                "vault_path": str(workspace.vault),
                "data_path": str(workspace.data),
            },
        }

    def json_for_candidate(row: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(row.get("payload_json") or "{}")
        return {
            **row,
            "payload": payload,
            "related_candidate_keys": json.loads(row.get("related_candidate_keys_json") or "[]"),
        }

    def markdown_title(path: Path) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("# ").strip() or path.stem
        return path.stem.replace("_", " ")

    def parse_markdown_sections(content: str) -> dict[str, Any]:
        title = ""
        summary = ""
        aliases: list[str] = []
        claims: list[str] = []
        relations: list[str] = []
        sources: list[str] = []
        section = ""
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()
            if line.startswith("# ") and not title:
                title = line[2:].strip()
                continue
            if lowered.startswith("## "):
                name = lowered[3:].strip()
                if "alias" in name or "별칭" in name:
                    section = "aliases"
                elif "claim" in name or "주장" in name or "근거" in name:
                    section = "claims"
                elif "relation" in name or "관련" in name:
                    section = "relations"
                elif "source" in name or "출처" in name:
                    section = "sources"
                else:
                    section = ""
                continue
            if line.startswith("#"):
                continue
            if not summary:
                summary = line.lstrip("- ").strip()
            target = None
            if section == "aliases":
                target = aliases
            elif section == "claims":
                target = claims
            elif section == "relations":
                target = relations
            elif section == "sources":
                target = sources
            if target is not None:
                value = line[1:].strip() if line.startswith("-") else line
                if value and value not in target:
                    target.append(value)
        return {
            "title": title,
            "summary": summary,
            "aliases": aliases,
            "claims": claims,
            "relations": relations,
            "sources": sources,
        }

    def slug_title(value: str) -> str:
        return value.replace("_", " ").replace("-", " ").strip() or value

    def candidate_payload(row: dict[str, Any] | sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        raw = row["payload_json"] if isinstance(row, sqlite3.Row) else row.get("payload_json")
        return json.loads(raw or "{}")

    def related_candidate_keys(row: dict[str, Any] | sqlite3.Row | None) -> list[str]:
        if row is None:
            return []
        raw = row["related_candidate_keys_json"] if isinstance(row, sqlite3.Row) else row.get("related_candidate_keys_json")
        try:
            values = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []
        return [str(value) for value in values if str(value).strip()]

    def collect_evidence_refs(value: Any, refs: list[str] | None = None) -> list[str]:
        if refs is None:
            refs = []
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = key.lower()
                if "evidence" in lowered or lowered.endswith("_ref") or lowered.endswith("_refs"):
                    if isinstance(item, list):
                        for sub in item:
                            if isinstance(sub, (str, int, float)):
                                refs.append(str(sub))
                    elif isinstance(item, (str, int, float)):
                        refs.append(str(item))
                collect_evidence_refs(item, refs)
        elif isinstance(value, list):
            for item in value:
                collect_evidence_refs(item, refs)
        return list(dict.fromkeys(refs))

    def query_candidates(*, status_filter: str | None = None, candidate_id: str | None = None, candidate_key: str | None = None) -> list[dict[str, Any]]:
        conn = connect(workspace.db)
        try:
            query = "SELECT * FROM review_candidates"
            clauses: list[str] = []
            params: list[Any] = []
            if status_filter is not None:
                clauses.append("status = ?")
                params.append(status_filter)
            if candidate_id is not None:
                clauses.append("id = ?")
                params.append(candidate_id)
            if candidate_key is not None:
                clauses.append("candidate_key = ?")
                params.append(candidate_key)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY created_at"
            return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
        finally:
            conn.close()

    def get_candidate_by_id(candidate_id: str) -> dict[str, Any] | None:
        rows = query_candidates(candidate_id=candidate_id)
        return rows[0] if rows else None

    def get_candidate_by_key(candidate_key: str) -> dict[str, Any] | None:
        rows = query_candidates(candidate_key=candidate_key)
        return rows[0] if rows else None

    def known_concept_ids() -> set[str]:
        ids = {path.stem for path in workspace.wiki_concepts.glob("*.md")} if workspace.wiki_concepts.exists() else set()
        for row in query_candidates():
            existing_id = candidate_payload(row).get("existing_node_id")
            if isinstance(existing_id, str) and existing_id.strip():
                ids.add(existing_id.strip())
        return ids

    def concept_source_rows(concept_id: str) -> list[dict[str, Any]]:
        conn = connect(workspace.db)
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT s.id, s.title, s.pipeline_stage
                FROM review_candidates rc
                JOIN sources s ON s.id = rc.source_id
                WHERE json_extract(rc.payload_json, '$.existing_node_id') = ?
                   OR rc.candidate_key = ?
                   OR rc.related_candidate_keys_json LIKE ?
                ORDER BY s.created_at DESC
                """,
                (concept_id, concept_id, f'%"{concept_id}"%'),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def list_concepts() -> list[dict[str, Any]]:
        concepts: list[dict[str, Any]] = []
        for concept_id in sorted(known_concept_ids()):
            path = workspace.wiki_concepts / f"{concept_id}.md"
            if path.exists():
                parsed = parse_markdown_sections(path.read_text(encoding="utf-8"))
                title = parsed["title"] or markdown_title(path)
                summary = parsed["summary"]
                aliases = parsed["aliases"]
                claims_count = len(parsed["claims"])
                relations_count = len(parsed["relations"])
                rel_path: str | None = str(path.relative_to(workspace.root))
            else:
                title = slug_title(concept_id)
                summary = "Markdown page not created yet. Review data references this concept id."
                aliases = []
                claims_count = 0
                relations_count = 0
                rel_path = None
            concepts.append(
                {
                    "id": concept_id,
                    "title": title,
                    "path": rel_path,
                    "aliases": aliases,
                    "summary": summary,
                    "claims_count": claims_count,
                    "relations_count": relations_count,
                }
            )
        return concepts

    def concept_detail(concept_id: str) -> dict[str, Any]:
        path = workspace.wiki_concepts / f"{concept_id}.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            parsed = parse_markdown_sections(content)
            title = parsed["title"] or markdown_title(path)
            aliases = parsed["aliases"]
            claims = parsed["claims"]
            relations = parsed["relations"]
            source_refs = parsed["sources"]
            rel_path: str | None = str(path.relative_to(workspace.root))
        elif concept_id in known_concept_ids():
            title = slug_title(concept_id)
            content = f"# {title}\n\nMarkdown page has not been generated yet. Review data still references this concept id."
            aliases = []
            claims = []
            relations = []
            source_refs = []
            rel_path = None
        else:
            raise HTTPException(status_code=404, detail=f"Unknown concept_id: {concept_id}")
        related = []
        for row in query_candidates():
            if candidate_payload(row).get("existing_node_id") == concept_id:
                related.append({"id": row["id"], "candidate_type": row["candidate_type"], "candidate_key": row["candidate_key"]})
        return {
            "id": concept_id,
            "title": title,
            "content": content,
            "path": rel_path,
            "aliases": aliases,
            "claims": claims,
            "relations": relations,
            "sources": source_refs or concept_source_rows(concept_id),
            "related_candidates": related,
        }

    def candidate_graph_detail(row: dict[str, Any]) -> dict[str, Any]:
        payload = candidate_payload(row)
        return {
            "id": row["candidate_key"],
            "title": payload.get("title") or row["candidate_key"],
            "content": json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            "path": None,
            "aliases": payload.get("aliases") or [],
            "claims": payload.get("evidence_claim_keys") or [],
            "relations": payload.get("related_candidate_keys") or related_candidate_keys(row),
            "sources": [{"id": row.get("source_id")}] if row.get("source_id") else [],
            "candidate": json_for_candidate(row),
            "evidence_refs": collect_evidence_refs(payload),
        }

    def graph_data(concept_id: str) -> dict[str, Any]:
        fallback = get_candidate_by_key(concept_id)
        if concept_id in known_concept_ids():
            center = {"id": concept_id, "label": concept_detail(concept_id)["title"], "kind": "concept"}
        elif fallback:
            center = {"id": concept_id, "label": candidate_payload(fallback).get("title") or concept_id, "kind": "candidate", "reason": "candidate_fallback"}
        else:
            return {
                "center": {"id": concept_id, "label": concept_id, "kind": "unknown"},
                "nodes": [],
                "edges": [],
                "reason": "no_concept_or_candidate_match",
            }
        nodes: dict[str, dict[str, Any]] = {concept_id: center}
        edges: list[dict[str, Any]] = []
        for row in query_candidates():
            payload = candidate_payload(row)
            if row.get("candidate_type") != "mapping":
                continue
            if payload.get("existing_node_id") != concept_id and row.get("candidate_key") != concept_id:
                continue
            incoming = payload.get("incoming_ref") or {}
            node_id = incoming.get("candidate_key") or row.get("candidate_key")
            nodes[node_id] = {"id": node_id, "label": node_id, "kind": "candidate"}
            edges.append({"source": node_id, "target": concept_id, "label": payload.get("mapping_action") or "related"})
        return {"center": center, "nodes": list(nodes.values()), "edges": edges, "reason": center.get("reason")}

    def slugify_concept_id(value: str) -> str:
        slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", value.strip().lower()).strip("-")
        return slug or f"concept-{uuid.uuid4().hex[:8]}"

    def candidate_related_rows(candidate: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [candidate]
        keys = related_candidate_keys(candidate)
        if not keys:
            return rows
        conn = connect(workspace.db)
        try:
            placeholders = ", ".join("?" for _ in keys)
            rows.extend([dict(row) for row in conn.execute(f"SELECT * FROM review_candidates WHERE source_id = ? AND candidate_key IN ({placeholders}) ORDER BY created_at", (candidate.get("source_id"), *keys)).fetchall()])
        finally:
            conn.close()
        return rows

    def concept_markdown_body(*, title: str, summary: str, aliases: list[str], claims: list[str], relations: list[str], source_refs: list[str]) -> str:
        sections = [f"# {title}", "", summary.strip() or "Generated from mapping confirmation."]
        if aliases:
            sections.extend(["", "## Aliases", *[f"- {item}" for item in aliases]])
        if claims:
            sections.extend(["", "## Claims", *[f"- {item}" for item in claims]])
        if relations:
            sections.extend(["", "## Relations", *[f"- {item}" for item in relations]])
        if source_refs:
            sections.extend(["", "## Sources", *[f"- {item}" for item in source_refs]])
        return "\n".join(sections).strip() + "\n"

    def build_mapping_effect(candidate: dict[str, Any], action: str, metadata: dict[str, Any]) -> dict[str, Any]:
        related_rows = candidate_related_rows(candidate)
        related_payloads = {row["candidate_key"]: candidate_payload(row) for row in related_rows}
        primary = candidate_payload(candidate)
        source_id = str(candidate.get("source_id") or "")
        target_concept_id = str(metadata.get("target_concept_id") or primary.get("existing_node_id") or "").strip()
        node_payload = primary
        incoming = primary.get("incoming_ref") if isinstance(primary.get("incoming_ref"), dict) else {}
        if incoming.get("candidate_key") in related_payloads:
            node_payload = related_payloads[str(incoming.get("candidate_key"))]
        claim_keys = list(node_payload.get("evidence_claim_keys") or primary.get("evidence_claim_keys") or [])
        claims: list[str] = []
        for key in claim_keys:
            claim_payload = related_payloads.get(str(key))
            if claim_payload and claim_payload.get("statement"):
                claims.append(str(claim_payload["statement"]))
        title = str(node_payload.get("title") or primary.get("title") or primary.get("candidate_key") or "").strip()
        summary = str(node_payload.get("summary") or primary.get("summary") or primary.get("reason") or "").strip()
        aliases = [str(item).strip() for item in (node_payload.get("aliases") or []) if str(item).strip()]
        effect = {
            "policy": "preview_then_confirm",
            "action": action,
            "surface": metadata.get("surface") or "mapping",
            "step": metadata.get("step") or "page_mapping",
            "source_id": source_id,
            "source_refs": [source_id] if source_id else [],
            "title": title,
            "summary": summary,
            "aliases": aliases,
            "claims": claims,
            "relations": [],
            "target_concept_id": target_concept_id or None,
            "index_status": "pending",
        }
        if action in {"add", "merge"}:
            if not target_concept_id:
                return {**effect, "status": "blocked", "reason": "target_concept_id is required for merge/add preview"}
            effect["status"] = "preview_ready"
            return effect
        if action == "create_new":
            if not title:
                return {**effect, "status": "blocked", "reason": "candidate title is required to create a wiki page"}
            effect["target_concept_id"] = slugify_concept_id(title)
            effect["status"] = "preview_ready"
            return effect
        if action == "edit":
            return {
                **effect,
                "status": "preview_ready",
                "index_status": "queued_manual_review",
                "reason": "manual edit preview recorded; confirm keeps a queued/manual effect",
            }
        return {**effect, "status": "blocked", "reason": f"Unsupported mapping action: {action}"}

    def apply_mapping_effect(candidate: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
        if effect.get("status") != "preview_ready":
            return {**effect, "status": "blocked", "index_status": "blocked"}
        action = str(effect.get("action") or "")
        concept_id = str(effect.get("target_concept_id") or "").strip()
        if action == "edit":
            return {**effect, "status": "queued", "index_status": "queued_manual_review", "applied": False}
        if not concept_id:
            return {**effect, "status": "blocked", "reason": "target concept id is missing", "index_status": "blocked"}
        path = workspace.wiki_concepts / f"{concept_id}.md"
        existing = parse_markdown_sections(path.read_text(encoding="utf-8")) if path.exists() else {"title": slug_title(concept_id), "summary": "", "aliases": [], "claims": [], "relations": [], "sources": []}
        title = str(effect.get("title") or existing.get("title") or slug_title(concept_id)).strip()
        if action == "create_new" and path.exists():
            return {**effect, "status": "blocked", "reason": f"wiki page already exists for {concept_id}", "index_status": "blocked"}
        # FR-3-NO-04: "add" appends without dedup; "merge" dedup-merges into existing.
        # Both still preserve the existing record; the policy distinction is observable in
        # the wiki markdown body (add allows duplicates for raw add-into-wiki intents).
        if action == "add":
            aliases = list([*(existing.get("aliases") or []), *(effect.get("aliases") or [])])
            claims = list([*(existing.get("claims") or []), *(effect.get("claims") or [])])
            relations = list([*(existing.get("relations") or []), *(effect.get("relations") or [])])
            source_refs = list([*(existing.get("sources") or []), *(effect.get("source_refs") or [])])
        else:
            aliases = list(dict.fromkeys([*(existing.get("aliases") or []), *(effect.get("aliases") or [])]))
            claims = list(dict.fromkeys([*(existing.get("claims") or []), *(effect.get("claims") or [])]))
            relations = list(dict.fromkeys([*(existing.get("relations") or []), *(effect.get("relations") or [])]))
            source_refs = list(dict.fromkeys([*(existing.get("sources") or []), *(effect.get("source_refs") or [])]))
        summary = str(effect.get("summary") or existing.get("summary") or "").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            concept_markdown_body(
                title=title,
                summary=summary,
                aliases=aliases,
                claims=claims,
                relations=relations,
                source_refs=source_refs,
            ),
            encoding="utf-8",
        )
        conn = connect(workspace.db)
        try:
            conn.execute(
                "UPDATE sources SET pipeline_stage = 'mapped', review_status = 'completed', updated_at = ? WHERE id = ?",
                (utc_now(), candidate.get("source_id")),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            **effect,
            "status": "applied",
            "applied": True,
            "wiki_path": str(path.relative_to(workspace.root)),
            "index_status": "pending",
            "merge_policy": "append" if action == "add" else "dedup_merge",
        }

    def record_mapping_preview(candidate_id: str, action: str, payload: ReviewDecisionRequest) -> dict[str, Any]:
        candidate = get_candidate_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
        effect = build_mapping_effect(candidate, action, payload.metadata)
        metadata = {
            **payload.metadata,
            "decision_policy": "preview_then_confirm",
            "decision_phase": "preview",
            "effect": effect,
        }
        decision_id = record_human_decision(
            workspace.db,
            candidate_id,
            action,
            note=payload.note,
            metadata=metadata,
            candidate_status="pending",
        )
        artifact = record_artifact(
            workspace,
            artifact_type="mapping_decision_preview",
            task_type="mapping_decision",
            payload={"status": effect.get("status"), "candidate_id": candidate_id, "decision_id": decision_id, "effect": effect},
            target_type="candidate",
            target_id=candidate_id,
        )
        return {
            "status": effect.get("status") or "ok",
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "action": action,
            "effect": effect,
            **artifact,
        }

    def confirm_mapping_decision(candidate_id: str, action: str, payload: ReviewDecisionRequest) -> dict[str, Any]:
        candidate = get_candidate_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
        preview_decision_id = str(payload.metadata.get("preview_decision_id") or "").strip()
        if not preview_decision_id:
            raise HTTPException(status_code=422, detail="preview_decision_id is required before confirming mapping")
        conn = connect(workspace.db)
        try:
            preview_row = conn.execute("SELECT decision_type, metadata_json FROM human_decisions WHERE id = ? AND candidate_id = ?", (preview_decision_id, candidate_id)).fetchone()
        finally:
            conn.close()
        if not preview_row:
            raise HTTPException(status_code=422, detail="Unknown preview decision for candidate")
        preview_meta = read_json_value(preview_row["metadata_json"], {})
        if preview_row["decision_type"] != action or preview_meta.get("decision_phase") != "preview":
            raise HTTPException(status_code=422, detail="Confirm action must match the recorded preview")
        effect = build_mapping_effect(candidate, action, payload.metadata)
        applied = apply_mapping_effect(candidate, effect)
        metadata = {
            **payload.metadata,
            "decision_policy": "preview_then_confirm",
            "decision_phase": "confirm",
            "effect": applied,
        }
        candidate_status = "approved" if applied.get("status") in {"applied", "queued"} else "pending"
        decision_id = record_human_decision(
            workspace.db,
            candidate_id,
            action,
            note=payload.note,
            metadata=metadata,
            candidate_status=candidate_status,
        )
        artifact = record_artifact(
            workspace,
            artifact_type="mapping_decision_effect",
            task_type="mapping_decision",
            payload={"status": applied.get("status"), "candidate_id": candidate_id, "decision_id": decision_id, "effect": applied},
            target_type="candidate",
            target_id=candidate_id,
        )
        return {
            "status": applied.get("status") or "ok",
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "action": action,
            "effect": applied,
            **artifact,
        }

    def db_schema_status() -> tuple[dict[str, Any], sqlite3.Connection | None]:
        inspection = inspect_database(workspace.db)
        if not inspection.get("exists"):
            return {"exists": False, "schema_ok": False, "table_count": 0, "fts5": False, "vec_status": "db_missing"}, None
        conn = connect(workspace.db)
        required_tables = {
            "sources",
            "source_chunks",
            "embeddings",
            "jobs",
            "agent_runs",
            "artifacts",
            "review_candidates",
            "human_decisions",
            "retry_instructions",
            "prompt_versions",
        }
        vec_status = "not_detected"
        try:
            has_vectors = conn.execute("SELECT 1 FROM embeddings WHERE COALESCE(vector_json, '') != '' OR vector_blob IS NOT NULL LIMIT 1").fetchone()
            if has_vectors:
                vec_status = "embedding_vectors_present"
        except sqlite3.DatabaseError:
            vec_status = "unavailable"
        return {
            "exists": True,
            "schema_ok": required_tables.issubset(set(inspection.get("tables") or [])),
            "table_count": len(inspection.get("tables") or []),
            "fts5": bool(inspection.get("fts5")),
            "vec_status": vec_status,
        }, conn

    def job_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
        counts = {"queued": 0, "running": 0, "needs_review": 0, "failed": 0}
        for row in conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall():
            counts[str(row["status"])] = int(row["count"])
        return counts

    def prompt_group_summary() -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in list_prompt_versions(workspace.db):
            group = grouped.setdefault(row["task_type"], {"task_type": row["task_type"], "confirmed": None, "test": None, "history": []})
            group["history"].append(row)
            if row["state"] == "confirmed":
                group["confirmed"] = row
            elif row["state"] == "test":
                group["test"] = row
        return grouped

    def status_component(name: str, status_value: str, detail: str, extra: dict[str, Any] | None = None, *, required: bool = True) -> dict[str, Any]:
        payload = {
            "name": name,
            "status": status_value,
            "detail": detail,
            "required": required,
        }
        if extra:
            payload.update(extra)
        return payload

    def setup_status_payload() -> dict[str, Any]:
        db_info, conn = db_schema_status()
        settings_payload = load_settings(workspace.settings_file)
        llm_settings = settings_payload.get("llm") or {}
        auth = auth_setup_status()
        llm_models = llm_settings.get("models") or {}
        chat_model_name = str(llm_settings.get("default_chat_model") or llm_models.get("chat_default", {}).get("model_name") or "").strip()
        embedding_model_name = str(llm_settings.get("default_embedding_model") or llm_models.get("embedding_default", {}).get("model_name") or "").strip()
        api_key_env = str(llm_settings.get("api_key_env") or "LLM_WIKI_API_KEY")
        api_key_configured = bool(os.environ.get(api_key_env))
        endpoint_configured = bool(str(llm_settings.get("endpoint") or "").strip())
        workspace_initialized = workspace.settings_file.exists() and workspace.vault.exists() and workspace.data.exists()
        vault_ready = workspace.vault.exists() and workspace.vault.is_dir()
        db_ready = bool(db_info["exists"] and db_info["schema_ok"])
        counts = {
            "sources": 0,
            "sources_new": 0,
            "chunks": 0,
            "embeddings": 0,
            "jobs": {"queued": 0, "running": 0, "needs_review": 0, "failed": 0},
            "review_candidates": {"pending": 0},
            "wiki_concepts": len(list_concepts()),
            "prompt_versions": {"confirmed": 0, "test": 0},
        }
        try:
            if conn is not None:
                counts["sources"] = int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
                counts["sources_new"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM sources WHERE COALESCE(pipeline_stage, 'created') IN ('created', 'new')"
                    ).fetchone()[0]
                )
                counts["chunks"] = int(conn.execute("SELECT COUNT(*) FROM source_chunks").fetchone()[0])
                counts["embeddings"] = int(conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
                counts["jobs"] = job_status_counts(conn)
                counts["review_candidates"]["pending"] = int(conn.execute("SELECT COUNT(*) FROM review_candidates WHERE status = 'pending'").fetchone()[0])
                for row in conn.execute("SELECT state, COUNT(*) AS count FROM prompt_versions GROUP BY state").fetchall():
                    if row["state"] in {"confirmed", "test"}:
                        counts["prompt_versions"][str(row["state"])] = int(row["count"])
        finally:
            if conn is not None:
                conn.close()
        next_actions: list[dict[str, Any]] = []
        if not auth["configured"]:
            next_actions.append({"id": "set-web-password", "label": "Configure web admin password", "command_or_path": workspace.env_file.name, "priority": "high"})
        if not llm_settings.get("endpoint"):
            next_actions.append({"id": "configure-llm-endpoint", "label": "Configure LLM endpoint", "command_or_path": "/settings?tab=llm", "priority": "high"})
        if counts["sources"] == 0:
            next_actions.append({"id": "ingest-first-source", "label": "Ingest your first source", "command_or_path": "wiki ingest <markdown>", "priority": "high"})
        if counts["review_candidates"]["pending"] > 0:
            next_actions.append({"id": "review-pending", "label": "Review pending candidates", "command_or_path": "/review", "priority": "medium"})
        if counts["wiki_concepts"] > 0:
            next_actions.append({"id": "browse-wiki", "label": "Browse wiki content", "command_or_path": "/wiki", "priority": "medium"})
        components = {
            "auth": status_component(
                "auth",
                "ready" if auth["configured"] else "missing_config",
                "Web admin password configured" if auth["configured"] else auth["message"],
            ),
            "workspace": status_component(
                "workspace",
                "ready" if workspace_initialized else "missing_config",
                "Workspace settings, vault, and data paths are present" if workspace_initialized else "Workspace directories are not fully initialized",
            ),
            "database": status_component(
                "database",
                "ready" if db_ready else ("missing_config" if not db_info["exists"] else "blocked"),
                "Database schema is ready" if db_ready else ("Database file is missing" if not db_info["exists"] else "Database schema is incomplete"),
            ),
            "vault": status_component(
                "vault",
                "ready" if vault_ready else "missing_config",
                f"Vault path ready: {workspace.vault}" if vault_ready else "Vault path is missing or not a directory",
            ),
            "llm_endpoint": status_component(
                "llm_endpoint",
                "ready" if endpoint_configured else "missing_config",
                "LLM endpoint configured" if endpoint_configured else "LLM endpoint is not configured",
            ),
            "llm_api_key": status_component(
                "llm_api_key",
                "ready" if api_key_configured else "missing_config",
                f"API key available via {api_key_env}" if api_key_configured else f"Set {api_key_env} before testing the LLM connection",
            ),
            "llm_chat_model": status_component(
                "llm_chat_model",
                "ready" if bool(chat_model_name) else "missing_config",
                f"Chat model selected: {chat_model_name}" if chat_model_name else "Chat model is not selected",
            ),
            "llm_embedding_model": status_component(
                "llm_embedding_model",
                "ready" if bool(embedding_model_name) else "missing_config",
                f"Embedding model selected: {embedding_model_name}" if embedding_model_name else "Embedding model is not selected",
            ),
        }
        llm_config_ready = all(
            components[key]["status"] == "ready"
            for key in ["llm_endpoint", "llm_api_key", "llm_chat_model", "llm_embedding_model"]
        )
        chat_test = latest_model_test_status("chat_default") if chat_model_name else {"test_status": "blocked", "reason": "chat model is not configured"}
        embedding_test = latest_model_test_status("embedding_default") if embedding_model_name else {"test_status": "blocked", "reason": "embedding model is not configured"}
        llm_connection_ready = llm_config_ready and chat_test["test_status"] == "passed" and embedding_test["test_status"] == "passed"
        components["llm_connection"] = status_component(
            "llm_connection",
            "ready" if llm_connection_ready else "blocked",
            "LLM connection tests passed" if llm_connection_ready else "LLM connection requires passed chat and embedding model tests",
            {
                "test_status": "passed" if llm_connection_ready else "blocked",
                "chat_test_status": chat_test["test_status"],
                "embedding_test_status": embedding_test["test_status"],
                "chat_reason": chat_test.get("reason"),
                "embedding_reason": embedding_test.get("reason"),
            },
        )
        required_components = [
            "auth",
            "workspace",
            "database",
            "vault",
            "llm_endpoint",
            "llm_api_key",
            "llm_chat_model",
            "llm_embedding_model",
            "llm_connection",
        ]
        setup_complete = all(components[name]["status"] == "ready" for name in required_components)
        return {
            "workspace_initialized": workspace_initialized,
            "db_exists": db_info["exists"],
            "db_schema_ok": db_info["schema_ok"],
            "db_table_count": db_info["table_count"],
            "db_fts5": db_info["fts5"],
            "db_vec_status": db_info["vec_status"],
            "needs_onboarding": not setup_complete,
            "setup_complete": setup_complete,
            "onboarding_path": "/onboarding",
            "dashboard_path": "/dashboard",
            "completion_policy": "connection_test_passed",
            "web_admin_password_configured": auth["configured"],
            "llm": {
                "provider": str(llm_models.get("chat_default", {}).get("provider") or llm_models.get("embedding_default", {}).get("provider") or ""),
                "endpoint": str(llm_settings.get("endpoint") or ""),
                "endpoint_configured": endpoint_configured,
                "chat_model": chat_model_name,
                "chat_model_configured": bool(chat_model_name),
                "embedding_model": embedding_model_name,
                "embedding_model_configured": bool(embedding_model_name),
                "api_key_env": api_key_env,
                "api_key_configured": api_key_configured,
                "connection_status": components["llm_connection"]["status"],
                "connection_test_status": components["llm_connection"].get("test_status"),
                "connection_ok": llm_connection_ready,
                "status": "ready" if llm_connection_ready else "missing_config",
            },
            "vault": {
                "path": str(workspace.vault),
                "status": components["vault"]["status"],
            },
            "vault_path": str(workspace.vault),
            "data_path": str(workspace.data),
            "env_file_exists": workspace.env_file.exists(),
            "counts": counts,
            "components": components,
            "next_actions": next_actions,
        }

    def post_login_redirect_path() -> str:
        return "/onboarding" if setup_status_payload()["needs_onboarding"] else "/dashboard"

    def enforce_setup_page_access(current_path: str, *, allow_incomplete: bool = False, allow_complete: bool = True) -> RedirectResponse | None:
        setup = setup_status_payload()
        # FR-3-NO-01 / Contract A: authenticated users with incomplete setup must
        # be routed through Onboarding before accessing protected operational
        # pages. Settings remains separately accessible so configuration can be
        # completed.
        if setup["needs_onboarding"] and not allow_incomplete:
            return RedirectResponse(url=setup["onboarding_path"], status_code=303)
        if setup["setup_complete"] and not allow_complete:
            return RedirectResponse(url=setup["dashboard_path"], status_code=303)
        return None

    def tokenize(text: str) -> set[str]:
        return {token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token}

    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def mean_vectors(vectors: list[list[float]]) -> list[float]:
        if not vectors:
            return []
        width = len(vectors[0])
        if any(len(vector) != width for vector in vectors):
            return []
        return [sum(vector[idx] for vector in vectors) / len(vectors) for idx in range(width)]

    def embedding_vectors(conn: sqlite3.Connection, *, target_type: str, target_ids: list[str]) -> dict[str, list[float]]:
        if not target_ids:
            return {}
        placeholders = ", ".join("?" for _ in target_ids)
        rows = conn.execute(
            f"SELECT target_id, vector_json FROM embeddings WHERE target_type = ? AND target_id IN ({placeholders}) AND COALESCE(vector_json, '') != ''",
            (target_type, *target_ids),
        ).fetchall()
        grouped: dict[str, list[list[float]]] = {}
        for row in rows:
            try:
                vector = json.loads(row["vector_json"])
            except json.JSONDecodeError:
                continue
            if isinstance(vector, list) and all(isinstance(item, (int, float)) for item in vector):
                grouped.setdefault(str(row["target_id"]), []).append([float(item) for item in vector])
        return {target_id: mean_vectors(vectors) for target_id, vectors in grouped.items() if vectors}

    def candidate_similarity_rows(source_candidate_id: str) -> list[dict[str, Any]]:
        candidate = get_candidate_by_id(source_candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {source_candidate_id}")
        concepts = list_concepts()
        if not concepts:
            return []
        payload = candidate_payload(candidate)
        evidence_refs = collect_evidence_refs(payload)[:3]
        conn = connect(workspace.db)
        try:
            candidate_vector: list[float] = []
            if candidate.get("source_id"):
                chunk_ids = [str(row["id"]) for row in conn.execute("SELECT id FROM source_chunks WHERE source_id = ? ORDER BY chunk_index", (candidate["source_id"],)).fetchall()]
                chunk_vectors = embedding_vectors(conn, target_type="source_chunk", target_ids=chunk_ids)
                candidate_vector = mean_vectors(list(chunk_vectors.values()))
            concept_vectors = embedding_vectors(conn, target_type="concept", target_ids=[item["id"] for item in concepts])
        finally:
            conn.close()
        rows: list[dict[str, Any]] = []
        if candidate_vector and concept_vectors:
            for concept in concepts:
                rows.append(
                    {
                        "concept_id": concept["id"],
                        "title": concept["title"],
                        "score": round(cosine_similarity(candidate_vector, concept_vectors.get(concept["id"], [])), 4),
                        "top_evidence_refs": evidence_refs,
                    }
                )
            return sorted(rows, key=lambda item: item["score"], reverse=True)
        candidate_tokens = tokenize(" ".join(str(payload.get(key) or "") for key in ("title", "summary", "candidate_key")))
        for concept in concepts:
            concept_tokens = tokenize(" ".join([concept["title"], concept["id"], *(concept.get("aliases") or [])]))
            union = candidate_tokens | concept_tokens
            score = len(candidate_tokens & concept_tokens) / len(union) if union else 0.0
            rows.append({"concept_id": concept["id"], "title": concept["title"], "score": round(score, 4), "top_evidence_refs": evidence_refs})
        return sorted(rows, key=lambda item: (item["score"], item["title"]), reverse=True)

    def candidate_detail(candidate_id: str) -> dict[str, Any]:
        candidate = get_candidate_by_id(candidate_id)
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
        conn = connect(workspace.db)
        try:
            source = None
            if candidate.get("source_id"):
                row = conn.execute("SELECT id, title, pipeline_stage, normalized_path FROM sources WHERE id = ?", (candidate["source_id"],)).fetchone()
                source = dict(row) if row else {"id": candidate["source_id"]}
            run = None
            if candidate.get("run_id"):
                row = conn.execute("SELECT id, job_id, agent_type, provider, model, task_type, status, started_at, finished_at FROM agent_runs WHERE id = ?", (candidate["run_id"],)).fetchone()
                run = dict(row) if row else {"id": candidate["run_id"]}
            related = []
            keys = related_candidate_keys(candidate)
            if keys:
                placeholders = ", ".join("?" for _ in keys)
                related = [json_for_candidate(dict(row)) for row in conn.execute(f"SELECT * FROM review_candidates WHERE candidate_key IN ({placeholders}) ORDER BY created_at", tuple(keys)).fetchall()]
            decisions = [
                {
                    **dict(row),
                    "metadata": read_json_value(row["metadata_json"], {}),
                }
                for row in conn.execute(
                    "SELECT * FROM human_decisions WHERE candidate_id = ? ORDER BY decided_at DESC",
                    (candidate_id,),
                ).fetchall()
            ]
        finally:
            conn.close()
        item = json_for_candidate(candidate)
        return {
            **item,
            "source": source,
            "run": run,
            "related_candidates": related,
            "decisions": decisions,
            "latest_effect": decisions[0]["metadata"].get("effect") if decisions else None,
            "evidence_refs": collect_evidence_refs(item.get("payload") or {}),
        }

    def masked_llm_status() -> dict[str, Any]:
        raw = load_settings(workspace.settings_file)
        llm_settings = raw.get("llm") or {}
        safe_settings = mask_sensitive(llm_settings)
        if "api_key_env" in llm_settings:
            # api_key_env is the non-secret environment variable name; the value of
            # that variable is never returned by the Web API.
            safe_settings["api_key_env"] = llm_settings["api_key_env"]
        return {
            "models": list_models(workspace).get("models", []),
            "routes": get_route_map(workspace).get("routes", {}),
            "settings": safe_settings,
            "missing": {
                "endpoint_missing": not bool(llm_settings.get("endpoint")),
                "api_key_missing": not bool(os.environ.get(str(llm_settings.get("api_key_env") or "LLM_WIKI_API_KEY"))),
                "chat_model_missing": not bool(llm_settings.get("default_chat_model") or (llm_settings.get("models") or {}).get("chat_default", {}).get("model_name")),
                "embedding_model_missing": not bool(llm_settings.get("default_embedding_model") or (llm_settings.get("models") or {}).get("embedding_default", {}).get("model_name")),
            },
        }

    def persist_workspace_secret(env_name: str, secret_value: str, *, remove_names: list[str] | None = None) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
            raise HTTPException(status_code=422, detail="Invalid api_key_env")
        existing_lines = workspace.env_file.read_text(encoding="utf-8").splitlines() if workspace.env_file.exists() else []
        remove_set = {name for name in (remove_names or []) if name and name != env_name}
        escaped = secret_value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        rendered = f'{env_name}="{escaped}"'
        updated_lines: list[str] = []
        wrote_target = False
        for line in existing_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                updated_lines.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in remove_set:
                continue
            if key == env_name:
                if not wrote_target:
                    updated_lines.append(rendered)
                    wrote_target = True
                continue
            updated_lines.append(line)
        if not wrote_target:
            if updated_lines and updated_lines[-1].strip():
                updated_lines.append("")
            updated_lines.append(rendered)
        workspace.env_file.parent.mkdir(parents=True, exist_ok=True)
        workspace.env_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        os.environ[env_name] = secret_value
        for name in remove_set:
            os.environ.pop(name, None)

    def update_llm_config(payload: LlmConfigUpdateRequest) -> dict[str, Any]:
        settings_data = load_settings(workspace.settings_file, resolve_env=False)
        llm = settings_data.setdefault("llm", {})
        previous_api_key_env = str(llm.get("api_key_env") or "LLM_WIKI_API_KEY")
        endpoint = payload.endpoint.strip()
        api_key_env = payload.api_key_env.strip() or previous_api_key_env
        api_key = (payload.api_key or "").strip()
        models = llm.setdefault("models", {})
        chat = models.setdefault("chat_default", {})
        embedding = models.setdefault("embedding_default", {})
        chat_model = payload.default_chat_model.strip() or str(llm.get("default_chat_model") or chat.get("model_name") or "").strip()
        embedding_model = payload.default_embedding_model.strip() or str(llm.get("default_embedding_model") or embedding.get("model_name") or "").strip()
        chat_model_name = payload.chat_model_name.strip() or chat_model
        embedding_model_name = payload.embedding_model_name.strip() or embedding_model
        if api_key:
            persist_workspace_secret(api_key_env, api_key, remove_names=[previous_api_key_env])
        elif api_key_env != previous_api_key_env:
            previous_api_key = os.environ.get(previous_api_key_env, "").strip()
            if previous_api_key:
                persist_workspace_secret(api_key_env, previous_api_key, remove_names=[previous_api_key_env])
        llm["endpoint"] = endpoint
        llm["api_key_env"] = api_key_env
        llm["default_chat_model"] = chat_model
        llm["default_embedding_model"] = embedding_model
        chat.update({
            "id": "chat_default",
            "provider": chat.get("provider") or "generic_openai_compatible",
            "capability": "chat",
            "endpoint": endpoint,
            "api_key_env": api_key_env,
            "model_name": chat_model_name,
            "request_format": chat.get("request_format") or "openai_chat",
        })
        embedding.update({
            "id": "embedding_default",
            "provider": embedding.get("provider") or "generic_openai_compatible",
            "capability": "embedding",
            "endpoint": endpoint,
            "api_key_env": api_key_env,
            "model_name": embedding_model_name,
            "request_format": embedding.get("request_format") or "openai_embeddings",
        })
        save_settings(workspace.settings_file, settings_data)
        record_artifact(
            workspace,
            artifact_type="settings_change",
            task_type="web_settings_llm_update",
            payload={
                "status": "ok",
                "changed": ["llm.endpoint", "llm.api_key_env", "llm.default_chat_model", "llm.default_embedding_model"],
                "api_key_value_stored": False,
            },
            target_type="settings",
            target_id="llm",
        )
        return masked_llm_status()

    def update_vault_config(payload: VaultConfigUpdateRequest) -> dict[str, Any]:
        settings_data = load_settings(workspace.settings_file, resolve_env=False)
        vault_rel = payload.vault_path.strip() or "vault"
        data_rel = payload.data_path.strip() or "data"
        for raw in (vault_rel, data_rel):
            p = Path(raw)
            if p.is_absolute() or ".." in p.parts:
                raise HTTPException(status_code=422, detail="Vault/data paths must be relative workspace paths")
        paths = settings_data.setdefault("paths", {})
        paths["vault"] = vault_rel
        paths["data"] = data_rel
        paths["db"] = f"{data_rel.rstrip('/')}/wiki.sqlite"
        paths["raw"] = f"{data_rel.rstrip('/')}/raw"
        paths["normalized"] = f"{data_rel.rstrip('/')}/normalized"
        paths["artifacts"] = f"{data_rel.rstrip('/')}/artifacts"
        paths["exports"] = f"{data_rel.rstrip('/')}/exports"
        paths["cache"] = f"{data_rel.rstrip('/')}/cache"
        paths["settings"] = f"{vault_rel.rstrip('/')}/90_Settings/settings.yaml"
        settings_data.setdefault("workspace", {})["human_vault"] = vault_rel
        settings_data.setdefault("workspace", {})["system_data"] = data_rel
        save_settings(workspace.settings_file, settings_data)
        created: list[str] = []
        if payload.create_missing:
            for rel in [vault_rel, data_rel]:
                target = workspace.root / rel
                target.mkdir(parents=True, exist_ok=True)
                created.append(str(target.relative_to(workspace.root)))
        record_artifact(
            workspace,
            artifact_type="settings_change",
            task_type="web_setup_vault_update",
            payload={"status": "ok", "vault_path": vault_rel, "data_path": data_rel, "created": created},
            target_type="settings",
            target_id="vault",
        )
        return {"vault_path": str(workspace.root / vault_rel), "data_path": str(workspace.root / data_rel), "created": created}

    def dashboard_metrics() -> dict[str, Any]:
        setup = setup_status_payload()
        conn = connect(workspace.db)
        try:
            review_pending = conn.execute("SELECT COUNT(*) FROM review_candidates WHERE status = 'pending'").fetchone()[0]
            pending_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'running', 'needs_review')").fetchone()[0]
            errors = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'failed'").fetchone()[0]
            source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            # FR-3-NO-08: explicit pending source count and warning messages so the
            # dashboard JS can render Needs Attention without silent zero fallbacks.
            pending_sources = conn.execute(
                "SELECT COUNT(*) FROM sources WHERE COALESCE(pipeline_stage, 'created') IN ('created', 'new')"
            ).fetchone()[0]
        finally:
            conn.close()
        inspection = inspect_database(workspace.db)
        concepts = list_concepts()
        # FR-3-NO-08: derive LLM/Vault warning strings from setup components.
        llm_warning = None
        llm_conn = setup.get("components", {}).get("llm_connection") or {}
        if not setup.get("llm", {}).get("endpoint_configured"):
            llm_warning = "LLM endpoint not configured."
        elif llm_conn.get("test_status") in {"failed", "blocked"}:
            reason = llm_conn.get("detail") or llm_conn.get("chat_reason") or llm_conn.get("embedding_reason")
            llm_warning = f"LLM connection {llm_conn.get('test_status')}: {reason or 'see Settings'}."
        vault_warning = None
        if setup.get("vault", {}).get("status") != "ready":
            vault_warning = "Vault path is missing or unreadable."
        return {
            "review_pending": review_pending,
            "pending_jobs": pending_jobs,
            "errors": errors,
            "wiki_count": len(concepts),
            "source_count": source_count,
            "pending_sources": pending_sources,
            "needs_onboarding": setup["needs_onboarding"],
            "setup_complete": setup["setup_complete"],
            "llm_status": setup["llm"]["status"],
            "llm_warning": llm_warning,
            "vault_status": setup["vault"]["status"],
            "vault_ready": setup["vault"]["status"] == "ready",
            "vault_warning": vault_warning,
            "provider": setup["llm"].get("provider") or "—",
            "chat_model": setup["llm"].get("chat_model") or "—",
            "embedding_model": setup["llm"].get("embedding_model") or "—",
            "vault_path": setup["vault_path"],
            "db_status": {"exists": inspection["exists"], "fts5": inspection["fts5"], "table_count": len(inspection["tables"])} ,
            "system_status": {"workspace_ready": workspace.settings_file.exists() and workspace.db.exists(), "auth": auth_setup_status()},
        }

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> HTMLResponse:
        return RedirectResponse(url=post_login_redirect_path() if is_authenticated(request) else "/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, error: str | None = None) -> HTMLResponse:
        if is_authenticated(request):
            return RedirectResponse(url=post_login_redirect_path(), status_code=303)
        return render_page(request, "login.html", {"error": error})

    @app.post("/login", response_class=HTMLResponse)
    def login(request: Request, password: str = Form(...)) -> HTMLResponse:
        setup = auth_setup_status()
        if not setup["configured"]:
            return render_page(request, "login.html", {"error": setup["message"]}, status_code=503)
        if not hmac.compare_digest(password, admin_password()):
            return render_page(request, "login.html", {"error": "Invalid password"}, status_code=401)
        expires_at = int(time.time()) + session_ttl_seconds()
        response = RedirectResponse(url=post_login_redirect_path(), status_code=303)
        response.set_cookie(session_cookie_name(), sign_session(expires_at), httponly=True, samesite="lax", max_age=session_ttl_seconds())
        return response

    @app.post("/logout")
    def logout() -> RedirectResponse:
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(session_cookie_name())
        return response

    @app.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def dashboard_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/dashboard"):
            return redirect
        return render_page(request, "dashboard.html", {"page": "dashboard"})

    @app.get("/onboarding", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def onboarding_page(request: Request) -> HTMLResponse:
        setup = setup_status_payload()
        if redirect := enforce_setup_page_access("/onboarding", allow_incomplete=True, allow_complete=False):
            return redirect
        return render_page(request, "onboarding.html", {"page": "onboarding", "setup": setup})

    @app.get("/wiki", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def wiki_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/wiki"):
            return redirect
        return render_page(request, "wiki.html", {"page": "wiki"})

    @app.get("/wiki/{concept_id}", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def wiki_detail_page(request: Request, concept_id: str) -> HTMLResponse:
        if redirect := enforce_setup_page_access(f"/wiki/{concept_id}"):
            return redirect
        return render_page(request, "wiki.html", {"page": "wiki", "initial_concept_id": concept_id, "initial_concept": concept_detail(concept_id)})

    @app.get("/inbox", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def inbox_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/inbox"):
            return redirect
        return render_page(request, "inbox.html", {"page": "inbox"})

    @app.get("/mapping", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def mapping_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/mapping"):
            return redirect
        return render_page(request, "mapping.html", {"page": "mapping"})

    @app.get("/vault", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def vault_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/vault"):
            return redirect
        return render_page(request, "vault.html", {"page": "vault"})

    @app.get("/review", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def review_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/review"):
            return redirect
        return render_page(request, "review.html", {"page": "mapping", "legacy_route": True})

    @app.get("/search", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def search_page(request: Request) -> HTMLResponse:
        if redirect := enforce_setup_page_access("/search"):
            return redirect
        return render_page(request, "search.html", {"page": "search"})

    @app.get("/settings", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    def settings_page(request: Request, tab: str | None = None) -> HTMLResponse:
        allowed_tabs = {"llm", "prompt", "vault", "auth"}
        active_tab = tab if tab in allowed_tabs else "llm"
        return render_page(request, "settings.html", {"page": "settings", "active_tab": active_tab})

    @app.get("/api/setup/status", dependencies=[Depends(require_auth)])
    def api_setup_status() -> dict[str, Any]:
        return {"status": "ok", **setup_status_payload()}

    @app.post("/api/setup/llm", dependencies=[Depends(require_auth)])
    def api_setup_llm(payload: LlmConfigUpdateRequest) -> dict[str, Any]:
        return {"status": "ok", **update_llm_config(payload)}

    @app.post("/api/setup/vault", dependencies=[Depends(require_auth)])
    def api_setup_vault(payload: VaultConfigUpdateRequest) -> dict[str, Any]:
        return {"status": "ok", **update_vault_config(payload)}

    @app.get("/api/setup/vault/detect-structure", dependencies=[Depends(require_auth)])
    def api_setup_vault_detect_structure(path: str) -> dict[str, Any]:
        selected_path, rel_path = sanitize_workspace_relative_path(path, allow_root=True)
        if not selected_path.exists() or not selected_path.is_dir():
            raise HTTPException(status_code=404, detail="Vault folder not found")
        role_map, missing_roles = detect_vault_role_map(selected_path)
        return {
            "status": "ok",
            "path": rel_path,
            "role_map": role_map,
            "missing_roles": missing_roles,
            "message": "Vault structure detection completed",
        }

    @app.post("/api/setup/vault/create", dependencies=[Depends(require_auth)])
    def api_setup_vault_create(payload: VaultCreateRequest) -> dict[str, Any]:
        parent_path, parent_rel = sanitize_workspace_browse_path(payload.parent_path)
        if not parent_path.exists() or not parent_path.is_dir():
            raise HTTPException(status_code=404, detail="Parent folder not found")
        vault_name = (payload.vault_name or "llm-wiki").strip()
        if not vault_name or vault_name.startswith(".") or Path(vault_name).name != vault_name:
            raise HTTPException(status_code=422, detail="Invalid vault_name")
        vault_path = (parent_path / vault_name).resolve()
        if not is_path_under_directory(vault_path, browse_root):
            raise HTTPException(status_code=422, detail="Path traversal blocked")
        created: list[str] = []
        for folder in [
            vault_path,
            vault_path / "00_Inbox",
            vault_path / "00_Inbox" / "files",
            vault_path / "00_Inbox" / "memo",
            vault_path / "00_Inbox" / "text",
            vault_path / "10_Wiki",
            vault_path / "10_Wiki" / "concepts",
            vault_path / "10_Wiki" / "sources",
            vault_path / "10_Wiki" / "claims",
            vault_path / "10_Wiki" / "pages",
            vault_path / "20_Review",
            vault_path / "20_Review" / "candidates",
            vault_path / "20_Review" / "mapping",
            vault_path / "20_Review" / "rejected",
            vault_path / "80_Raws",
            vault_path / "90_Settings",
        ]:
            existed = folder.exists()
            folder.mkdir(parents=True, exist_ok=True)
            if not existed:
                created.append(home_relative_str(folder))
        vault_rel = home_relative_str(vault_path)
        role_map = {
            "inbox": f"{vault_rel}/00_Inbox",
            "wiki": f"{vault_rel}/10_Wiki",
            "review": f"{vault_rel}/20_Review",
            "raws": f"{vault_rel}/80_Raws",
            "settings": f"{vault_rel}/90_Settings",
        }
        apply_vault_role_mapping(vault_rel, role_map)
        record_artifact(
            workspace,
            artifact_type="vault_create",
            task_type="web_setup_vault_create",
            payload={"status": "ok", "parent_path": parent_rel, "vault_path": vault_rel, "created": created, "role_map": role_map},
            target_type="settings",
            target_id="vault_create",
        )
        return {"status": "ok", "parent_path": parent_rel, "vault_path": vault_rel, "created": created, "role_map": role_map, "message": "Vault created"}

    @app.post("/api/setup/vault/mapping", dependencies=[Depends(require_auth)])
    def api_setup_vault_mapping(payload: VaultMappingRequest) -> dict[str, Any]:
        vault_path, vault_rel = sanitize_workspace_relative_path(payload.vault_path)
        if not vault_path.exists() or not vault_path.is_dir():
            raise HTTPException(status_code=404, detail="Vault folder not found")
        normalized_role_map: dict[str, str] = {}
        for role, raw_path in payload.role_map.items():
            target_path, rel_path = sanitize_workspace_relative_path(raw_path)
            if role in {"inbox", "wiki", "review", "raws", "settings"} and not is_path_under_directory(target_path, vault_path):
                raise HTTPException(status_code=422, detail=f"Role {role} must stay under the selected vault")
            if role == "artifacts" and "data" in payload.role_map:
                data_path, _ = sanitize_workspace_relative_path(payload.role_map["data"])
                if not is_path_under_directory(target_path, data_path):
                    raise HTTPException(status_code=422, detail="Artifacts path must stay under data path")
            normalized_role_map[role] = rel_path
        apply_vault_role_mapping(vault_rel, normalized_role_map)
        record_artifact(
            workspace,
            artifact_type="vault_mapping",
            task_type="web_setup_vault_mapping",
            payload={"status": "ok", "vault_path": vault_rel, "role_map": normalized_role_map},
            target_type="settings",
            target_id="vault_mapping",
        )
        return {"status": "ok", "vault_path": vault_rel, "role_map": normalized_role_map, "message": "Vault mapping saved"}

    @app.get("/api/setup/fs/browse", dependencies=[Depends(require_auth)])
    def api_setup_fs_browse(path: str | None = None) -> dict[str, Any]:
        browse_path, rel_path = sanitize_workspace_browse_path(path)
        if not browse_path.exists() or not browse_path.is_dir():
            raise HTTPException(status_code=404, detail="Browse folder not found")
        entries = []
        for entry in list_dir_or_403(browse_path, relative_to=browse_root):
            if str(entry["name"]).startswith("."):
                continue
            child = browse_path / entry["name"]
            if child.is_symlink():
                continue
            kind = "folder" if entry["is_dir"] else "file"
            rel_child = home_relative_str(child)
            entries.append({
                "name": entry["name"],
                "path": rel_child,
                "is_dir": entry["is_dir"],
                "kind": kind,
            })
        return {
            "status": "ok",
            "path": rel_path,
            "display_path": rel_path,
            "root": "~",
            "can_go_parent": browse_path != browse_root,
            "parent_path": home_relative_str(browse_path.parent) if browse_path != browse_root else None,
            "entries": entries,
            "folders": [entry for entry in entries if entry["is_dir"]],
        }

    @app.get("/api/dashboard/metrics", dependencies=[Depends(require_auth)])
    def api_dashboard_metrics() -> dict[str, Any]:
        return {"status": "ok", **dashboard_metrics()}

    @app.get("/api/search", dependencies=[Depends(require_auth)])
    def api_search(q: str, limit: int = 10, mode: str = "combined") -> dict[str, Any]:
        if mode not in SEARCH_MODES:
            raise HTTPException(status_code=422, detail=f"Unsupported search mode: {mode}")
        try:
            return search_workspace(workspace, q, limit=limit, mode=mode)
        except Exception:
            raise HTTPException(status_code=500, detail="Search failed") from None

    @app.post("/api/ask", dependencies=[Depends(require_auth)])
    def api_ask(payload: AskRequest) -> dict[str, Any]:
        try:
            _exit_code, result = run_ask(SimpleNamespace(path=str(workspace.root), query=payload.query))
        except Exception:
            raise HTTPException(status_code=500, detail="Ask failed") from None
        return {
            "status": result["status"],
            "query": result["query"],
            "answer": result["answer"],
            "evidence_refs": result["evidence_refs"],
            "search_metadata": result["search_metadata"],
            "prompt_version_id": result.get("prompt_version_id"),
            "artifact_id": result.get("artifact_id"),
            "run_id": result.get("run_id"),
            "message": result["message"],
        }

    @app.get("/api/dashboard/summary", dependencies=[Depends(require_auth)])
    def api_dashboard_summary() -> dict[str, Any]:
        return {"status": "ok", **dashboard_summary(), **dashboard_metrics()}

    @app.get("/api/dashboard/needs-attention", dependencies=[Depends(require_auth)])
    def api_dashboard_needs_attention(limit: int = 10) -> dict[str, Any]:
        summary = dashboard_summary()
        items: list[dict[str, Any]] = []
        conn = connect(workspace.db)
        try:
            for row in conn.execute("SELECT * FROM jobs WHERE status = 'failed' ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall():
                error_payload = read_json_value(row["error_json"], {})
                items.append({
                    "kind": "job_failed",
                    "label": "Inbox processing failed",
                    "target": f"/inbox?item={row['target_id']}",
                    "target_id": row["target_id"],
                    "summary": error_payload.get("reason") if isinstance(error_payload, dict) else row["job_type"],
                    "created_at": row["created_at"],
                })
            for row in conn.execute("SELECT * FROM review_candidates WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall():
                items.append({
                    "kind": "mapping_pending",
                    "label": "Mapping candidate pending",
                    "target": f"/mapping?candidate_id={row['id']}",
                    "target_id": row["id"],
                    "summary": row["candidate_key"],
                    "created_at": row["created_at"],
                })
        finally:
            conn.close()
        if not summary["system"]["llm"]["endpoint_configured"]:
            items.append({"kind": "llm_warning", "label": "LLM setup warning", "target": "/settings?tab=llm", "summary": "Endpoint is not configured"})
        return {"status": "ok", "count": len(items[:limit]), "items": items[:limit]}

    @app.get("/api/dashboard/system-status", dependencies=[Depends(require_auth)])
    def api_dashboard_system_status() -> dict[str, Any]:
        summary = dashboard_summary()
        return {"status": "ok", **summary["system"], "vault": summary["vault"]}

    @app.get("/api/dashboard/recent-activity", dependencies=[Depends(require_auth)])
    def api_dashboard_recent_activity(limit: int = 10) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            decisions = [dict(row) for row in conn.execute("SELECT * FROM human_decisions ORDER BY decided_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall()]
            artifacts = [dict(row) for row in conn.execute("SELECT * FROM artifacts ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall()]
        finally:
            conn.close()
        rows = [
            {"kind": "decision", "at": row["decided_at"], "label": row["decision_type"], "target_id": row["candidate_id"]}
            for row in decisions
        ]
        rows.extend(
            {"kind": "artifact", "at": row["created_at"], "label": row["artifact_type"], "target_id": row.get("target_id")}
            for row in artifacts
        )
        rows.sort(key=lambda item: item.get("at") or "", reverse=True)
        return {"status": "ok", "count": len(rows[:limit]), "items": rows[:limit]}

    @app.get("/api/dashboard/sources", dependencies=[Depends(require_auth)])
    def api_dashboard_sources(limit: int = 10) -> dict[str, Any]:
        stage_counts = {stage: 0 for stage in ["created", "ingested", "normalized", "chunked", "embedded", "candidate_generated", "synced", "failed"]}
        conn = connect(workspace.db)
        try:
            for row in conn.execute("SELECT pipeline_stage, COUNT(*) AS count FROM sources GROUP BY pipeline_stage").fetchall():
                stage_counts[str(row["pipeline_stage"])] = int(row["count"])
            recent = [dict(row) for row in conn.execute("SELECT id, title, source_type, pipeline_stage, review_status, created_at, updated_at FROM sources ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall()]
        finally:
            conn.close()
        return {"status": "ok", "stage_counts": stage_counts, "recent": recent}

    @app.get("/api/dashboard/jobs", dependencies=[Depends(require_auth)])
    def api_dashboard_jobs(limit: int = 10) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            counts = job_status_counts(conn)
            recent = []
            for row in conn.execute("SELECT id, job_type, target_type, target_id, status, created_at, started_at, finished_at, error_json FROM jobs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall():
                item = dict(row)
                item["error"] = json.loads(item.pop("error_json") or "null")
                recent.append(item)
        finally:
            conn.close()
        return {"status": "ok", "status_counts": counts, "recent": recent}

    @app.get("/api/dashboard/errors", dependencies=[Depends(require_auth)])
    def api_dashboard_errors(limit: int = 10) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            rows = []
            for row in conn.execute("SELECT id, target_type, target_id, status, started_at, error_json FROM jobs WHERE status IN ('failed', 'needs_review') ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall():
                error_payload = json.loads(row["error_json"] or "{}")
                masked_error = mask_sensitive(error_payload)
                rows.append({"id": row["id"], "target": f"{row['target_type'] or 'unknown'}:{row['target_id'] or ''}".rstrip(":"), "status": row["status"], "started_at": row["started_at"], "error_summary": masked_error.get("reason") if isinstance(masked_error, dict) else masked_error})
        finally:
            conn.close()
        return {"status": "ok", "count": len(rows), "errors": rows}

    @app.get("/api/dashboard/review", dependencies=[Depends(require_auth)])
    def api_dashboard_review(limit: int = 10) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            by_type = Counter()
            by_route = Counter()
            for row in conn.execute("SELECT candidate_type, review_route FROM review_candidates WHERE status = 'pending'").fetchall():
                by_type[str(row["candidate_type"])] += 1
                by_route[str(row["review_route"])] += 1
            rows = [json_for_candidate(dict(row)) for row in conn.execute("SELECT * FROM review_candidates WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 50)),)).fetchall()]
        finally:
            conn.close()
        return {"status": "ok", "pending_by_candidate_type": dict(by_type), "pending_by_review_route": dict(by_route), "count": len(rows), "rows": rows}

    @app.get("/api/dashboard/wiki", dependencies=[Depends(require_auth)])
    def api_dashboard_wiki() -> dict[str, Any]:
        concepts = list_concepts()
        missing_markdown = sorted(concept["id"] for concept in concepts if not concept.get("path"))
        conn = connect(workspace.db)
        try:
            source_count = int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
        finally:
            conn.close()
        page_count = len(list(workspace.wiki_pages.glob("*.md"))) if workspace.wiki_pages.exists() else 0
        return {"status": "ok", "concept_count": len(concepts), "page_count": page_count, "source_count": source_count, "stale_warning": bool(missing_markdown), "missing_markdown_concept_ids": missing_markdown}

    @app.get("/api/inbox/items", dependencies=[Depends(require_auth)])
    def api_inbox_items(status_filter: str | None = None) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            items = [build_inbox_item(dict(row), conn) for row in conn.execute("SELECT * FROM sources ORDER BY updated_at DESC, created_at DESC").fetchall()]
        finally:
            conn.close()
        if status_filter and status_filter != "all":
            items = [item for item in items if item["status"] == status_filter]
        order = {"failed": 0, "needs_mapping": 1, "new": 2, "processing": 3, "completed": 4}
        items.sort(key=lambda item: (order.get(item["status"], 99), item.get("updated_at") or ""), reverse=False)
        return {"status": "ok", "count": len(items), "items": items}

    @app.get("/api/inbox/items/{item_id}", dependencies=[Depends(require_auth)])
    def api_inbox_item_detail(item_id: str) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (item_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Unknown inbox item: {item_id}")
            item = build_inbox_item(dict(row), conn)
            preview = ""
            raw_path = row["raw_path"]
            if raw_path:
                raw_file = workspace.root / raw_path
                if raw_file.exists() and raw_file.is_file():
                    preview = raw_file.read_text(encoding="utf-8", errors="replace")[:4000]
            item["preview"] = preview
            item["content"] = preview
            item["content_preview"] = preview[:800]
            item["source_path"] = item.get("raw_path") or raw_path
            item["processing_log"] = build_processing_log(item_id, conn)
            error_events = [event for event in item["processing_log"] if event.get("status") in {"failed", "blocked"} or event.get("error")]
            item["error"] = error_events[0].get("error") if error_events else None
        finally:
            conn.close()
        return {"status": "ok", "item": item}

    @app.get("/api/inbox/items/{item_id}/result-record", dependencies=[Depends(require_auth)])
    def api_inbox_result_record(item_id: str) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            source = conn.execute("SELECT * FROM sources WHERE id = ?", (item_id,)).fetchone()
            if not source:
                raise HTTPException(status_code=404, detail=f"Unknown inbox item: {item_id}")
            final_state = build_inbox_item(dict(source), conn)["status"]
            candidate_rows = [dict(row) for row in conn.execute("SELECT * FROM review_candidates WHERE source_id = ? ORDER BY created_at DESC", (item_id,)).fetchall()]
            decision_rows = [dict(row) for row in conn.execute("SELECT * FROM human_decisions WHERE candidate_id IN (SELECT id FROM review_candidates WHERE source_id = ?) ORDER BY decided_at DESC", (item_id,)).fetchall()]
            run = conn.execute(
                """
                SELECT ar.* FROM agent_runs ar
                LEFT JOIN review_candidates rc ON rc.run_id = ar.id
                WHERE rc.source_id = ?
                ORDER BY ar.started_at DESC LIMIT 1
                """,
                (item_id,),
            ).fetchone()
            artifacts = source_artifact_rows(conn, item_id)
        finally:
            conn.close()
        model_summary = None
        if run:
            model_summary = {
                "provider": run["provider"],
                "model": run["model"],
                "task_type": run["task_type"],
                "prompt_version_id": run["prompt_version_id"],
                "status": run["status"],
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
            }
        return {
            "status": "ok",
            "record": {
                "source": {"id": source["id"], "title": source["title"], "origin": source["origin"], "processed_at": source["updated_at"], "final_state": final_state},
                "model_run": model_summary,
                "results": {
                    "generated_candidates_count": len(candidate_rows),
                    "decisions_count": len(decision_rows),
                    "approved_count": sum(1 for row in decision_rows if row["decision_type"] in {"approve", "merge", "create_new", "edit"}),
                    "retry_count": sum(1 for row in decision_rows if row["decision_type"] == "retry_with_instruction"),
                },
                "artifacts": [{"artifact_type": row["artifact_type"], "task_type": row["task_type"], "path": row["path"], "created_at": row["created_at"]} for row in artifacts],
            },
        }

    @app.post("/api/inbox/upload", dependencies=[Depends(require_auth)])
    async def api_inbox_upload(request: Request) -> dict[str, Any]:
        if "multipart/form-data" not in str(request.headers.get("content-type") or ""):
            raise HTTPException(status_code=422, detail="multipart/form-data is required")
        try:
            form = await request.form()
        except Exception as exc:
            raise HTTPException(status_code=501, detail="Multipart upload is unavailable in this runtime") from exc
        # FR-3-NO-02: single multipart field name "file". Legacy "files" is rejected
        # so the JS contract is the source of truth and the backend cannot be confused
        # by future callers that send a different name.
        uploaded_files: list[Any] = []
        if hasattr(form, "getlist"):
            uploaded_files.extend([item for item in form.getlist("file") if getattr(item, "filename", "")])
        else:
            item = form.get("file")
            if item is not None and getattr(item, "filename", ""):
                uploaded_files.append(item)
        if not uploaded_files:
            raise HTTPException(
                status_code=422,
                detail="file is required; use multipart field 'file' with Markdown (.md, .markdown) input. Other formats are Phase 2 conversion scope.",
            )
        results: list[Any] = []
        written_paths: list[Path] = []
        failed = False
        try:
            for uploaded in uploaded_files:
                target_name = f"{uuid.uuid4().hex}-{Path(str(uploaded.filename)).name}"
                temp_path = workspace.inbox_files / target_name
                written_paths.append(temp_path)
                data = await uploaded.read()
                temp_path.write_bytes(data)
                try:
                    results.append(ingest_markdown_file(workspace, temp_path))
                except UnsupportedInputError as exc:
                    # FR-3-NO-02: clean up ALL temp files on failure and surface
                    # an explicit 4xx with a hint about Phase 2 conversion scope.
                    raise HTTPException(
                        status_code=422,
                        detail=f"{exc} Markdown (.md, .markdown) upload is supported in Phase 3; other formats are Phase 2+ conversion scope.",
                    ) from exc
        except HTTPException:
            failed = True
            raise
        except Exception:
            # Any other failure (DB error, FS error, hash error, etc.) must also
            # clean up the temp files we wrote so the inbox/00_Inbox/files
            # folder does not accumulate stale uploads on 5xx.
            failed = True
            raise
        finally:
            if failed:
                for leftover in written_paths:
                    try:
                        leftover.unlink(missing_ok=True)
                    except OSError:
                        pass
        return {
            "status": "ok",
            "item": results[0],
            "items": results,
            "count": len(results),
            "field_name": "file",
        }

    @app.post("/api/inbox/text", dependencies=[Depends(require_auth)])
    def api_inbox_text(payload: InboxTextRequest) -> dict[str, Any]:
        try:
            result = ingest_text(workspace, payload.title, payload.text, origin=payload.source_note or "web_text")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"status": "ok", "item": result}

    @app.post("/api/inbox/scan", dependencies=[Depends(require_auth)])
    def api_inbox_scan() -> dict[str, Any]:
        result = scan_inbox(workspace, [workspace.inbox_memo, workspace.inbox_files, workspace.inbox_text])
        return {"status": "ok", **result}

    @app.post("/api/inbox/process", dependencies=[Depends(require_auth)])
    def api_inbox_process(payload: InboxProcessRequest) -> dict[str, Any]:
        item_ids = list(dict.fromkeys(payload.item_ids + ([payload.item_id] if payload.item_id else [])))
        if not item_ids:
            raise HTTPException(status_code=422, detail="item_ids is required")
        items = []
        conn = connect(workspace.db)
        try:
            known_ids = {
                str(row["id"])
                for row in conn.execute(
                    f"SELECT id FROM sources WHERE id IN ({', '.join('?' for _ in item_ids)})",
                    tuple(item_ids),
                ).fetchall()
            }
        finally:
            conn.close()
        for item_id in item_ids:
            if item_id not in known_ids:
                raise HTTPException(status_code=404, detail=f"Unknown inbox item: {item_id}")
            job_id = create_job(workspace.db, "inbox_process", target_type="source", target_id=item_id, input_refs=[{"kind": "source", "id": item_id}])
            items.append(process_inbox_source(workspace, item_id, job_id=job_id))
        failed_count = sum(1 for item in items if item.get("status") == "failed")
        blocked_count = sum(1 for item in items if item.get("status") == "blocked")
        return {
            "status": "ok" if failed_count == 0 and blocked_count == 0 else "partial",
            # Current contract: synchronous processing reports execution_mode /
            # acceptance_status. queued_count remains as a deprecated legacy
            # compatibility field only while older callers migrate.
            "execution_mode": "synchronous",
            "acceptance_status": "processed",
            "queued_count": len(items),
            "processed_count": len(items),
            "failed_count": failed_count,
            "blocked_count": blocked_count,
            "items": items,
            "message": "Inbox items processed through the synchronous web pipeline",
        }

    @app.post("/api/inbox/items/{item_id}/retry", dependencies=[Depends(require_auth)])
    def api_inbox_retry(item_id: str, payload: InboxRetryRequest) -> dict[str, Any]:
        queue_payload = InboxProcessRequest(item_ids=[item_id])
        response = api_inbox_process(queue_payload)
        response["note"] = payload.note
        return response

    @app.get("/api/inbox/items/{item_id}/log", dependencies=[Depends(require_auth)])
    def api_inbox_item_log(item_id: str) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            timeline = build_processing_log(item_id, conn)
        finally:
            conn.close()
        return {"status": "ok", "count": len(timeline), "events": timeline}

    @app.get("/api/inbox/status", dependencies=[Depends(require_auth)])
    def api_inbox_status() -> dict[str, Any]:
        items = api_inbox_items()["items"]
        counts = Counter(item["status"] for item in items)
        return {
            "status": "ok",
            "counts": dict(counts),
            "processing_count": counts.get("processing", 0),
            "needs_mapping_count": counts.get("needs_mapping", 0),
            "failed_count": counts.get("failed", 0),
            "last_scan_paths": [str(workspace.inbox_memo), str(workspace.inbox_files), str(workspace.inbox_text)],
        }

    @app.get("/api/review/candidates", dependencies=[Depends(require_auth)])
    def api_review_candidates(source_id: str | None = None) -> dict[str, Any]:
        rows = [json_for_candidate(row) for row in list_pending_candidates(workspace.db, source_id=source_id)]
        return {"status": "ok", "count": len(rows), "candidates": rows}

    @app.get("/api/review/candidates/{candidate_id}", dependencies=[Depends(require_auth)])
    def api_review_candidate_detail(candidate_id: str) -> dict[str, Any]:
        return {"status": "ok", "candidate": candidate_detail(candidate_id)}

    @app.get("/api/review/concepts", dependencies=[Depends(require_auth)])
    def api_review_concepts() -> dict[str, Any]:
        concepts = list_concepts()
        return {"status": "ok", "count": len(concepts), "concepts": concepts}

    @app.get("/api/review/concepts/{concept_id}", dependencies=[Depends(require_auth)])
    def api_review_concept_detail(concept_id: str) -> dict[str, Any]:
        if concept_id in known_concept_ids():
            return {"status": "ok", "concept": concept_detail(concept_id)}
        candidate = get_candidate_by_key(concept_id)
        if candidate:
            return {"status": "ok", "concept": candidate_graph_detail(candidate)}
        raise HTTPException(status_code=404, detail=f"Unknown concept_id: {concept_id}")

    @app.get("/api/review/graph/{concept_id}", dependencies=[Depends(require_auth)])
    def api_review_graph(concept_id: str) -> dict[str, Any]:
        return {"status": "ok", "graph": graph_data(concept_id)}

    @app.get("/api/review/mapping", dependencies=[Depends(require_auth)])
    def api_review_mapping(source_candidate_id: str) -> dict[str, Any]:
        rows = candidate_similarity_rows(source_candidate_id)
        return {"status": "ok", "count": len(rows), "concepts": rows}

    @app.post("/api/review/decide", dependencies=[Depends(require_auth)])
    def api_review_decide(payload: ReviewDecisionRequest) -> dict[str, Any]:
        action = payload.decision_type or payload.action
        if action == "batch_select":
            selected_ids = payload.candidate_ids or ([payload.candidate_id] if payload.candidate_id else [])
            for candidate_id in selected_ids:
                if get_candidate_by_id(candidate_id) is None:
                    raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
            # UI affordance only. Validate and echo the selection without DB or session state changes.
            return {"status": "ok", "action": "batch_select", "selected_count": len(selected_ids), "candidate_ids": selected_ids}
        if not payload.candidate_id:
            raise HTTPException(status_code=422, detail="candidate_id is required")
        metadata = dict(payload.metadata)
        if payload.edited_payload is not None:
            _update_candidate_payload(workspace.db, payload.candidate_id, payload.edited_payload)
            metadata["edited_payload"] = payload.edited_payload
        retry_instruction_id: str | None = None
        if action == "retry_with_instruction":
            if not (payload.reason and payload.instruction):
                raise HTTPException(status_code=422, detail="reason and instruction are required for retry_with_instruction")
            retry_instruction_id = record_retry_instruction(workspace.db, payload.candidate_id, reason=payload.reason, instruction=payload.instruction)
        elif action not in {"approve", "add", "merge", "create_new", "edit"}:
            raise HTTPException(status_code=422, detail=f"Unsupported action: {action}")
        decision_id = record_human_decision(workspace.db, payload.candidate_id, action, note=payload.note, retry_instruction_id=retry_instruction_id, metadata=metadata)
        return {"status": "ok", "decision_id": decision_id, "retry_instruction_id": retry_instruction_id, "candidate_id": payload.candidate_id, "action": action}

    @app.get("/api/mapping/candidates", dependencies=[Depends(require_auth)])
    def api_mapping_candidates(status_filter: str | None = "pending") -> dict[str, Any]:
        rows = query_candidates(status_filter=status_filter) if status_filter else query_candidates()
        candidates = []
        for row in rows:
            item = json_for_candidate(row)
            item["steps"] = [
                {"id": "page_validate", "label": "Page 검증"},
                {"id": "page_mapping", "label": "Page Mapping"},
                {"id": "relationship_validate", "label": "Relationship 검증"},
                {"id": "errors", "label": "오류/에러"},
            ]
            item["current_step"] = item.get("payload", {}).get("current_step") or "page_validate"
            candidates.append(item)
        return {"status": "ok", "count": len(candidates), "new_count": len(candidates), "candidates": candidates}

    @app.get("/api/mapping/candidates/{candidate_id}", dependencies=[Depends(require_auth)])
    def api_mapping_candidate_detail(candidate_id: str) -> dict[str, Any]:
        candidate = candidate_detail(candidate_id)
        candidate["wizard"] = {
            "steps": [
                {"id": "page_validate", "label": "Page 검증", "actions": ["reject", "edit", "next"]},
                {"id": "page_mapping", "label": "Page Mapping", "actions": ["reject", "edit", "next"]},
                {"id": "relationship_validate", "label": "Relationship 검증", "actions": ["reject", "edit", "confirm"]},
                {"id": "errors", "label": "오류/에러", "actions": ["retry_with_instruction", "mark_rejected", "back"]},
            ],
            "current_step": (candidate.get("payload") or {}).get("current_step") or "page_validate",
        }
        return {"status": "ok", "candidate": candidate}

    @app.get("/api/mapping/wiki-matches", dependencies=[Depends(require_auth)])
    def api_mapping_wiki_matches(candidate_id: str) -> dict[str, Any]:
        rows = candidate_similarity_rows(candidate_id)
        return {"status": "ok", "count": len(rows), "matches": rows}

    @app.get("/api/mapping/wiki/{concept_id}", dependencies=[Depends(require_auth)])
    def api_mapping_wiki_detail(concept_id: str) -> dict[str, Any]:
        return {"status": "ok", "wiki": concept_detail(concept_id)}

    @app.post("/api/mapping/decide", dependencies=[Depends(require_auth)])
    def api_mapping_decide(payload: ReviewDecisionRequest) -> dict[str, Any]:
        payload.metadata = {**payload.metadata, "surface": "mapping", "step": payload.metadata.get("step") or "relationship_validate"}
        action = payload.decision_type or payload.action
        if not payload.candidate_id:
            raise HTTPException(status_code=422, detail="candidate_id is required")
        if action not in {"add", "merge", "create_new", "edit"}:
            result = api_review_decide(payload)
        elif payload.metadata.get("step") == "relationship_validate":
            result = confirm_mapping_decision(payload.candidate_id, action, payload)
        else:
            result = record_mapping_preview(payload.candidate_id, action, payload)
        result["step"] = payload.metadata["step"]
        return result

    @app.post("/api/mapping/candidates/{candidate_id}/retry", dependencies=[Depends(require_auth)])
    def api_mapping_candidate_retry(candidate_id: str, payload: MappingRetryRequest) -> dict[str, Any]:
        request_payload = ReviewDecisionRequest(
            candidate_id=candidate_id,
            action="retry_with_instruction",
            reason=payload.reason,
            instruction=payload.instruction,
            note=payload.note,
            metadata={**payload.metadata, "surface": "mapping", "step": payload.metadata.get("step") or "errors"},
        )
        return api_review_decide(request_payload)

    @app.get("/api/wiki/pages", dependencies=[Depends(require_auth)])
    def api_wiki_pages(query: str | None = None, limit: int = 50) -> dict[str, Any]:
        q = (query or "").strip().lower()
        pages = list_concepts()
        if q:
            pages = [page for page in pages if q in page["id"].lower() or q in page["title"].lower() or q in (page.get("summary") or "").lower() or any(q in alias.lower() for alias in page.get("aliases") or [])]
        pages = pages[: max(1, min(limit, 200))]
        return {"status": "ok", "count": len(pages), "pages": pages}

    @app.get("/api/wiki/pages/{concept_id}", dependencies=[Depends(require_auth)])
    def api_wiki_page_detail(concept_id: str) -> dict[str, Any]:
        return {"status": "ok", "page": concept_detail(concept_id)}

    @app.get("/api/wiki/pages/{concept_id}/graph", dependencies=[Depends(require_auth)])
    def api_wiki_page_graph(concept_id: str) -> dict[str, Any]:
        concept_detail(concept_id)
        graph = graph_data(concept_id)
        return {"status": "ok", "graph": {"nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}}

    @app.get("/api/vault/tree", dependencies=[Depends(require_auth)])
    def api_vault_tree() -> dict[str, Any]:
        return {"status": "ok", "tree": vault_tree_node(workspace.vault)}

    @app.get("/api/vault/folder", dependencies=[Depends(require_auth)])
    def api_vault_folder(path: str | None = None) -> dict[str, Any]:
        folder = sanitize_vault_relative_path(path)
        return {"status": "ok", **folder_listing(folder)}

    @app.get("/api/vault/file", dependencies=[Depends(require_auth)])
    def api_vault_file(path: str) -> dict[str, Any]:
        file_path = sanitize_vault_relative_path(path, allow_root=False)
        return {"status": "ok", "file": vault_file_payload(file_path)}

    @app.get("/api/vault/search", dependencies=[Depends(require_auth)])
    def api_vault_search(q: str, limit: int = 25) -> dict[str, Any]:
        query = q.strip().lower()
        rows = []
        if query:
            for path in sorted(workspace.vault.rglob("*")):
                if len(rows) >= max(1, min(limit, 100)):
                    break
                if path.is_symlink() or not path.is_file() or not is_visible_vault_path(path):
                    continue
                rel = relative_vault_path(path)
                if query in path.name.lower():
                    rows.append({"path": rel, "name": path.name, "match": "name"})
                    continue
                if path.suffix.lower() in {".md", ".txt", ".json"}:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if query in text.lower():
                        rows.append({"path": rel, "name": path.name, "match": "content"})
        return {"status": "ok", "count": len(rows), "results": rows}

    @app.get("/api/settings/prompt-versions", dependencies=[Depends(require_auth)])
    def api_prompt_versions(task_type: str | None = None) -> dict[str, Any]:
        versions = list_prompt_versions(workspace.db, task_type)
        return {"status": "ok", "count": len(versions), "prompt_versions": versions}

    @app.get("/api/settings/prompts", dependencies=[Depends(require_auth)])
    def api_settings_prompts(task_type: str | None = None) -> dict[str, Any]:
        groups = list(prompt_group_summary().values())
        if task_type:
            groups = [group for group in groups if group["task_type"] == task_type]
        return {"status": "ok", "count": len(groups), "task_groups": groups}

    @app.get("/api/settings/prompts/history", dependencies=[Depends(require_auth)])
    def api_settings_prompts_history(task_type: str) -> dict[str, Any]:
        history = list_prompt_versions(workspace.db, task_type)
        return {"status": "ok", "count": len(history), "task_type": task_type, "history": history}

    @app.get("/api/settings/prompts/active", dependencies=[Depends(require_auth)])
    def api_settings_prompts_active(task_type: str) -> dict[str, Any]:
        active = get_active_prompt(workspace.db, task_type)
        default_status = active.get("version_label") == "phase2-default-v1" or "rollback_from:" in str(active.get("change_note") or "")
        return {
            "status": "ok",
            "task_type": task_type,
            "active": active,
            "default": {
                "phase2_default_label": "phase2-default-v1",
                "is_phase2_default": active.get("version_label") == "phase2-default-v1",
                "is_rollback_restored": "rollback_from:" in str(active.get("change_note") or ""),
                "visible": default_status,
            },
        }

    @app.post("/api/settings/prompt-versions", dependencies=[Depends(require_auth)])
    def api_create_prompt_version(payload: PromptVersionCreateRequest) -> dict[str, Any]:
        prompt_id = create_prompt_version(workspace.db, payload.task_type, payload.version_label or f"web-test-{utc_now().replace(':', '').replace('-', '')}", payload.prompt_text, state="test", change_note=payload.change_note, created_by=payload.created_by)
        return {"status": "ok", "prompt_id": prompt_id, "message": "Created test prompt version"}

    @app.post("/api/settings/prompts/test", dependencies=[Depends(require_auth)])
    def api_settings_prompts_test(payload: PromptVersionCreateRequest) -> dict[str, Any]:
        # Create test version first
        prompt_id = create_prompt_version(workspace.db, payload.task_type, payload.version_label or f"web-test-{utc_now().replace(':', '').replace('-', '')}", payload.prompt_text, state="test", change_note=payload.change_note, created_by=payload.created_by)

        # Run schema validation / dry-run test
        test_result = test_prompt_version(workspace.db, prompt_id, workspace_root=workspace.root)

        # Record test artifact
        artifact = record_artifact(
            workspace,
            artifact_type="prompt_test_result",
            task_type="prompt_test",
            payload={
                "status": test_result["status"],
                "result": test_result["status"],
                "validation_type": test_result["validation_type"],
                "reason": test_result.get("reason"),
                "schema_errors": test_result.get("schema_errors", []),
                "sample_input": test_result.get("sample_input"),
                "sample_output": test_result.get("sample_output"),
                "prompt_id": prompt_id,
                "task_type": payload.task_type,
                "version_label": payload.version_label or f"web-test-{utc_now().replace(':', '').replace('-', '')}",
                "message": f"Prompt test {test_result['status']}: {test_result['validation_type']}",
            },
            target_type="prompt_version",
            target_id=prompt_id,
            # FR-3-NO-05: confirm_prompt_version reads status from metadata_json;
            # duplicating the summary fields into metadata_json keeps the guard
            # offline (no file read) and makes the audit trail queryable.
            metadata={
                "status": test_result["status"],
                "validation_type": test_result["validation_type"],
                "reason": test_result.get("reason"),
                "schema_errors": test_result.get("schema_errors", []),
                "prompt_id": prompt_id,
            },
        )

        return {
            "status": "ok",
            "prompt_id": prompt_id,
            "message": f"Prompt test {test_result['status']}: {test_result['validation_type']}",
            "test_status": test_result["status"],
            "validation_type": test_result["validation_type"],
            "reason": test_result.get("reason"),
            "schema_errors": test_result.get("schema_errors", []),
            "artifact_id": artifact["artifact_id"],
        }

    @app.post("/api/settings/prompt-versions/{prompt_id}/confirm", dependencies=[Depends(require_auth)])
    def api_confirm_prompt_version(prompt_id: str) -> dict[str, Any]:
        # FR-3-NO-05: confirm_prompt_version auto-detects server-initiated bypass
        # via the prompt_versions.bypass_test column. The web endpoint must not
        # accept user-controllable bypass labels.
        confirm_result = confirm_prompt_version(workspace.db, prompt_id)
        if not confirm_result["confirmed"]:
            raise HTTPException(
                status_code=422,
                detail=confirm_result["reason"],
            )
        # Record confirm test run artifact
        _record_prompt_confirm_test_run(workspace, prompt_id)
        return {"status": "ok", "prompt_id": prompt_id, "message": "Confirmed prompt version", "bypass": confirm_result.get("bypass", False)}

    @app.post("/api/settings/prompts/{prompt_id}/confirm", dependencies=[Depends(require_auth)])
    def api_settings_prompts_confirm(prompt_id: str) -> dict[str, Any]:
        return api_confirm_prompt_version(prompt_id)

    @app.post("/api/settings/prompts/{prompt_id}/rollback", dependencies=[Depends(require_auth)])
    def api_settings_prompts_rollback(prompt_id: str, payload: PromptRollbackRequest) -> dict[str, Any]:
        try:
            result = rollback_prompt_version(workspace.db, prompt_id, change_note=payload.reason, created_by=payload.created_by)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        record_artifact(
            workspace,
            artifact_type="prompt_rollback",
            task_type="prompt_rollback",
            payload={"status": "ok", **result, "reason": payload.reason},
            target_type="prompt_version",
            target_id=result["new_version_id"],
        )
        return {"status": "ok", **result}

    @app.get("/api/settings/models", dependencies=[Depends(require_auth)])
    def api_settings_models() -> dict[str, Any]:
        settings_payload = mask_sensitive(load_settings(workspace.settings_file))
        return {"status": "ok", "models": list_models(workspace).get("models", []), "routes": get_route_map(workspace).get("routes", {}), "settings": settings_payload.get("llm", {})}

    @app.get("/api/settings/routes", dependencies=[Depends(require_auth)])
    def api_settings_routes() -> dict[str, Any]:
        return {"status": "ok", "count": len(route_rows()), "routes": route_rows()}

    @app.post("/api/settings/routes", dependencies=[Depends(require_auth)])
    def api_settings_routes_update(payload: RouteUpdateRequest) -> dict[str, Any]:
        return api_settings_llm_route(payload)

    @app.get("/api/settings/routes/history", dependencies=[Depends(require_auth)])
    def api_settings_routes_history(limit: int = 25) -> dict[str, Any]:
        conn = connect(workspace.db)
        try:
            rows = [dict(row) for row in conn.execute("SELECT * FROM artifacts WHERE artifact_type = 'route_change' ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()]
        finally:
            conn.close()
        return {"status": "ok", "count": len(rows), "history": rows}

    @app.get("/api/settings/llm/status", dependencies=[Depends(require_auth)])
    def api_settings_llm_status() -> dict[str, Any]:
        return {"status": "ok", **masked_llm_status()}

    @app.post("/api/settings/llm/config", dependencies=[Depends(require_auth)])
    def api_settings_llm_config(payload: LlmConfigUpdateRequest) -> dict[str, Any]:
        return {"status": "ok", **update_llm_config(payload)}

    @app.post("/api/settings/llm/test/{model_id}", dependencies=[Depends(require_auth)])
    def api_settings_llm_test(model_id: str) -> dict[str, Any]:
        """Test LLM model connection.

        Returns:
          - passed: connection successful
          - failed: connection failed (invalid endpoint/credentials)
          - blocked: missing configuration (no endpoint/API key/model)
        """
        exit_code, result = test_model_connection(workspace, model_id)
        # Map exit codes to status strings
        status_map = {0: "passed", 1: "failed", 3: "blocked"}
        test_status = status_map.get(exit_code, "failed")
        result_status = result.get("status", "failed")
        return {
            "status": "ok",
            "model_id": model_id,
            "test_status": test_status,
            "result_status": result_status,
            "reason": result.get("reason"),
            "message": result.get("message"),
            "artifact_id": result.get("artifact_id"),
            "run_id": result.get("run_id"),
            "job_id": result.get("job_id"),
        }

    @app.post("/api/settings/llm/route", dependencies=[Depends(require_auth)])
    def api_settings_llm_route(payload: RouteUpdateRequest) -> dict[str, Any]:
        task_type = ROUTE_LABELS.get(payload.task_type, {}).get("task_type") or payload.task_type
        if task_type not in ALLOWED_ROUTE_TASKS:
            raise HTTPException(status_code=422, detail=f"Unsupported task_type: {payload.task_type}")
        model_ids = {model["id"] for model in list_models(workspace).get("models", [])}
        if payload.model_id not in model_ids:
            raise HTTPException(status_code=422, detail=f"Unknown model_id: {payload.model_id}")
        try:
            result = set_route_model(workspace, task_type, payload.model_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"status": "ok", "route": {"task_type": task_type, "model_id": payload.model_id}, **result}

    @app.get("/api/settings/llm/concurrency", dependencies=[Depends(require_auth)])
    def api_settings_llm_concurrency() -> dict[str, Any]:
        return {"status": "ok", **concurrency_payload()}

    @app.post("/api/settings/llm/concurrency", dependencies=[Depends(require_auth)])
    def api_settings_llm_concurrency_update(payload: LlmConcurrencyUpdateRequest) -> dict[str, Any]:
        return {"status": "ok", **update_concurrency(payload.value)}

    @app.get("/api/settings/vault", dependencies=[Depends(require_auth)])
    def api_settings_vault() -> dict[str, Any]:
        return {"status": "ok", "vault_path": str(workspace.vault), "data_path": str(workspace.data), "env_file_exists": workspace.env_file.exists(), "onboarding_path": "/onboarding"}

    @app.get("/api/settings/auth", dependencies=[Depends(require_auth)])
    def api_settings_auth() -> dict[str, Any]:
        auth = auth_setup_status()
        return {"status": "ok", "web_admin_password_configured": auth["configured"], "env_name": auth["env_name"]}

    @app.get("/api/auth/status")
    def api_auth_status() -> dict[str, Any]:
        return {"status": "ok", "auth": auth_setup_status()}

    return app


def _update_candidate_payload(db_path: Path, candidate_id: str, payload: dict[str, Any]) -> None:
    now = utc_now()
    conn = connect(db_path)
    try:
        existing = conn.execute("SELECT id FROM review_candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"Unknown candidate_id: {candidate_id}")
        conn.execute("UPDATE review_candidates SET payload_json = ?, updated_at = ? WHERE id = ?", (json.dumps(payload, ensure_ascii=False, sort_keys=True), now, candidate_id))
        conn.commit()
    finally:
        conn.close()


def _record_prompt_confirm_test_run(workspace: WorkspacePaths, prompt_id: str) -> None:
    job_id = create_job(workspace.db, "prompt_confirm_test", target_type="prompt_version", target_id=prompt_id)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="web_admin",
        task_type="prompt_confirm_test",
        model=None,
        provider="web",
        prompt_version_id=prompt_id,
        input_refs=[{"kind": "prompt_version", "id": prompt_id}],
    )
    artifact = record_artifact(
        workspace,
        artifact_type="prompt_confirm_test",
        task_type="prompt_confirm_test",
        payload={
            "status": "ok",
            "result": "ok",
            "prompt_id": prompt_id,
            "run_id": run_id,
            "job_id": job_id,
            "message": "Web prompt confirm test run recorded",
        },
        target_type="prompt_version",
        target_id=prompt_id,
        run_id=run_id,
    )
    update_agent_run(workspace.db, run_id, status="succeeded", output_refs=[artifact], artifact_id=artifact["artifact_id"])
    update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
