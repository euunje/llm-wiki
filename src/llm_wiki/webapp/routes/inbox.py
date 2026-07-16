"""Inbox routes for reviewing and approving low-confidence classifications."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ... import config as cfg
from ... import db
from ... import inbox as inbox_domain
from ... import page_writer
from ... import relinker

router = APIRouter()

VALID_FILTER_STATES = {"all", "pending", "review", "failed"}

MAX_DIAGNOSTIC_BYTES = 16 * 1024  # 16 KiB cap for diagnostic content in API response


class PromotionModel(BaseModel):
    folder: str  # 'entities' | 'concepts' | 'synthesis'


class ReviewClassificationModel(BaseModel):
    target_kind: str | None = None
    target_folder: str | None = None
    tags: list[str] | None = None
    note: str | None = None
    candidate_slug: str | None = None
    candidate_action: str | None = None


def _safe_read_text(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _page_title(path: Path) -> str:
    parsed = page_writer.read_page(path)
    if parsed and isinstance(parsed.frontmatter.get("title"), str):
        title = parsed.frontmatter["title"].strip()
        if title:
            return title
    return path.stem


def _legacy_review_items(paths: cfg.WikiPaths) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not paths.non_categories.exists():
        return items
    for path in sorted(paths.non_categories.glob("*.md")):
        if path.name.startswith("."):
            continue
        parsed = page_writer.read_page(path)
        if parsed is None:
            continue
        items.append(
            {
                "key": f"legacy:{path.stem}",
                "source": "legacy_review",
                "item_id": None,
                "slug": path.stem,
                "title": parsed.frontmatter.get("title", path.stem),
                "state": "pending",
                "type": "pending",
                "confidence": parsed.frontmatter.get("confidence", "low"),
                "processed_at": parsed.frontmatter.get("processed_at", ""),
                "source_file": parsed.frontmatter.get("source_file", ""),
                "suggestedExternalOwner": parsed.frontmatter.get("suggestedExternalOwner", ""),
                "relpath": f"non_categories/{path.name}",
                "path": str(path),
                "body": parsed.body.strip(),
                "frontmatter": dict(parsed.frontmatter),
                "input_type": None,
                "error_message": None,
                "created_at": parsed.frontmatter.get("created", ""),
                "updated_at": parsed.frontmatter.get("updated", ""),
            }
        )
    return items


def _db_item_path(paths: cfg.WikiPaths, item: inbox_domain.InboxItem) -> Path | None:
    if not item.relpath:
        return None
    return (paths.root / item.relpath).resolve()


def _db_item_body(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    if path.suffix.lower() == ".md":
        parsed = page_writer.read_page(path)
        if parsed is not None:
            return parsed.body.strip()
    return _safe_read_text(path).strip()


def _db_item_frontmatter(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or path.suffix.lower() != ".md":
        return {}
    parsed = page_writer.read_page(path)
    return dict(parsed.frontmatter) if parsed is not None else {}


def _diagnostic_path_for_item(paths: cfg.WikiPaths, item: inbox_domain.InboxItem) -> Path | None:
    path = _db_item_path(paths, item)
    if path is None:
        return None
    diagnostic = path.parent / f"{path.name}.diagnostic.md"
    return diagnostic if diagnostic.exists() else None


def _db_workbench_items(paths: cfg.WikiPaths) -> list[dict[str, Any]]:
    with db.connect(paths.state_db) as conn:
        raw_items = inbox_domain.list_inbox_items(conn)
        event_map = {item.id: inbox_domain.list_inbox_events(conn, item.id) for item in raw_items}

    items: list[dict[str, Any]] = []
    for item in raw_items:
        if item.state not in {"pending", "review", "failed"}:
            continue
        path = _db_item_path(paths, item)
        frontmatter = _db_item_frontmatter(path)
        body = _db_item_body(path)
        title = item.title or frontmatter.get("title") or (path.stem if path else f"item-{item.id}")
        diagnostic_path = _diagnostic_path_for_item(paths, item)
        events = event_map.get(item.id, [])
        phase = ""
        reason = ""
        for event in reversed(events):
            phase = str(event.data.get("phase") or phase or "")
            reason = str(event.data.get("reason") or reason or "")
            if phase and reason:
                break
        items.append(
            {
                "key": f"db:{item.id}",
                "source": "inbox_item",
                "item_id": item.id,
                "slug": path.stem if path else f"item-{item.id}",
                "title": title,
                "state": item.state,
                "type": item.state,
                "confidence": frontmatter.get("confidence", item.state),
                "processed_at": frontmatter.get("processed_at", item.updated_at),
                "source_file": frontmatter.get("source_file", item.relpath or ""),
                "suggestedExternalOwner": frontmatter.get("suggestedExternalOwner", ""),
                "relpath": item.relpath,
                "path": str(path) if path else "",
                "body": body,
                "frontmatter": frontmatter,
                "input_type": item.input_type,
                "error_message": item.error_message,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "has_diagnostic": diagnostic_path is not None,
                "diagnostic_path": str(diagnostic_path) if diagnostic_path else None,
                "phase": phase,
                "reason": reason,
                "source_path": str(path) if path else None,
                "error": item.error_message,
                "log_preview": _safe_read_text(diagnostic_path)[:4000] if diagnostic_path else "",
            }
        )
    return items


def _candidate_paths(paths: cfg.WikiPaths) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    for folder_name, folder in (
        ("entities", paths.entities),
        ("concepts", paths.concepts),
        ("synthesis", paths.synthesis),
        ("non_categories", paths.non_categories),
    ):
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.md")):
            if not path.name.startswith("."):
                candidates.append((folder_name, path))
    return candidates


def _similar_candidates(paths: cfg.WikiPaths, item: dict[str, Any]) -> list[dict[str, Any]]:
    slug = str(item.get("slug") or "").strip().casefold()
    title = str(item.get("title") or "").strip().casefold()
    item_path = str(item.get("path") or "")
    matches: list[dict[str, Any]] = []
    try:
        for folder_name, path in _candidate_paths(paths):
            if str(path) == item_path:
                continue
            page_slug = path.stem.casefold()
            page_title = _page_title(path).strip().casefold()
            reason = None
            if slug and page_slug == slug:
                reason = "exact_slug"
            elif title and page_title == title:
                reason = "exact_title"
            if reason is None:
                continue
            matches.append(
                {
                    "slug": path.stem,
                    "title": _page_title(path),
                    "folder": folder_name,
                    "path": f"{folder_name}/{path.name}",
                    "reason": reason,
                    "similarity": 1.0,
                    "preview": _db_item_body(path)[:400],
                }
            )
    except Exception:
        return []
    return matches[:5]


def _item_events(paths: cfg.WikiPaths, item_id: int | None) -> list[dict[str, Any]]:
    if item_id is None:
        return []
    with db.connect(paths.state_db) as conn:
        events = inbox_domain.list_inbox_events(conn, item_id)
    return [
        {
            "seq": event.seq,
            "event_type": event.event_type,
            "from_state": event.from_state,
            "to_state": event.to_state,
            "relpath": event.relpath,
            "message": event.message,
            "data": event.data,
            "created_at": event.created_at,
        }
        for event in events
    ]


def _selected_item(items: list[dict[str, Any]], selected: str | None) -> dict[str, Any] | None:
    if not items:
        return None
    if selected:
        for item in items:
            if item["key"] == selected or str(item.get("item_id")) == selected or item["slug"] == selected:
                return item
    return items[0]


def _sort_value(item: dict[str, Any]) -> tuple[str, str]:
    primary = item.get("updated_at") or item.get("processed_at") or item.get("created_at") or ""
    return (str(primary), str(item.get("title") or ""))


def _workbench_context(paths: cfg.WikiPaths, *, filter_state: str, selected: str | None) -> dict[str, Any]:
    legacy_items = _legacy_review_items(paths)
    db_items = _db_workbench_items(paths)
    unified_items = sorted(
        [*legacy_items, *db_items],
        key=_sort_value,
        reverse=True,
    )

    counts = {
        "all": len(unified_items),
        "pending": sum(1 for item in unified_items if item["state"] == "pending"),
        "review": sum(1 for item in unified_items if item["state"] == "review"),
        "failed": sum(1 for item in db_items if item["state"] == "failed"),
    }
    if filter_state == "all":
        filtered_items = unified_items
    else:
        filtered_items = [item for item in unified_items if item["state"] == filter_state]
    selected_item = _selected_item(filtered_items, selected)
    selected_detail = None
    if selected_item is not None:
        selected_detail = {
            **selected_item,
            "candidates": _similar_candidates(paths, selected_item) if selected_item["state"] == "review" else [],
            "events": _item_events(paths, selected_item.get("item_id")),
            "diagnostic": None,
        }
        if selected_item.get("item_id") is not None and selected_item["state"] == "failed":
            db_item = _require_inbox_item(paths, int(selected_item["item_id"]))
            diagnostic_path = _diagnostic_path_for_item(paths, db_item)
            if diagnostic_path is not None:
                selected_detail["diagnostic"] = {
                    "path": str(diagnostic_path),
                    "content": _safe_read_text(diagnostic_path),
                }
    return {
        "legacy_items": legacy_items,
        "items": unified_items,
        "filtered_items": filtered_items,
        "counts": counts,
        "filter_state": filter_state,
        "selected_item": selected_item,
        "selected_detail": selected_detail,
        "available_states": ["all", "pending", "review", "failed"],
    }


def _to_item_namespace(value: dict[str, Any] | None) -> SimpleNamespace | None:
    if value is None:
        return None
    return SimpleNamespace(**_json_ready(value))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _require_inbox_item(paths: cfg.WikiPaths, item_id: int) -> inbox_domain.InboxItem:
    with db.connect(paths.state_db) as conn:
        item = inbox_domain.get_inbox_item(conn, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inbox item not found.")
    return item


def _serialize_item(paths: cfg.WikiPaths, item: inbox_domain.InboxItem) -> dict[str, Any]:
    path = _db_item_path(paths, item)
    diagnostic_path = _diagnostic_path_for_item(paths, item)
    return {
        "id": item.id,
        "source_id": item.source_id,
        "input_type": item.input_type,
        "state": item.state,
        "relpath": item.relpath,
        "title": item.title,
        "error_message": item.error_message,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "path": str(path) if path else None,
        "exists": path.exists() if path else False,
        "has_diagnostic": diagnostic_path is not None,
        "diagnostic_path": str(diagnostic_path) if diagnostic_path else None,
        "events": _item_events(paths, item.id),
        "candidates": _similar_candidates(
            paths,
            {
                "slug": path.stem if path else item.title or f"item-{item.id}",
                "title": item.title or (path.stem if path else f"item-{item.id}"),
                "path": str(path) if path else "",
                "state": item.state,
            },
        ) if item.state == "review" else [],
    }


def _remove_path_if_exists(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    path.unlink()
    return True


@router.get("/inbox", response_class=HTMLResponse)
async def inbox_view(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    filter_state = request.query_params.get("state", "all")
    if filter_state not in VALID_FILTER_STATES:
        filter_state = "all"
    selected = request.query_params.get("selected")
    workbench = _workbench_context(paths, filter_state=filter_state, selected=selected)

    return request.app.state.templates.TemplateResponse(
        request,
        "inbox.html",
        {
            "items": [_to_item_namespace(item) for item in workbench["items"]],
            "filtered_items": [_to_item_namespace(item) for item in workbench["filtered_items"]],
            "page": "inbox",
            "active_state": workbench["filter_state"],
            "filter_state": workbench["filter_state"],
            "filter_counts": workbench["counts"],
            "counts": workbench["counts"],
            "workbench_items": workbench["filtered_items"],
            "selected_item": _to_item_namespace(workbench["selected_detail"]),
            "selected_detail": _to_item_namespace(workbench["selected_detail"]),
            "available_states": workbench["available_states"],
            "workbench": workbench,
        },
    )


@router.get("/api/inbox/items/{item_id}")
async def inbox_item_detail(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    return JSONResponse({"status": "success", "item": _serialize_item(paths, item)})


@router.post("/api/inbox/items/{item_id}/hold")
async def hold_inbox_item(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    result = inbox_domain.move_to_archive(
        paths,
        item_id,
        message="Held from inbox workbench.",
        data={"requested_action": "hold"},
    )
    if not result.moved:
        raise HTTPException(status_code=409, detail="Failed to archive inbox item.")
    diagnostic_deleted = _remove_path_if_exists(_diagnostic_path_for_item(paths, result.item))
    item = _require_inbox_item(paths, item_id)
    return JSONResponse(
        {
            "status": "success",
            "action": "hold",
            "diagnostic_deleted": diagnostic_deleted,
            "item": _serialize_item(paths, item),
        }
    )


@router.post("/api/inbox/items/{item_id}/retry")
async def retry_failed_item(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    if item.state != inbox_domain.InboxState.FAILED.value:
        raise HTTPException(status_code=409, detail="Only failed inbox items can be retried.")
    diagnostic_path = _diagnostic_path_for_item(paths, item)
    result = inbox_domain.move_to_pending(
        paths,
        item_id,
        message="Retry requested from inbox workbench.",
        data={"requested_action": "retry"},
    )
    if not result.moved:
        raise HTTPException(status_code=409, detail="Failed to move inbox item back to pending.")
    diagnostic_deleted = _remove_path_if_exists(diagnostic_path)
    updated = _require_inbox_item(paths, item_id)
    return JSONResponse(
        {
            "status": "success",
            "action": "retry",
            "diagnostic_deleted": diagnostic_deleted,
            "item": _serialize_item(paths, updated),
            "note": "Retry currently restores the file to the input-type inbox folder and resets state to pending.",
        }
    )


@router.post("/api/inbox/items/{item_id}/reprocess")
async def reprocess_review_item(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    if item.state not in {inbox_domain.InboxState.REVIEW.value, inbox_domain.InboxState.FAILED.value}:
        raise HTTPException(status_code=409, detail="Only review or failed inbox items can be reprocessed.")
    if item.state == inbox_domain.InboxState.FAILED.value:
        return await retry_failed_item(request, item_id)
    result = inbox_domain.move_to_pending(
        paths,
        item_id,
        message="Reprocess requested from inbox workbench.",
        data={"requested_action": "reprocess"},
    )
    if not result.moved:
        raise HTTPException(status_code=409, detail="Failed to move inbox item back to pending.")
    updated = _require_inbox_item(paths, item_id)
    return JSONResponse({"status": "success", "action": "reprocess", "item": _serialize_item(paths, updated)})


@router.post("/api/inbox/items/{item_id}/classify")
async def classify_review_item(request: Request, item_id: int, body: ReviewClassificationModel) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    with db.connect(paths.state_db) as conn:
        inbox_domain.append_inbox_event(
            conn,
            inbox_item_id=item_id,
            event_type="review_classification_submitted",
            from_state=item.state,
            to_state=item.state,
            relpath=item.relpath,
            message="Review classification submitted from inbox workbench.",
            data={
                "target_kind": body.target_kind,
                "target_folder": body.target_folder,
                "tags": body.tags or [],
                "note": body.note,
                "candidate_slug": body.candidate_slug,
                "candidate_action": body.candidate_action,
                "db_state": item.state,
                "retryable": True,
            },
        )
    updated = _require_inbox_item(paths, item_id)
    return JSONResponse({"status": "success", "action": "classify", "item": _serialize_item(paths, updated)})


@router.get("/api/inbox/items/{item_id}/diagnostic")
async def read_failed_diagnostic(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    diagnostic_path = _diagnostic_path_for_item(paths, item)
    if diagnostic_path is None:
        raise HTTPException(status_code=404, detail="Diagnostic not found.")
    content = _safe_read_text(diagnostic_path)
    truncated = len(content) > MAX_DIAGNOSTIC_BYTES
    if truncated:
        content = content[:MAX_DIAGNOSTIC_BYTES]
    response_data = {
        "status": "success",
        "item_id": item_id,
        "diagnostic": {"path": str(diagnostic_path), "content": content},
        "truncated": truncated,
    }
    if truncated:
        response_data["cap_bytes"] = MAX_DIAGNOSTIC_BYTES
    return JSONResponse(response_data)


@router.delete("/api/inbox/items/{item_id}/diagnostic")
async def delete_failed_diagnostic(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    diagnostic_path = _diagnostic_path_for_item(paths, item)
    if diagnostic_path is None:
        raise HTTPException(status_code=404, detail="Diagnostic not found.")
    diagnostic_path.unlink()
    with db.connect(paths.state_db) as conn:
        inbox_domain.append_inbox_event(
            conn,
            inbox_item_id=item_id,
            event_type="failed_diagnostic_deleted",
            from_state=item.state,
            to_state=item.state,
            relpath=item.relpath,
            message="Failed diagnostic deleted from inbox workbench.",
            data={"db_state": item.state, "retryable": item.state == inbox_domain.InboxState.FAILED.value},
        )
    return JSONResponse({"status": "success", "action": "diagnostic_delete", "item_id": item_id})


@router.delete("/api/inbox/items/{item_id}")
async def delete_inbox_item(request: Request, item_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    item = _require_inbox_item(paths, item_id)
    item_path = _db_item_path(paths, item)
    diagnostic_path = _diagnostic_path_for_item(paths, item)
    source_deleted = _remove_path_if_exists(item_path)
    diagnostic_deleted = _remove_path_if_exists(diagnostic_path)
    with db.connect(paths.state_db) as conn:
        conn.execute("DELETE FROM inbox_events WHERE inbox_item_id = ?", (item_id,))
        conn.execute("DELETE FROM inbox_items WHERE id = ?", (item_id,))
    return JSONResponse(
        {
            "status": "success",
            "action": "delete",
            "item_id": item_id,
            "source_deleted": source_deleted,
            "diagnostic_deleted": diagnostic_deleted,
        }
    )


@router.post("/api/inbox/promote/{slug}")
async def promote_document(request: Request, slug: str, body: PromotionModel) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths

    if body.folder not in ("entities", "concepts", "synthesis"):
        raise HTTPException(status_code=400, detail="Invalid target folder selection.")

    success = relinker.promote_file(paths, slug, body.folder)
    if not success:
        raise HTTPException(status_code=404, detail="Pending review document not found.")

    return JSONResponse({"status": "success", "message": f"Document promoted to {body.folder}/."})


@router.delete("/api/inbox/delete/{slug}")
async def delete_document(request: Request, slug: str) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    doc_path = paths.non_categories / f"{slug}.md"

    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        doc_path.unlink()

        old_wiki_path = f"non_categories/{slug}.md"
        with db.connect(paths.state_db) as conn:
            conn.execute("DELETE FROM source_pages WHERE wiki_path = ?", (old_wiki_path,))

        import datetime

        page_writer.rebuild_index(paths, datetime.date.today().isoformat())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse({"status": "success", "message": "Document deleted."})
