"""Changelog routes — operational / config / playbook change history surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ... import config as cfg
from . import changelog_store as store


router = APIRouter()


class CreateChangeModel(BaseModel):
    changed_by: str
    change_type: str
    before_state: Any = None
    after_state: Any = None
    reason: str
    source_file: str = ""
    affected_service: str = ""
    rollback_available: bool = False
    verification_evidence: str | None = None
    linked_wiki_pages: list[str] | None = None
    status: str = "pending"


class VerifyChangeModel(BaseModel):
    verification_evidence: str


@router.get("/changelog", response_class=HTMLResponse)
async def changelog_page(request: Request) -> HTMLResponse:
    """Render the changelog list page."""
    return request.app.state.templates.TemplateResponse(
        request,
        "changelog.html",
        {"page": "changelog"},
    )


@router.get("/api/changelog")
async def list_changes_api(
    request: Request,
    change_type: str | None = None,
    status: str | None = None,
) -> JSONResponse:
    """List change history entries, newest first, optionally filtered."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    entries = store.list_changes(paths, change_type=change_type, status=status)
    return JSONResponse({"changes": entries, "total": len(entries)})


@router.post("/api/changelog")
async def create_change_api(request: Request, data: CreateChangeModel) -> JSONResponse:
    """Record a new change history entry."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths

    # Validate change_type against known values
    valid_types = {t.value for t in store.ChangeType}
    if data.change_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid change_type '{data.change_type}'. Must be one of: {sorted(valid_types)}",
        )

    entry = store.create_change(
        paths=paths,
        changed_by=data.changed_by,
        change_type=data.change_type,
        before_state=data.before_state,
        after_state=data.after_state,
        reason=data.reason,
        source_file=data.source_file,
        affected_service=data.affected_service,
        rollback_available=data.rollback_available,
        verification_evidence=data.verification_evidence,
        linked_wiki_pages=data.linked_wiki_pages,
        status=data.status,
    )
    return JSONResponse({"status": "created", "change": entry}, status_code=201)


@router.post("/api/changelog/verify/{change_id}")
async def verify_change_api(
    request: Request,
    change_id: str,
    data: VerifyChangeModel,
) -> JSONResponse:
    """Mark a change as verified with the provided evidence."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths

    entry = store.update_change_status(
        paths=paths,
        change_id=change_id,
        new_status="verified",
        verification_evidence=data.verification_evidence,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Change '{change_id}' not found.")

    return JSONResponse({"status": "updated", "change": entry})
