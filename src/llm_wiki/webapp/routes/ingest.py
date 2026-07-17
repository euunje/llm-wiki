"""Ingest route — persistent-jobs version.

Flow:
  1. GET /ingest — landing page with drag-drop upload + pending list + recent jobs
  2. POST /ingest/upload — accept files and register inbox items
  3. POST /ingest/start — create a job for a given inbox_item_id/source_id, queue it
  4. GET /ingest/jobs/{job_id}/stream — SSE: replay history + live tail

Because progress is persisted in SQLite (via jobs.py), closing the tab and
coming back still shows full history. Multiple tabs can watch the same job.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ... import config as cfg
from ... import db
from ... import inbox
from ... import ingest_raw
from ... import jobs as jobs_module

router = APIRouter()


def _register_upload(paths: cfg.WikiPaths, filename: str, content: bytes) -> inbox.InboxRegistrationResult:
    return inbox.register_uploaded_bytes(paths, filename=filename, content=content)


def _coerce_tags(raw_tags: list[str]) -> list[str]:
    tags: list[str] = []
    for raw_tag in raw_tags:
        for part in raw_tag.split(","):
            tag = part.strip()
            if tag:
                tags.append(tag)
    return tags


def _register_raw_source_in_inbox(
    paths: cfg.WikiPaths,
    file_path,
) -> inbox.InboxRegistrationResult:
    suffix = file_path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return inbox.register_markdown_file(paths, file_path, copy=False)
    return inbox.register_document_file(paths, file_path, copy=False)


@router.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    queue_items: list[dict] = []

    # Primary queue: Inbox pending items (Phase 5B Inbox-first flow)
    with db.connect(paths.state_db) as conn:
        inbox_pending = inbox.list_inbox_items(conn, state=inbox.InboxState.PENDING)
    for item in inbox_pending:
        queue_items.append(
            {
                "inbox_item_id": item.id,
                "source_id": item.source_id,
                "relpath": item.relpath or "",
                "input_type": item.input_type,
                "status": item.state,
                "is_legacy": False,
            }
        )

    # Legacy error sources: kept for backward-compatible retry visibility
    # Filter out sources with linked inbox items to prevent duplicates when an
    # inbox-linked ingest fails (source shows "error", inbox item shows "pending")
    legacy_error_sources = []
    for s in ingest_raw.list_sources(paths):
        if s.get("status") == "error":
            if inbox.linked_inbox_item_id_for_source(paths, s["id"]) is None:
                legacy_error_sources.append(s)
    for src in legacy_error_sources:
        queue_items.append(
            {
                "inbox_item_id": None,
                "source_id": src["id"],
                "relpath": src.get("relpath", ""),
                "input_type": src.get("file_type", ""),
                "status": "error",
                "is_legacy": True,
            }
        )

    recent_jobs = jobs_module.list_jobs(paths, limit=20)
    return request.app.state.templates.TemplateResponse(
        request,
        "ingest.html",
        {"queue_items": queue_items, "recent_jobs": recent_jobs, "page": "ingest"},
    )


@router.post("/ingest/upload")
async def ingest_upload(
    request: Request, files: list[UploadFile] = File(...)
) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths

    results = []
    for up in files:
        if not up.filename:
            continue
        content = await up.read()
        registration = _register_upload(paths, up.filename, content)
        item = registration.item
        results.append(
            {
                "filename": up.filename,
                "inbox_item_id": item.id,
                "relpath": item.relpath,
                "state": item.state,
                "input_type": item.input_type,
                "source_id": item.source_id,
                "deduped": registration.deduped,
            }
        )
    return JSONResponse({"ok": True, "files": results})


@router.post("/ingest/paste")
async def ingest_paste(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    source_url: str = Form(""),
    tags: list[str] = Form(default=[]),
) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    if not title.strip():
        raise HTTPException(status_code=400, detail="title required")
    if not body.strip():
        raise HTTPException(status_code=400, detail="body required")
    registration = inbox.register_pasted_text(
        paths,
        title=title.strip(),
        body=body,
        source_url=source_url.strip() or None,
        tags=_coerce_tags(tags),
    )
    item = registration.item
    return JSONResponse(
        {
            "ok": True,
            "inbox_item_id": item.id,
            "relpath": item.relpath,
            "state": item.state,
            "input_type": item.input_type,
            "source_id": item.source_id,
            "deduped": registration.deduped,
        }
    )


@router.post("/ingest/scan")
async def ingest_scan(request: Request) -> JSONResponse:
    """Import supported Raw Sources files into Inbox pending items."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    paths.raw.mkdir(parents=True, exist_ok=True)

    counts = {"registered": 0, "deduped": 0, "skipped": 0, "errors": 0}
    files = list(ingest_raw.iter_addable_files(paths.raw, recursive=True))
    results = []
    for file_path in files:
        try:
            registration = _register_raw_source_in_inbox(paths, file_path)
        except ValueError as exc:
            counts["skipped"] += 1
            results.append(
                {
                    "path": str(file_path.relative_to(paths.root)),
                    "result": "skipped_unsupported",
                    "message": str(exc),
                }
            )
            continue
        except Exception as exc:
            counts["errors"] += 1
            results.append(
                {
                    "path": str(file_path.relative_to(paths.root)),
                    "result": "error",
                    "message": str(exc),
                }
            )
            continue

        item = registration.item
        if registration.deduped:
            counts["deduped"] += 1
        else:
            counts["registered"] += 1
        results.append(
            {
                "path": str(file_path.relative_to(paths.root)),
                "result": "deduped" if registration.deduped else "registered",
                "inbox_item_id": item.id,
                "relpath": item.relpath,
                "state": item.state,
                "source_id": item.source_id,
            }
        )

    counts["added"] = counts["registered"]
    with db.connect(paths.state_db) as conn:
        pending_count = len(inbox.list_inbox_items(conn, state=inbox.InboxState.PENDING))
    return JSONResponse(
        {
            "ok": True,
            "scanned": len(files),
            "pending_count": pending_count,
            "counts": counts,
            "results": results,
        }
    )


@router.post("/ingest/start")
async def ingest_start(request: Request) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    form = await request.form()
    inbox_item_id_raw = form.get("inbox_item_id")
    source_id_raw = form.get("source_id")
    inbox_item_id: int | None = None
    source_id: int

    if inbox_item_id_raw is not None:
        try:
            inbox_item_id = int(inbox_item_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="inbox_item_id must be int")
        try:
            materialized = inbox.materialize_source_for_inbox_item(paths, inbox_item_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        source_id = materialized.source_id
    elif source_id_raw is not None:
        try:
            source_id = int(source_id_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="source_id must be int")
    else:
        raise HTTPException(status_code=400, detail="inbox_item_id or source_id required")

    row = ingest_raw.get_source(paths, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No source with id {source_id}")
    if row.get("status") != "pending":
        ok, message = ingest_raw.mark_source_pending(paths, source_id)
        if not ok:
            raise HTTPException(status_code=400, detail=message)
    manager = jobs_module.get_manager(paths)
    job_id = manager.enqueue(source_id)
    return JSONResponse(
        {"ok": True, "inbox_item_id": inbox_item_id, "source_id": source_id, "job_id": job_id}
    )


@router.get("/ingest/jobs/{job_id}/stream")
async def ingest_job_stream(request: Request, job_id: int) -> StreamingResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    if jobs_module.get_job(paths, job_id) is None:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")

    async def generator():
        last_seq = -1
        last_job_snapshot: tuple | None = None
        terminal_states = {"done", "failed", "interrupted"}
        job = jobs_module.get_job(paths, job_id)
        if job:
            last_job_snapshot = (job.state, job.phase, job.progress, job.pages_created, job.pages_updated, job.error)
            yield (
                f"event: job\ndata: "
                f"{json.dumps({'state': job.state, 'phase': job.phase, 'progress': job.progress, 'pages_created': job.pages_created, 'pages_updated': job.pages_updated, 'error': job.error})}\n\n"
            )
        for _ in range(3600):
            if await request.is_disconnected():
                break
            events = jobs_module.get_events_since(paths, job_id, last_seq)
            for ev in events:
                yield f"event: {ev['kind']}\ndata: {json.dumps(ev['data'])}\n\n"
                last_seq = ev["seq"]
            job = jobs_module.get_job(paths, job_id)
            if job is None:
                break
            snapshot = (job.state, job.phase, job.progress, job.pages_created, job.pages_updated, job.error)
            if snapshot != last_job_snapshot:
                yield (
                    f"event: job\ndata: "
                    f"{json.dumps({'state': job.state, 'phase': job.phase, 'progress': job.progress, 'pages_created': job.pages_created, 'pages_updated': job.pages_updated, 'error': job.error})}\n\n"
                )
                last_job_snapshot = snapshot
            if job.state in terminal_states:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    all_jobs = jobs_module.list_jobs(paths, limit=50)
    counts = {"queued": 0, "running": 0, "done": 0, "failed": 0, "interrupted": 0}
    for j in all_jobs:
        counts[j.state] = counts.get(j.state, 0) + 1
    return request.app.state.templates.TemplateResponse(
        request,
        "jobs.html",
        {"jobs": all_jobs, "counts": counts, "page": "jobs"},
    )


@router.get("/api/jobs")
async def api_jobs(request: Request) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    all_jobs = jobs_module.list_jobs(paths, limit=50)
    return JSONResponse(
        {
            "jobs": [
                {
                    "id": j.id,
                    "inbox_item_id": j.inbox_item_id,
                    "source_id": j.source_id,
                    "source_relpath": j.source_relpath,
                    "source_type": j.source_type,
                    "state": j.state,
                    "phase": j.phase,
                    "progress": j.progress,
                    "pages_created": j.pages_created,
                    "pages_updated": j.pages_updated,
                    "error": j.error,
                    "created_at": j.created_at,
                    "started_at": j.started_at,
                    "finished_at": j.finished_at,
                }
                for j in all_jobs
            ]
        }
    )


@router.post("/api/reprocess/{source_id}")
async def api_reprocess(request: Request, source_id: int) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    row = ingest_raw.get_source(paths, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No source with id {source_id}")
        
    from ... import db as db_module
    with db_module.connect(paths.state_db) as conn:
        conn.execute(
            "UPDATE sources SET status = 'pending' WHERE id = ?", (source_id,)
        )
        
    manager = jobs_module.get_manager(paths)
    job_id = manager.enqueue(source_id)
    return JSONResponse({"ok": True, "job_id": job_id})
