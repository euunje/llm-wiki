"""Lint route — health check report with one-click auto-fix.

Reuses lint.run_lint() and lint.apply_fixes() directly. Deep checks
(LLM-powered contradiction detection) are CLI-only — too slow for the UI.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import json
import queue
import threading

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ... import config as cfg
from ... import lint as lint_module

router = APIRouter()


def _sse_format(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _group_issues_by_severity(report: lint_module.LintReport) -> dict:
    """Group issues into errors / warnings / infos for template rendering."""
    grouped: dict[str, list] = {"errors": [], "warnings": [], "infos": []}
    for issue in report.issues:
        if issue.severity == lint_module.Severity.ERROR:
            grouped["errors"].append(issue)
        elif issue.severity == lint_module.Severity.WARNING:
            grouped["warnings"].append(issue)
        else:
            grouped["infos"].append(issue)
    return grouped


def _decorate_issues(issues: list) -> list:
    """Convert LintIssue dataclasses to template-friendly dicts."""
    return [
        {
            "check": issue.check.value,
            "severity": issue.severity.value,
            "page": issue.page,
            "message": issue.message,
            "suggestion": issue.suggestion,
            "fixable": issue.fixable,
        }
        for issue in issues
    ]


def _render_lint_response(request: Request, report: lint_module.LintReport, *, auto_fixed: int, just_fixed: bool) -> HTMLResponse:
    grouped = _group_issues_by_severity(report)
    warnings_by_page: dict[str, list] = defaultdict(list)
    for issue in grouped["warnings"]:
        warnings_by_page[issue.page].append(issue)

    fixable_count = sum(1 for i in report.issues if i.fixable)

    return request.app.state.templates.TemplateResponse(
        request,
        "lint.html",
        {
            "page": "lint",
            "report": {
                "score": report.health_score,
                "pages_checked": report.pages_checked,
                "duration": report.duration_seconds,
                "errors_count": len(grouped["errors"]),
                "warnings_count": len(grouped["warnings"]),
                "infos_count": len(grouped["infos"]),
                "auto_fixed": auto_fixed,
            },
            "errors": _decorate_issues(grouped["errors"]),
            "warnings": _decorate_issues(grouped["warnings"]),
            "infos": _decorate_issues(grouped["infos"]),
            "warnings_by_page": {
                page: _decorate_issues(issues)
                for page, issues in warnings_by_page.items()
            },
            "fixable_count": fixable_count,
            "just_fixed": just_fixed,
        },
    )


def _run_fix_and_relint(paths: cfg.WikiPaths) -> tuple[lint_module.LintReport, int]:
    initial = lint_module.run_lint(paths, deep=False)
    fixed_count = lint_module.apply_fixes(paths, initial.issues)
    report = lint_module.run_lint(paths, deep=False)
    report.auto_fixed = fixed_count
    return report, fixed_count


@router.get("/lint", response_class=HTMLResponse)
async def lint_page(request: Request) -> HTMLResponse:
    """Run fast lint checks and render the report."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    report = lint_module.run_lint(paths, deep=False)
    return _render_lint_response(request, report, auto_fixed=report.auto_fixed, just_fixed=False)


@router.post("/lint/fix", response_class=HTMLResponse)
async def lint_fix(request: Request) -> HTMLResponse:
    """Run lint, apply fixable issues, then re-render the report."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths
    report, fixed_count = _run_fix_and_relint(paths)
    return _render_lint_response(request, report, auto_fixed=fixed_count, just_fixed=True)


@router.get("/lint/fix/stream")
async def lint_fix_stream(request: Request) -> StreamingResponse:
    """Stream lint auto-fix progress for the browser UI via SSE."""
    paths: cfg.WikiPaths = request.app.state.wiki_paths

    async def generator():
        events: "queue.Queue[tuple[str, dict] | None]" = queue.Queue()

        def worker() -> None:
            try:
                initial = lint_module.run_lint(paths, deep=False)
                initial_fixable = sum(1 for issue in initial.issues if issue.fixable)
                events.put((
                    "progress",
                    {
                        "phase": "scan",
                        "message": "Lint scan complete.",
                        "progress": 0.0,
                        "fixed_count": 0,
                        "remaining_fixable": initial_fixable,
                        "current_page": None,
                    },
                ))

                def on_progress(update: lint_module.LintFixProgress) -> None:
                    events.put((
                        "progress",
                        {
                            "phase": update.phase,
                            "message": update.message,
                            "progress": update.progress,
                            "fixed_count": update.fixed_count,
                            "remaining_fixable": update.remaining_fixable,
                            "current_page": update.current_page,
                        },
                    ))

                fixed_count = lint_module.apply_fixes(paths, initial.issues, progress_callback=on_progress)
                report = lint_module.run_lint(paths, deep=False)
                remaining_fixable = sum(1 for issue in report.issues if issue.fixable)
                events.put((
                    "complete",
                    {
                        "phase": "complete",
                        "message": "Lint auto-fix complete.",
                        "progress": 1.0,
                        "fixed_count": fixed_count,
                        "remaining_fixable": remaining_fixable,
                        "current_page": None,
                        "redirect_url": "/lint",
                        "completed": True,
                    },
                ))
            except Exception as exc:
                events.put((
                    "error",
                    {
                        "phase": "error",
                        "message": str(exc),
                        "progress": 1.0,
                        "fixed_count": 0,
                        "remaining_fixable": 0,
                        "current_page": None,
                    },
                ))
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()

        while True:
            if await request.is_disconnected():
                break
            item = await asyncio.to_thread(events.get)
            if item is None:
                break
            event, payload = item
            yield _sse_format(event, payload)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
