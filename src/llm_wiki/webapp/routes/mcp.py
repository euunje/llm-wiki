"""MCP (Model Context Protocol) server endpoint integration route."""

from __future__ import annotations

import json
import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from ... import config as cfg
from ... import search
from ... import page_writer

router = APIRouter()

# Active SSE connection queues: connection_id -> asyncio.Queue
_active_connections: dict[str, asyncio.Queue] = {}


def handle_mcp_request(paths: cfg.WikiPaths, request_dict: dict) -> dict:
    req_id = request_dict.get("id")
    method = request_dict.get("method")
    
    response = {
        "jsonrpc": "2.0",
        "id": req_id
    }
    
    if method == "tools/list" or method == "listTools":
        response["result"] = {
            "tools": [
                {
                    "name": "list_wiki_pages",
                    "description": "List all pages and categories in the wiki",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "get_page_content",
                    "description": "Read markdown body of a specific wiki page by path (e.g. entities/openai.md)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to page, e.g. entities/openai.md"
                            }
                        },
                        "required": ["path"]
                    }
                },
                {
                    "name": "search_wiki",
                    "description": "Perform keyword/semantic search over the wiki contents",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search keyword or natural language query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
        return response
        
    elif method == "tools/call" or method == "callTool":
        params = request_dict.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "list_wiki_pages":
            pages_list = []
            for sub in ("sources", "entities", "concepts", "synthesis", "non_categories"):
                dir_path = paths.wiki / sub
                if dir_path.exists():
                    for f in dir_path.glob("*.md"):
                        if not f.name.startswith("."):
                            pages_list.append(f"{sub}/{f.name}")
            
            result_text = "Pages:\n" + "\n".join(f"- {p}" for p in pages_list)
            response["result"] = {
                "content": [
                    {
                        "type": "text",
                        "text": result_text
                    }
                ]
            }
            return response
            
        elif tool_name == "get_page_content":
            page_path_str = args.get("path", "")
            clean_path = page_path_str.replace("..", "").strip("/")
            full_path = paths.wiki / clean_path
            
            if not full_path.exists() or not full_path.is_file():
                response["error"] = {
                    "code": -32602,
                    "message": f"Page not found: {page_path_str}"
                }
                return response
                
            try:
                content = full_path.read_text(encoding="utf-8")
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            except Exception as e:
                response["error"] = {
                    "code": -32603,
                    "message": str(e)
                }
            return response
            
        elif tool_name == "search_wiki":
            query_str = args.get("query", "")
            if not query_str:
                response["error"] = {
                    "code": -32602,
                    "message": "Query parameter is required."
                }
                return response
                
            from ... import search as search_module
            try:
                if search_module.is_available():
                    res = search_module.query(paths, query_str, mode="hybrid", limit=10)
                    hits_text = []
                    for hit in res.hits:
                        hits_text.append(f"Page: {hit.path}\nTitle: {hit.title}\nSnippet: {hit.snippet}\nScore: {hit.score}\n---")
                    
                    result_text = "\n\n".join(hits_text) if hits_text else "No search results found."
                else:
                    matches = []
                    for sub in ("sources", "entities", "concepts", "synthesis"):
                        dir_path = paths.wiki / sub
                        if dir_path.exists():
                            for f in dir_path.glob("*.md"):
                                try:
                                    txt = f.read_text(encoding="utf-8")
                                    if query_str.lower() in txt.lower():
                                        matches.append(f"{sub}/{f.name}")
                                except Exception:
                                    pass
                    result_text = "Matching pages:\n" + "\n".join(f"- {m}" for m in matches) if matches else "No matches found."
                    
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text
                        }
                    ]
                }
            except Exception as e:
                response["error"] = {
                    "code": -32603,
                    "message": str(e)
                }
            return response
            
    response["error"] = {
        "code": -32601,
        "message": "Method not found"
    }
    return response


@router.get("/mcp")
async def mcp_sse_handshake(request: Request):
    conn_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    _active_connections[conn_id] = queue
    
    async def event_generator():
        # First yield the endpoint event mapping
        yield f"event: endpoint\ndata: /api/mcp/message?connection_id={conn_id}\n\n"
        
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _active_connections.pop(conn_id, None)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/mcp/message")
async def mcp_message_handler(request: Request, connection_id: str) -> JSONResponse:
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
        
    response = handle_mcp_request(paths, body)
    
    # Send response back via SSE if connection exists
    if connection_id in _active_connections:
        await _active_connections[connection_id].put(response)
        return JSONResponse({"status": "accepted"})
    else:
        # Fallback to direct HTTP response if connection closed or directly requesting
        return JSONResponse(response)
