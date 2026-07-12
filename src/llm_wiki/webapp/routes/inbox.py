"""Inbox routes for reviewing and approving low-confidence classifications."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from pydantic import BaseModel

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from ... import config as cfg
from ... import db
from ... import page_writer
from ... import relinker

router = APIRouter()


class PromotionModel(BaseModel):
    folder: str  # 'entities' | 'concepts' | 'synthesis'


@router.get("/inbox", response_class=HTMLResponse)
async def inbox_view(request: Request) -> HTMLResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    non_cat_dir = paths.non_categories
    
    items = []
    if non_cat_dir.exists():
        for path in sorted(non_cat_dir.glob("*.md")):
            if path.name.startswith("."):
                continue
            parsed = page_writer.read_page(path)
            if parsed:
                items.append({
                    "slug": path.stem,
                    "title": parsed.frontmatter.get("title", path.stem),
                    "confidence": parsed.frontmatter.get("confidence", "low"),
                    "processed_at": parsed.frontmatter.get("processed_at", ""),
                    "source_file": parsed.frontmatter.get("source_file", ""),
                    "body": parsed.body.strip()
                })
                
    return request.app.state.templates.TemplateResponse(
        request,
        "inbox.html",
        {
            "items": items,
            "page": "inbox",
        },
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
        # Delete file from disk
        doc_path.unlink()
        
        # Clean up database references
        old_wiki_path = f"non_categories/{slug}.md"
        with db.connect(paths.state_db) as conn:
            conn.execute("DELETE FROM source_pages WHERE wiki_path = ?", (old_wiki_path,))
            
        # Rebuild index
        import datetime
        page_writer.rebuild_index(paths, datetime.date.today().isoformat())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return JSONResponse({"status": "success", "message": "Document deleted."})
