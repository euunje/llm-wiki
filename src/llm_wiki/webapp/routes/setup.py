"""Setup routes for the onboarding wizard."""

from __future__ import annotations

import os
import sys
import httpx
import asyncio
import subprocess
import logging
from pathlib import Path
from pydantic import BaseModel

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from ... import config as cfg
from ... import scaffold

router = APIRouter()
logger = logging.getLogger("llm_wiki.setup")


class SetupConfigModel(BaseModel):
    path: str
    llm_provider: str
    llm_model: str
    llm_host: str
    llm_temperature: float = 0.3
    llm_thinking: bool = True
    api_key: str | None = None
    wiki_dir: str = "wiki"
    raw_dir: str = "raw"
    schema_dir: str = "schema"


class TestConnectionModel(BaseModel):
    llm_provider: str
    llm_host: str
    api_key: str | None = None


@router.get("/setup", response_class=HTMLResponse)
async def setup_view(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    current_dir = str(paths.root.resolve())
    
    response = request.app.state.templates.TemplateResponse(
        request,
        "setup.html",
        {
            "current_dir": current_dir,
            "page": "setup",
        },
    )
    
    # Force disable browser caching for setup page to ensure latest JS runs
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/api/setup/list-dirs")
async def list_dirs(path: str = "") -> JSONResponse:
    """Robust web-based directory browser that doesn't depend on OS-level UI permissions."""
    if not path:
        p = Path.home()
    else:
        # Support '~' expansion
        p = Path(os.path.expanduser(path)).resolve()
        
    if not p.exists() or not p.is_dir():
        p = Path.home()
        
    try:
        subdirs = []
        for child in sorted(p.iterdir()):
            try:
                if child.is_dir() and not child.name.startswith("."):
                    subdirs.append(child.name)
            except (PermissionError, FileNotFoundError):
                continue
        
        return JSONResponse({
            "status": "success",
            "current_path": str(p),
            "parent_path": str(p.parent) if p.parent != p else None,
            "subdirs": subdirs
        })
    except Exception as e:
        print(f"Error listing directory {p}: {e}", file=sys.stderr, flush=True)
        return JSONResponse({
            "status": "error",
            "current_path": str(p),
            "parent_path": str(p.parent) if p.parent != p else None,
            "subdirs": [],
            "error": str(e)
        })


@router.post("/api/setup/browse-directory")
async def browse_directory() -> JSONResponse:
    """Trigger native macOS Finder directory selector dialog (with AppleScript fallback)."""
    try:
        # Prompt user using macOS AppleScript
        cmd = 'osascript -e \'POSIX path of (choose folder with prompt "Select LLM-Wiki Project Directory")\''
        
        # Run in thread pool with a timeout to avoid blocking FastAPI event loop
        result = await asyncio.to_thread(
            lambda: subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2.0)
        )
        
        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                print(f"[Setup OS Picker] Native folder selected: {path}", file=sys.stderr, flush=True)
                return JSONResponse({"status": "success", "path": path})
        
        print(f"[Setup OS Picker Warn] AppleScript folder picker returned non-zero code: {result.returncode}", file=sys.stderr, flush=True)
        return JSONResponse({
            "status": "error",
            "message": "macOS folder picker returned non-zero code or was cancelled. Using web directory browser fallback."
        })
    except subprocess.TimeoutExpired:
        print("[Setup OS Picker Warn] AppleScript folder picker timed out. Falling back to web folder browser.", file=sys.stderr, flush=True)
        return JSONResponse({
            "status": "error",
            "message": "macOS folder picker timed out. Using web directory browser fallback."
        })
    except Exception as e:
        # Log error in terminal
        print(f"[Setup OS Picker Warn] AppleScript folder picker failed: {e}", file=sys.stderr, flush=True)
        return JSONResponse({
            "status": "error",
            "message": f"macOS folder picker failed: {e}. Using web directory browser fallback."
        })


@router.post("/api/setup/test-connection")
async def test_connection(data: TestConnectionModel) -> JSONResponse:
    """Test connection to LLM host and retrieve list of available models."""
    provider = data.llm_provider
    host = data.llm_host.strip().rstrip("/")
    api_key = data.api_key
    
    print(f"[Setup Test Connection] Testing {provider} connection at host: '{host}'...", file=sys.stderr, flush=True)
    
    if provider == "ollama":
        url = f"{host}/api/tags"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    models_data = response.json()
                    models_list = [model["name"] for model in models_data.get("models", [])]
                    print(f"[Setup Test Connection] Success! Found {len(models_list)} models: {models_list}", file=sys.stderr, flush=True)
                    return JSONResponse({
                        "status": "success",
                        "message": "Successfully connected to Ollama!",
                        "models": models_list
                    })
                else:
                    msg = f"Ollama returned status code {response.status_code}."
                    print(f"[Setup Test Connection] Error: {msg}", file=sys.stderr, flush=True)
                    return JSONResponse({
                        "status": "error",
                        "message": msg
                    })
        except Exception as e:
            msg = f"Could not connect to Ollama at {host}: {str(e)}"
            print(f"[Setup Test Connection] Exception: {msg}", file=sys.stderr, flush=True)
            return JSONResponse({
                "status": "error",
                "message": msg
            })
            
    elif provider in ("openai", "openai-local"):
        url = f"{host}/models"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=5.0)
                if response.status_code == 200:
                    models_data = response.json()
                    if provider == "openai-local":
                        models_list = [model["id"] for model in models_data.get("data", [])]
                    else:
                        models_list = [model["id"] for model in models_data.get("data", []) if "gpt" in model["id"] or "o1" in model["id"]]
                    print(f"[Setup Test Connection] Success! Found {len(models_list)} models: {models_list[:5]}...", file=sys.stderr, flush=True)
                    return JSONResponse({
                        "status": "success",
                        "message": "Successfully connected to OpenAI!",
                        "models": sorted(models_list)
                    })
                else:
                    msg = f"OpenAI returned status code {response.status_code}. Detail: {response.text}"
                    print(f"[Setup Test Connection] Error: {msg}", file=sys.stderr, flush=True)
                    return JSONResponse({
                        "status": "error",
                        "message": f"OpenAI returned status code {response.status_code}. Please verify API key."
                    })
        except Exception as e:
            msg = f"Could not connect to OpenAI: {str(e)}"
            print(f"[Setup Test Connection] Exception: {msg}", file=sys.stderr, flush=True)
            return JSONResponse({
                "status": "error",
                "message": msg
            })
            
    return JSONResponse({
        "status": "success",
        "message": "Connection configuration accepted.",
        "models": []
    })


@router.post("/api/setup")
async def execute_setup(request: Request, data: SetupConfigModel) -> JSONResponse:
    target_path = Path(os.path.expanduser(data.path)).resolve()
    
    # 1. Run scaffold to initialize directories, templates, config, and DB
    try:
        paths = scaffold.scaffold(
            target_path,
            force=True,
            wiki_dir=data.wiki_dir,
            raw_dir=data.raw_dir,
            schema_dir=data.schema_dir
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scaffolding failed: {str(e)}")
        
    # 2. Update config.yml with user LLM preferences and custom paths
    try:
        config = cfg.load_config(paths)
        config["llm"] = {
            "provider": data.llm_provider,
            "model": data.llm_model,
            "host": data.llm_host,
            "temperature": data.llm_temperature,
            "thinking": data.llm_thinking,
        }
        config["paths"] = {
            "wiki_dir": data.wiki_dir,
            "raw_dir": data.raw_dir,
            "schema_dir": data.schema_dir
        }
        cfg.save_config(paths, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save LLM configuration: {str(e)}")
        
    # 3. Write API Keys to .env if provided
    if data.api_key:
        env_key = "OPENAI_API_KEY"
        if data.llm_provider == "anthropic":
            env_key = "ANTHROPIC_API_KEY"
        elif data.llm_provider == "gemini":
            env_key = "GEMINI_API_KEY"
            
        env_file = os.environ.get("ENV_FILE_PATH")
        env_path = Path(env_file) if env_file else paths.root / ".env"
        
        try:
            env_path.write_text(f"{env_key}={data.api_key}\n", encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write .env file: {str(e)}")
            
    # 4. Update the running app's state with the new resolved paths
    request.app.state.wiki_paths = paths
    
    return JSONResponse({"status": "success", "message": "LLM-Wiki project initialized successfully!"})


@router.get("/guide", response_class=HTMLResponse)
async def guide_view(request: Request) -> HTMLResponse:
    """Renders the comprehensive system directory and pipeline guide page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "guide.html",
        {
            "page": "guide",
        },
    )
