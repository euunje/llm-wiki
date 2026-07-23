from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from llm_wiki.config import load_settings, save_settings
from llm_wiki.jobs import create_agent_run, create_job, record_artifact, update_agent_run, update_job
from llm_wiki.workspace import WorkspacePaths

ALLOWED_ROUTE_TASKS = {"extract_claims", "ask"}

# User-facing labels mapped to internal task types.
# Only actual LLM call units are routable.
ROUTE_USER_LABELS: dict[str, str] = {
    "Node/Claim 후보 생성": "extract_claims",
    "Ask 답변 합성": "ask",
}


def get_task_type_from_label(user_label: str) -> str | None:
    """Map a user-facing label to its internal task type.

    Args:
        user_label: One of the known user labels (Page 검증, Page Mapping, etc.).

    Returns:
        The internal task type string, or None if label is not recognized.
    """
    return ROUTE_USER_LABELS.get(user_label)


def get_user_label_for_task(task_type: str) -> str | None:
    """Map an internal task type to its user-facing label.

    Args:
        task_type: Internal task type (extract_claims, map, link, etc.).

    Returns:
        The user-facing label string, or None if task_type is not mapped.
    """
    for label, ttype in ROUTE_USER_LABELS.items():
        if ttype == task_type:
            return label
    return None


def list_route_labels() -> list[dict[str, str]]:
    """Return all user-label to task_type mappings.

    Returns:
        List of dicts with 'label' and 'task_type' keys.
    """
    return [{"label": label, "task_type": task_type} for label, task_type in ROUTE_USER_LABELS.items()]


# Concurrency settings constants and helpers.
CONCURRENCY_DEFAULT = 1
CONCURRENCY_MAX = 3
CONCURRENCY_KEY = "concurrency"
CONCURRENCY_LEGACY_KEY = "max_concurrent_requests"


def get_concurrency_config(workspace: WorkspacePaths) -> dict[str, int]:
    """Get current concurrency configuration.

    Returns:
        Dict with 'default' (per-provider default), 'max' (absolute max),
        and 'provider_concurrency' dict of provider-specific overrides.
    """
    settings = load_settings(workspace.settings_file, resolve_env=False)
    llm_settings = settings.get("llm", {})
    provider_concurrency = llm_settings.get("provider_max_concurrent", {})

    return {
        "default": _validate_concurrency_value(
            llm_settings.get(CONCURRENCY_KEY, llm_settings.get(CONCURRENCY_LEGACY_KEY, CONCURRENCY_DEFAULT)),
            "default",
        ),
        "max": CONCURRENCY_MAX,
        "provider_concurrency": provider_concurrency,
    }


def set_concurrency_config(
    workspace: WorkspacePaths,
    *,
    default: int | None = None,
    provider: str | None = None,
    provider_limit: int | None = None,
) -> dict[str, Any]:
    """Set concurrency configuration in settings.

    Args:
        workspace: WorkspacePaths instance.
        default: Global default concurrency (1).
        provider: Provider name for provider-specific limit.
        provider_limit: Provider-specific max concurrency.

    Returns:
        Updated concurrency config dict.

    Raises:
        ValueError: If values fail validation.
    """
    settings = load_settings(workspace.settings_file, resolve_env=False)
    llm_settings = settings.setdefault("llm", {})

    if default is not None:
        validated = _validate_concurrency_value(default, "default")
        llm_settings[CONCURRENCY_KEY] = validated

    if provider is not None and provider_limit is not None:
        validated = _validate_concurrency_value(provider_limit, f"provider '{provider}'")
        llm_settings.setdefault("provider_max_concurrent", {})[provider] = validated

    save_settings(workspace.settings_file, settings)
    return get_concurrency_config(workspace)


def _validate_concurrency_value(value: int, context: str) -> int:
    """Validate and clamp a concurrency value.

    Args:
        value: Raw integer value.
        context: String describing what is being validated (for error messages).

    Returns:
        Validated integer between 1 and CONCURRENCY_MAX.

    Raises:
        ValueError: If value is not a valid integer.
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Concurrency {context} must be an integer, got: {value!r}")
    if value < 1:
        value = 1
    if value > CONCURRENCY_MAX:
        value = CONCURRENCY_MAX
    return value


def effective_concurrency_for_provider(
    workspace: WorkspacePaths,
    provider: str,
) -> int:
    """Get effective concurrency limit for a provider.

    If the provider has a specific limit configured, use it.
    Otherwise return the global default.
    If the provider is unsupported/not configured, return 1.

    Args:
        workspace: WorkspacePaths instance.
        provider: Provider name (e.g., 'openai', 'anthropic').

    Returns:
        Effective concurrency limit (1 to CONCURRENCY_MAX).
    """
    config = get_concurrency_config(workspace)
    provider_concurrency = config.get("provider_concurrency", {})
    if provider and provider in provider_concurrency:
        return provider_concurrency[provider]
    return config["default"]


def _llm_settings(workspace: WorkspacePaths) -> dict[str, Any]:
    return load_settings(workspace.settings_file).get("llm", {})


def _auth_headers(llm_settings: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = os.environ.get(str(llm_settings.get("api_key_env") or ""))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _openai_base_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    for suffix in ("/v1/chat/completions", "/chat/completions", "/v1/models", "/models"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    if normalized.endswith("/v1"):
        return normalized
    if normalized.endswith("/api"):
        normalized = normalized[: -len("/api")]
    return f"{normalized}/v1"


def _ollama_base_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/api/tags"):
        normalized = normalized[: -len("/api/tags")]
    elif normalized.endswith("/api"):
        normalized = normalized[: -len("/api")]
    return normalized


def list_provider_models(workspace: WorkspacePaths) -> list[dict[str, Any]]:
    """Return actual model names exposed by the configured local LLM provider."""
    llm_settings = _llm_settings(workspace)
    endpoint = str(llm_settings.get("endpoint") or "").rstrip("/")
    provider = str(llm_settings.get("provider") or "").lower()
    if not endpoint:
        return []
    try:
        if provider == "ollama":
            request = urllib.request.Request(f"{_ollama_base_url(endpoint)}/api/tags", headers=_auth_headers(llm_settings), method="GET")
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            raw_models = payload.get("models") or []
            return [
                {"id": str(item.get("name") or ""), "model_name": str(item.get("name") or ""), "display_name": str(item.get("name") or ""), "provider": "ollama", "capability": "chat"}
                for item in raw_models
                if item.get("name")
            ]
        request = urllib.request.Request(f"{_openai_base_url(endpoint)}/models", headers=_auth_headers(llm_settings), method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        raw_models = payload.get("data") or payload.get("models") or []
        result: list[dict[str, Any]] = []
        for item in raw_models:
            model_name = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
            capability = "embedding" if any(token in model_name.lower() for token in ("embed", "embedding")) else "chat"
            if model_name:
                result.append({"id": model_name, "model_name": model_name, "display_name": model_name, "provider": provider or "openai_compatible", "capability": capability})
        return result
    except Exception:
        return []


def _embedding_settings(workspace: WorkspacePaths) -> dict[str, Any]:
    return load_settings(workspace.settings_file).get("embedding", {})


def _embedding_model_root(workspace: WorkspacePaths, embedding_settings: dict[str, Any] | None = None) -> Path:
    settings = embedding_settings if embedding_settings is not None else _embedding_settings(workspace)
    raw = str(settings.get("model_root") or "data/models/embeddings").strip()
    root = Path(raw).expanduser()
    if not root.is_absolute():
        root = workspace.root / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def list_embedding_models(workspace: WorkspacePaths) -> list[dict[str, Any]]:
    """Return locally available embedding models from embedding.model_root.

    Embedding discovery is intentionally independent from the LLM provider
    endpoint. The configured root is a local directory whose immediate child
    directories are selectable embedding model IDs.
    """
    embedding_settings = _embedding_settings(workspace)
    root = _embedding_model_root(workspace, embedding_settings)
    result: list[dict[str, Any]] = []
    default_model = str(embedding_settings.get("default_model") or "").strip()
    if default_model:
        result.append(
            {
                "id": default_model,
                "model_name": default_model,
                "display_name": default_model,
                "provider": "local_embedding_folder",
                "capability": "embedding",
                "path": str(_resolve_embedding_model_path(workspace, default_model) or root),
                "root": str(root),
                "source": "configured_default",
            }
        )
    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_dir() or path.name.startswith(".") or path.name.startswith("models--"):
            continue
        rel = path.relative_to(root).as_posix()
        if rel == default_model:
            continue
        result.append(
            {
                "id": rel,
                "model_name": rel,
                "display_name": rel,
                "provider": "local_embedding_folder",
                "capability": "embedding",
                "path": str(path),
                "root": str(root),
                "source": "local_folder",
            }
        )
    return result


def _resolve_embedding_model_path(workspace: WorkspacePaths, model_name: str) -> Path | None:
    root = _embedding_model_root(workspace)
    candidate = Path(model_name).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve()
    local = root / model_name
    if local.exists() and local.is_dir():
        return local.resolve()
    return None


def list_fastembed_models() -> list[dict[str, Any]]:
    """Deprecated compatibility alias: use list_embedding_models(workspace)."""
    return []


def list_models(workspace: WorkspacePaths) -> dict[str, Any]:
    llm_settings = _llm_settings(workspace)
    models = []
    for model_id, config in (llm_settings.get("models") or {}).items():
        model = dict(config or {})
        model.setdefault("id", model_id)
        capability = model.get("capability") or "unknown"
        if capability == "embedding":
            embedding_settings = _embedding_settings(workspace)
            model["model_name"] = model.get("model_name") or embedding_settings.get("default_model") or ""
            model["provider"] = "local_embedding_folder"
            model["request_format"] = "local_embedding_folder"
        endpoint_configured = bool(model.get("endpoint") or llm_settings.get("endpoint")) if capability == "chat" else True
        models.append(
            {
                "id": model["id"],
                "model_name": model.get("model_name") or "",
                "display_name": model.get("model_name") or model["id"],
                "provider": model.get("provider") or (llm_settings.get("provider") if capability == "chat" else "local_embedding_folder") or "unknown",
                "capability": capability,
                "configured": bool(model.get("model_name") and endpoint_configured),
                "endpoint_configured": endpoint_configured,
                "model_name_configured": bool(model.get("model_name")),
                "request_format": model.get("request_format") or "unknown",
            }
        )
    provider_models = list_provider_models(workspace)
    embedding_models = list_embedding_models(workspace)
    return {
        "status": "ok",
        "models": models,
        "provider_models": provider_models,
        "embedding_models": embedding_models,
        "fastembed_models": [],
        "count": len(models),
        "provider_model_count": len(provider_models),
        "embedding_model_count": len(embedding_models),
        "fastembed_model_count": 0,
        "message": f"Found {len(models)} model configuration(s)",
    }


def _resolve_model(workspace: WorkspacePaths, model_id: str) -> dict[str, Any]:
    llm_settings = _llm_settings(workspace)
    models = llm_settings.get("models") or {}
    if model_id not in models:
        raise ValueError(f"Unknown model_id: {model_id}")
    model = dict(models[model_id] or {})
    model.setdefault("id", model_id)
    if model.get("capability") == "embedding":
        embedding_settings = _embedding_settings(workspace)
        model["provider"] = "local_embedding_folder"
        model["model_name"] = model.get("model_name") or embedding_settings.get("default_model") or ""
        model["request_format"] = "local_embedding_folder"
        model.setdefault("timeout_seconds", embedding_settings.get("fastembed_timeout_seconds") or 30)
        return model
    model.setdefault("endpoint", llm_settings.get("endpoint") or "")
    model.setdefault("api_key_env", llm_settings.get("api_key_env") or "LLM_WIKI_API_KEY")
    model.setdefault("timeout_seconds", llm_settings.get("timeout_seconds") or 300)
    return model


def get_route_map(workspace: WorkspacePaths, task_type: str | None = None) -> dict[str, Any]:
    configured_routes = (_llm_settings(workspace).get("routing") or {}).copy()
    routes = {task: configured_routes.get(task) for task in sorted(ALLOWED_ROUTE_TASKS)}
    if task_type:
        if task_type not in ALLOWED_ROUTE_TASKS:
            raise ValueError(f"Unknown task_type: {task_type}")
        routes = {task_type: routes.get(task_type)}
    return {"status": "ok", "routes": routes, "message": "Loaded route configuration"}


def set_route_model(workspace: WorkspacePaths, task_type: str, model_id: str) -> dict[str, Any]:
    if task_type not in ALLOWED_ROUTE_TASKS:
        raise ValueError(f"Unknown task_type: {task_type}")
    settings = load_settings(workspace.settings_file, resolve_env=False)
    model = _resolve_model(workspace, model_id)
    if model.get("capability") != "chat":
        raise ValueError(f"Model {model_id} capability must be chat for route {task_type}")
    settings.setdefault("llm", {}).setdefault("routing", {})[task_type] = model_id
    save_settings(workspace.settings_file, settings)
    artifact = record_artifact(
        workspace,
        artifact_type="route_change",
        task_type="route_set",
        payload={"status": "ok", "task_type": task_type, "model_id": model_id},
        target_type="route",
        target_id=task_type,
    )
    return {
        "status": "ok",
        "task_type": task_type,
        "model_id": model_id,
        **artifact,
        "message": f"Route {task_type} -> {model_id}",
    }


def _build_request(model: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    model_name = model.get("model_name") or ""
    capability = model.get("capability")
    request_format = model.get("request_format")
    if capability == "chat" and request_format == "openai_chat":
        body = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Return the single token OK."}],
            "temperature": 0,
            "max_tokens": 4,
        }
    elif capability == "embedding" and request_format == "openai_embeddings":
        body = {"model": model_name, "input": "phase1 connectivity test"}
    else:
        raise ValueError(f"Unsupported request format for Phase 1: {capability}/{request_format}")
    import json

    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(str(model.get("api_key_env") or ""))
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return payload, headers


def _request_endpoint(endpoint: str, request_format: str | None) -> str:
    """Resolve an OpenAI-compatible base endpoint to a concrete API path.

    Settings may provide either a full endpoint (for example a chat completions
    URL) or a provider base URL. Keep this dynamic so reusable source does not
    hardcode hostnames, ports, or local addresses.
    """

    normalized = endpoint.rstrip("/")
    if request_format == "openai_chat" and not normalized.endswith("/chat/completions"):
        return f"{_openai_base_url(endpoint)}/chat/completions"
    if request_format == "openai_embeddings" and not normalized.endswith("/embeddings"):
        return f"{_openai_base_url(endpoint)}/embeddings"
    return endpoint


def test_model_connection(workspace: WorkspacePaths, model_id: str) -> tuple[int, dict[str, Any]]:
    model = _resolve_model(workspace, model_id)
    job_id = create_job(workspace.db, "models_test", target_type="model", target_id=model_id)
    update_job(workspace.db, job_id, status="running")
    run_id = create_agent_run(
        workspace.db,
        job_id=job_id,
        agent_type="llm_model_test",
        task_type="models_test",
        provider=model.get("provider"),
        model=model_id,
        input_refs=[{"kind": "model", "model_id": model_id}],
    )
    endpoint = str(model.get("endpoint") or "")
    if model.get("capability") == "embedding":
        configured = bool(model.get("model_name"))
    else:
        configured = bool(endpoint and model.get("model_name"))
    if not configured:
        payload = {
            "status": "blocked",
            "result": "blocked",
            "reason": "local embedding model folder not configured or not found" if model.get("capability") == "embedding" else "model endpoint or model_name not configured",
            "model": {
                "id": model_id,
                "provider": model.get("provider"),
                "capability": model.get("capability"),
                "endpoint_configured": bool(endpoint) if model.get("capability") == "chat" else bool(_embedding_model_root(workspace)),
                "model_name_configured": bool(model.get("model_name")),
                "api_key_present": bool(os.environ.get(str(model.get("api_key_env") or ""))),
            },
            "phase_note": "Phase 1 records blocked/failure artifacts without leaking secret values.",
            "run_id": run_id,
            "job_id": job_id,
        }
        artifact = record_artifact(
            workspace,
            "model_test_report",
            "models_test",
            payload,
            "model",
            model_id,
            run_id,
            metadata=payload,
        )
        update_agent_run(workspace.db, run_id, status="blocked", output_refs=[artifact], artifact_id=artifact["artifact_id"])
        update_job(workspace.db, job_id, status="failed", output_refs=[artifact], error={"reason": payload["reason"]})
        return 3, {**payload, **artifact, "message": f"Model {model_id} test blocked"}
    started = time.monotonic()
    if model.get("capability") == "embedding":
        model_path = _resolve_embedding_model_path(workspace, str(model.get("model_name") or ""))
        model_root = _embedding_model_root(workspace)
        model_load_name = str(model_path) if model_path else str(model.get("model_name") or "")
        try:
            from fastembed import TextEmbedding  # type: ignore

            embedder = TextEmbedding(model_name=model_load_name, cache_dir=str(model_root))
            vector = next(iter(embedder.embed(["phase1 connectivity test"])))
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            payload = {
                "status": "ok",
                "result": "ok",
                "latency_ms": latency_ms,
                "embedding_dimension": len(list(vector)),
                "model": {
                    "id": model_id,
                    "provider": "local_embedding_folder",
                    "capability": "embedding",
                    "endpoint_configured": True,
                    "model_name_configured": True,
                    "api_key_present": False,
                    "model_root": str(model_root),
                    "model_path": str(model_path) if model_path else "",
                    "model_load_name": model_load_name,
                },
                "run_id": run_id,
                "job_id": job_id,
            }
            artifact = record_artifact(
                workspace,
                "model_test_report",
                "models_test",
                payload,
                "model",
                model_id,
                run_id,
                metadata=payload,
            )
            update_agent_run(workspace.db, run_id, status="succeeded", output_refs=[artifact], artifact_id=artifact["artifact_id"])
            update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
            return 0, {**payload, **artifact, "message": f"Model {model_id} test succeeded"}
        except Exception as exc:
            payload = {
                "status": "failed",
                "result": "failed",
                "reason": str(exc),
                "model": {
                    "id": model_id,
                    "provider": "local_embedding_folder",
                    "capability": "embedding",
                    "endpoint_configured": True,
                    "model_name_configured": True,
                    "api_key_present": False,
                    "model_root": str(model_root),
                    "model_path": str(model_path) if model_path else "",
                    "model_load_name": model_load_name,
                },
                "request": {"local_model_path_configured": bool(model_path), "cache_dir": str(model_root)},
                "run_id": run_id,
                "job_id": job_id,
            }
            artifact = record_artifact(workspace, "model_test_report", "models_test", payload, "model", model_id, run_id, metadata=payload)
            update_agent_run(workspace.db, run_id, status="failed", output_refs=[artifact], artifact_id=artifact["artifact_id"], error={"reason": str(exc)})
            update_job(workspace.db, job_id, status="failed", output_refs=[artifact], error={"reason": str(exc)})
            return 1, {**payload, **artifact, "message": f"Model {model_id} test failed"}
    try:
        body, headers = _build_request(model)
        request_endpoint = _request_endpoint(endpoint, model.get("request_format"))
        request = urllib.request.Request(request_endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=int(model.get("timeout_seconds") or 300)) as response:
            response_body = response.read()
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            payload = {
                "status": "ok",
                "result": "ok",
                "http_status": response.status,
                "latency_ms": latency_ms,
                "response_size_bytes": len(response_body),
                "model": {
                    "id": model_id,
                    "provider": model.get("provider"),
                    "capability": model.get("capability"),
                    "endpoint_configured": True,
                    "model_name_configured": True,
                    "api_key_present": bool(os.environ.get(str(model.get("api_key_env") or ""))),
                },
                "run_id": run_id,
                "job_id": job_id,
            }
            artifact = record_artifact(
                workspace,
                "model_test_report",
                "models_test",
                payload,
                "model",
                model_id,
                run_id,
                metadata=payload,
            )
            update_agent_run(workspace.db, run_id, status="succeeded", output_refs=[artifact], artifact_id=artifact["artifact_id"])
            update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
            return 0, {**payload, **artifact, "message": f"Model {model_id} test succeeded"}
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        payload = {
            "status": "failed",
            "result": "failed",
            "reason": str(exc),
            "model": {
                "id": model_id,
                "provider": model.get("provider"),
                "capability": model.get("capability"),
                "endpoint_configured": True,
                "model_name_configured": True,
                "api_key_present": bool(os.environ.get(str(model.get("api_key_env") or ""))),
            },
            # Never include Authorization header or raw request details here.
            # Credential-safe summary only.
            "request": {
                "endpoint_configured": True,
                "model_name_configured": True,
                "api_key_present": bool(os.environ.get(str(model.get("api_key_env") or ""))),
            },
            "run_id": run_id,
            "job_id": job_id,
        }
        artifact = record_artifact(
            workspace,
            "model_test_report",
            "models_test",
            payload,
            "model",
            model_id,
            run_id,
            metadata=payload,
        )
        update_agent_run(workspace.db, run_id, status="failed", output_refs=[artifact], artifact_id=artifact["artifact_id"], error={"reason": str(exc)})
        update_job(workspace.db, job_id, status="failed", output_refs=[artifact], error={"reason": str(exc)})
        return 1, {**payload, **artifact, "message": f"Model {model_id} test failed"}
