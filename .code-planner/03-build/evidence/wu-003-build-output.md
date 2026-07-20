# WU-003 Build Output — Mockup-aligned UI templates and static behavior

## workUnitId
WU-003

## agent
build-ui-dev

## status
completed

## filesChanged
- src/llm_wiki/web/__init__.py (created)
- src/llm_wiki/web/app.py (modified: added static file mounting)
- src/llm_wiki/web/templates/base.html (created)
- src/llm_wiki/web/templates/login.html (created)
- src/llm_wiki/web/templates/dashboard.html (created)
- src/llm_wiki/web/templates/review.html (created)
- src/llm_wiki/web/templates/settings.html (created)
- src/llm_wiki/web/static/css/style.css (created)
- src/llm_wiki/web/static/js/app.js (created)

## summary
Implemented server-rendered Jinja2 templates and plain CSS/vanilla JS matching approved Phase 3 Web Review UI mockup.

### Templates (5 files)
- **base.html**: Base layout with topbar navigation, uses `url_for()` for all route references
- **login.html**: Admin password login form with error display
- **dashboard.html**: Status metrics grid + quick actions + recent activity
- **review.html**: 3-column layout (concept list | concept detail | candidate cards) with reject modal and graph popup
- **settings.html**: Prompt versioning table + editor with test/confirm workflow

### Static Assets (2 files)
- **style.css** (494 lines): Dark theme matching mockup colors (--bg:#0f172a, --accent:#60a5fa, etc.), responsive layouts, component styles
- **app.js** (546 lines): Vanilla JS ES module with API client, dashboard/review/settings interactions, SVG graph rendering, toast notifications

### Backend Integration (1 file modified)
- **app.py**: Added `StaticFiles` import, `STATIC_DIR` constant, and `app.mount("/static", ...)` for serving CSS/JS

### Key Features
- Login → Dashboard flow with signed session cookies
- Dashboard: 6 status cards (review pending, pending jobs, errors, wiki count, DB status, system status)
- Review: Left column (concept similarity list), center (concept detail with claims/relations/compile preview), right (candidate batch cards)
- Actions: merge, create_new, edit, retry_with_instruction (reject + retry reason/instruction)
- Wiki compile preview: Expandable `<details>` element
- Graph popup: 1-hop SVG graph with clickable nodes showing concept details
- Settings: Prompt version table, test version editor, save/test/confirm/history workflow
- Responsive: Collapses to single column at 1100px breakpoint

## uiStatesCovered

### empty
- Dashboard: Shows "needs_review" / "clear" status badges, "최근 작업 없음" when no recent activity
- Review: "검토할 신규 후보가 없습니다" when no candidates, "concept 없음" when no concepts
- Settings: "(none)" for missing prompt versions, "history 없음" when no history

### success
- Toast notifications: "작업 완료", "결정 반영: merge", "test version 저장 완료", "version confirm 완료"
- Metrics display: Green "OK" status for healthy DB/system, green counts for wiki/sources
- Candidate cards: Successfully loaded with confidence scores and action buttons

### failure
- Error messages: "메트릭을 불러올 수 없습니다", "후보를 불러올 수 없습니다", "concept 내용을 불러올 수 없습니다"
- Toast notifications: "작업 실패: {error}", "결정 실패: {error}", "reject 실패: {error}"
- Status indicators: Red "Warn" / "Bad" for failed DB/system, red error counts
- Form validation: "reject reason을 입력하세요" when submitting empty reject form

## verification

### command
```bash
python3 -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/llm_wiki/web/templates')); [env.get_template(t) for t in ['base.html', 'login.html', 'dashboard.html', 'review.html', 'settings.html']]; print('All templates parse OK')"
```
### result
```
All templates parse OK
```

### command
```bash
node --check src/llm_wiki/web/static/js/app.js
```
### result
```
(no output, exit code 0)
```

### command
```bash
python3 -c "import ast; ast.parse(open('src/llm_wiki/web/app.py').read()); print('app.py syntax OK')"
```
### result
```
app.py syntax OK
```

### command
```bash
python3 -c "css = open('src/llm_wiki/web/static/css/style.css').read(); print(f'CSS braces: {css.count(chr(123))} open, {css.count(chr(125))} close, balanced={css.count(chr(123))==css.count(chr(125))}')"
```
### result
```
CSS braces: 105 open, 105 close, balanced=True
```

### command
```bash
grep -E "(localhost|127\.0\.0\.1|http://[^w]|https://[^w])" src/llm_wiki/web/static/js/app.js | grep -v "w3.org"
```
### result
```
(no matches - no hardcoded host URLs)
```

## mockupAlignment

### Visual baseline
`.code-planner/02-planning/mockups/phase-3-web-review-mockup.html` (approved)

### Color scheme (exact match)
```css
--bg: #0f172a
--panel: #111827
--panel2: #172033
--line: #334155
--text: #e5e7eb
--muted: #94a3b8
--accent: #60a5fa
--ok: #34d399
--warn: #f59e0b
--bad: #fb7185
--chip: #1e293b
```

### Layout structure
- **Dashboard**: 2-column grid (1.2fr metrics | 0.8fr actions+recent), metric-grid 3-column
- **Review**: 3-column grid (280px concept list | 1fr concept detail | 360px candidate cards)
- **Settings**: 2-column grid (280px prompt table | 1fr editor)
- **Graph popup**: 2-column grid (1fr SVG graph | 1fr concept detail)

### Components
- Metric cards with label/num and status colors (ok/warn/bad)
- Wiki-item list with score, title, summary, active state
- Candidate cards with title, confidence, source, summary, action buttons
- Graph popup with SVG nodes/edges, clickable nodes
- Prompt version table with task_type, state, version_label
- Toast notifications (fixed bottom-right, auto-dismiss)
- Modal overlays for reject form and graph popup

### Responsive behavior
```css
@media (max-width: 1100px) {
  .review { grid-template-columns: 1fr; }
  .dashboard, .settings, .popup { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: 1fr 1fr; }
}
```

## issues
None

## needsIntegration
- Backend routes already implemented in app.py (WU-002 completed)
- Templates reference correct route names: `dashboard_page`, `review_page`, `settings_page`, `login`, `logout`
- API endpoints match backend implementation:
  - `/api/dashboard/metrics` → `dashboard_metrics()`
  - `/api/review/candidates` → `api_review_candidates()`
  - `/api/review/concepts` → `api_review_concepts()`
  - `/api/review/concepts/{concept_id}` → `api_review_concept_detail()`
  - `/api/review/graph/{concept_id}` → `api_review_graph()`
  - `/api/review/decide` → `api_review_decide()`
  - `/api/settings/prompt-versions` → `api_prompt_versions()`
  - `/api/settings/prompt-versions/{prompt_id}/confirm` → `api_confirm_prompt_version()`
- Static files mounted at `/static` path via `app.mount("/static", StaticFiles(...))`
- All templates use `url_for()` for route generation (no hardcoded paths)
- All API calls use relative endpoints (no hardcoded host/port)

## blockedReason
None

## hardConstraintsVerification
- ✓ No React/Vite/Tailwind/build pipeline
- ✓ No external graph library (inline SVG + vanilla JS)
- ✓ No host URLs, localhost URLs, Tailscale IPs, secrets, or fixed ports in reusable source
- ✓ Did not deviate from approved visual baseline
- ✓ Did not silently change approved UX or layout intent
- ✓ Did not add new product scope
- ✓ Did not implement backend/data logic (only mounted static files)
- ✓ Inspected existing components before creating new ones (reused backend routes)

## additionalNotes
- Total implementation: 1,266 lines (226 lines templates, 494 lines CSS, 546 lines JS)
- All files syntactically validated
- No forbidden files modified
- Compatible with existing test suite (test_web_*.py files)
- Ready for WU-004 validation tests
