"""Settings routes for editing configurations and managing prompts version history."""

from __future__ import annotations

import os
import datetime
import sqlite3
from pathlib import Path
from typing import Any
from pydantic import BaseModel

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from ... import config as cfg
from ... import db

router = APIRouter()


class LLMConfigModel(BaseModel):
    provider: str
    model: str
    host: str
    temperature: float
    thinking: bool


class ChunkingConfigModel(BaseModel):
    chunk_size: int
    overlap: int
    strategy: str


class SettingsUpdateModel(BaseModel):
    config: dict[str, Any]
    env: dict[str, str]


class PromptContentModel(BaseModel):
    content: str


def read_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    env_data = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            env_data[key.strip()] = val.strip().strip('"').strip("'")
    return env_data


def write_env(env_path: Path, data: dict[str, str]) -> None:
    lines = ["# LLM-Wiki auto-generated environment variables", ""]
    for key, val in data.items():
        lines.append(f"{key}={val}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("/settings", response_class=HTMLResponse)
async def settings_view(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    config = cfg.load_config(paths)
    
    env_file = os.environ.get("ENV_FILE_PATH")
    env_path = Path(env_file) if env_file else paths.root / ".env"
    env_data = read_env(env_path)
    
    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        {
            "config": config,
            "env": env_data,
            "page": "settings",
        },
    )


@router.post("/api/settings")
async def save_settings(request: Request, data: SettingsUpdateModel) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    
    # 1. Update config.yml
    current_config = cfg.load_config(paths)
    current_config.update(data.config)
    cfg.save_config(paths, current_config)
    
    # 2. Update .env
    env_file = os.environ.get("ENV_FILE_PATH")
    env_path = Path(env_file) if env_file else paths.root / ".env"
    write_env(env_path, data.env)
    
    return JSONResponse({"status": "success", "message": "Settings updated successfully."})


@router.get("/api/settings/prompts/{prompt_key}")
async def get_prompt_details(request: Request, prompt_key: str) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    
    # Let's fetch prompt history
    history = []
    current_prompt = ""
    current_version = "v1.0"
    current_status = "published"
    
    try:
        with db.connect(paths.state_db) as conn:
            # Get prompt versions sorted newest-first
            rows = conn.execute(
                "SELECT * FROM prompt_versions WHERE prompt_key = ? ORDER BY id DESC",
                (prompt_key,)
            ).fetchall()
            
            for row in rows:
                history.append(dict(row))
                
            # Find the active edit draft or published prompt
            active_row = conn.execute(
                "SELECT * FROM prompt_versions WHERE prompt_key = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
                (prompt_key,)
            ).fetchone()
            
            if not active_row:
                active_row = conn.execute(
                    "SELECT * FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
                    (prompt_key,)
                ).fetchone()
                
            if active_row:
                current_prompt = active_row["content"]
                current_version = active_row["version_tag"]
                current_status = active_row["status"]
            else:
                from ...prompts import DEFAULT_PROMPTS
                current_prompt = DEFAULT_PROMPTS.get(prompt_key, "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return JSONResponse({
        "prompt_key": prompt_key,
        "content": current_prompt,
        "version_tag": current_version,
        "status": current_status,
        "history": history
    })


@router.post("/api/settings/prompts/{prompt_key}/draft")
async def save_prompt_draft(request: Request, prompt_key: str, data: PromptContentModel) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    with db.connect(paths.state_db) as conn:
        # Check if there is an existing draft to update
        existing_draft = conn.execute(
            "SELECT id FROM prompt_versions WHERE prompt_key = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
            (prompt_key,)
        ).fetchone()
        
        # Get active published version tag
        active_pub = conn.execute(
            "SELECT version_tag FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
            (prompt_key,)
        ).fetchone()
        
        version_tag = active_pub["version_tag"] if active_pub else "v1.0"
        
        if existing_draft:
            conn.execute(
                "UPDATE prompt_versions SET content = ?, created_at = ? WHERE id = ?",
                (data.content, now, existing_draft["id"])
            )
        else:
            conn.execute(
                """
                INSERT INTO prompt_versions (prompt_key, version_tag, content, status, created_at)
                VALUES (?, ?, ?, 'draft', ?)
                """,
                (prompt_key, version_tag, data.content, now)
            )
            
    return JSONResponse({"status": "success", "message": "Draft saved."})


@router.post("/api/settings/prompts/{prompt_key}/publish")
async def publish_prompt(request: Request, prompt_key: str) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    with db.connect(paths.state_db) as conn:
        # Get draft content
        draft = conn.execute(
            "SELECT * FROM prompt_versions WHERE prompt_key = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
            (prompt_key,)
        ).fetchone()
        
        # Get published prompt row
        pub = conn.execute(
            "SELECT version_tag FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
            (prompt_key,)
        ).fetchone()
        
        if not draft:
            # If no draft, check if we can publish existing content or error
            if pub:
                return JSONResponse({"status": "error", "message": "No new changes to publish."})
            raise HTTPException(status_code=400, detail="No draft exists to publish.")
            
        # Determine new version tag
        if pub:
            # parse vX.Y
            ver_str = pub["version_tag"].replace("v", "")
            try:
                major, minor = ver_str.split(".", 1)
                new_version = f"v{major}.{int(minor) + 1}"
            except ValueError:
                new_version = "v1.1"
        else:
            new_version = "v1.0"
            
        # Archive old published ones
        conn.execute(
            "UPDATE prompt_versions SET status = 'archived' WHERE prompt_key = ? AND status = 'published'",
            (prompt_key,)
        )
        
        # Update draft to published
        conn.execute(
            "UPDATE prompt_versions SET version_tag = ?, status = 'published', published_at = ? WHERE id = ?",
            (new_version, now, draft["id"])
        )
        
    return JSONResponse({"status": "success", "version_tag": new_version})


@router.post("/api/settings/prompts/{prompt_key}/rollback")
async def rollback_prompt(request: Request, prompt_key: str, version: str) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    with db.connect(paths.state_db) as conn:
        # Find prompt content matching the rollback version
        target = conn.execute(
            "SELECT content FROM prompt_versions WHERE prompt_key = ? AND version_tag = ? LIMIT 1",
            (prompt_key, version)
        ).fetchone()
        
        if not target:
            raise HTTPException(status_code=404, detail="Prompt version not found.")
            
        # Get active published tag to calculate next increment
        pub = conn.execute(
            "SELECT version_tag FROM prompt_versions WHERE prompt_key = ? AND status = 'published' ORDER BY id DESC LIMIT 1",
            (prompt_key,)
        ).fetchone()
        
        if pub:
            ver_str = pub["version_tag"].replace("v", "")
            try:
                major, minor = ver_str.split(".", 1)
                new_version = f"v{major}.{int(minor) + 1}"
            except ValueError:
                new_version = "v1.1"
        else:
            new_version = "v1.0"
            
        # Archive currently published ones
        conn.execute(
            "UPDATE prompt_versions SET status = 'archived' WHERE prompt_key = ? AND status = 'published'",
            (prompt_key,)
        )
        
        # Insert new rolled back version as published
        conn.execute(
            """
            INSERT INTO prompt_versions (prompt_key, version_tag, content, status, created_at, published_at)
            VALUES (?, ?, ?, 'published', ?, ?)
            """,
            (prompt_key, new_version, target["content"], now, now)
        )
        
    return JSONResponse({"status": "success", "version_tag": new_version})


@router.get("/api/raw-download/{source_id}")
async def raw_download(request: Request, source_id: int):
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    with db.connect(paths.state_db) as conn:
        row = conn.execute(
            "SELECT relpath FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Source not found.")
        
        # Determine actual file path
        file_path = paths.root / row["relpath"]
        if not file_path.exists():
            # Check data lake raw docs folder as fallback
            data_lake_path = Path("/data/raw_docs") / file_path.name
            if data_lake_path.exists():
                file_path = data_lake_path
            else:
                raise HTTPException(status_code=404, detail=f"File not found on disk: {row['relpath']}")
                
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream"
        )
