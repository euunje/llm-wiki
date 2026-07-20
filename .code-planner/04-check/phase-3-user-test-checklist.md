# Phase 3 User Functional Test Checklist

This phase requires real user functional testing on the Tailnet browser session because every page and most user actions are new. Automated tests cover contracts and reachability but not subjective UX quality or real-data flows.

## Blocking questions (must resolve before approval)

1. **API key non-exposure** — After saving a real API key in Onboarding or Settings LLM, does the key value ever reappear in any UI element, toast, DOM attribute, or API response?
2. **Mapping Confirm visibility gate** — Does the "Confirm" button only appear after reaching Step 3 (Relationship 검증)?
3. **Onboarding checklist completeness** — After completing the full wizard, does the finish screen show all checklist items as ✓?
4. **Inbox process flow** — After uploading a real file and clicking "Process", does the item progress and show a result record?
5. **Settings Prompt rollback** — Does rolling back a prompt create a new confirmed copy without destroying history?
6. **Settings concurrency save** — Does clicking "Save concurrency" actually persist the value to settings?
7. **Onboarding file browser** — Does the Onboarding vault step's file browser actually load folders/files?
8. **Wiki graph** — Does the Wiki page graph section load related concept edges?

## Checklist

### Navigation & Global Shell

- [ ] Top nav reads exactly `Onboarding | Dashboard | Inbox | Mapping | Vault | Wiki | Settings | Logout` in that order, with icons.
- [ ] No `Review / Mapping` or `Error` top-level item.
- [ ] Layout at 1920px wide has no horizontal scroll.

### Onboarding Wizard

- [ ] All 6 steps (`provider → test → models → vault → pipeline → finish`) navigable.
- [ ] API key field never pre-fills with a visible secret value.
- [ ] After save, the API key field is cleared and the key value does NOT reappear anywhere.
- [ ] Finish screen checklist shows all ✓ or specific missing items.

### Dashboard

- [ ] 5 metric cards: Inbox, Mapping, Wiki, Vault, Issues.
- [ ] Needs-attention section has actionable links.
- [ ] System status opens Settings when clicking "Open Settings".

### Inbox

- [ ] Upload file modal opens and lists uploaded file.
- [ ] Add text modal opens and adds text item with status pill `new`.
- [ ] Process selected queues items; processing log visible on detail.
- [ ] Retry from detail panel returns to processing.
- [ ] Completed item detail shows result record with final_state, model, prompt, candidates_approved.

### Mapping (3-step wizard)

- [ ] Selecting a candidate opens Step 1 with title, LLM reason, draft body.
- [ ] Step 2 shows candidate body vs similar wiki list.
- [ ] Clicking wiki match + `Merge into existing` advances to Step 3.
- [ ] Confirm only appears on Step 3.
- [ ] Confirm action sends to `/api/mapping/decide` and updates status.
- [ ] Reject modal requires both reason and instruction; submits to retry endpoint.
- [ ] `④ 오류/에러` tab shows error candidates and supports retry-with-instruction.

### Settings LLM

- [ ] Tabs visible: LLM | Prompt | Vault | Auth.
- [ ] Save basic settings clears API key field and shows success toast.
- [ ] DevTools confirms API key value is NOT in localStorage / sessionStorage / cookies.
- [ ] Route table shows all 6 task rows; `Use this model` updates the route.
- [ ] Concurrency save persists the value (radio button value appears in `/api/settings/llm/concurrency`).

### Settings Prompt

- [ ] Active/default prompt visible.
- [ ] Version history shows prior versions with rollback button per archived row.
- [ ] Rollback creates a new confirmed copy (history preserved).
- [ ] No `Confirm anyway` control visible.

### Vault Browser

- [ ] Folder tree and file list reachable.
- [ ] No `New`, `Delete`, `Move`, `Edit` controls visible.
- [ ] Markdown renders with frontmatter hidden but accessible via disclosure.
- [ ] Non-Markdown files render as plain text.

### Wiki Reader

- [ ] Page list + detail reachable.
- [ ] Frontmatter hidden in rendered body.
- [ ] Graph section at bottom loads edges (or shows fallback for empty graph).
- [ ] Mobile (360px) shows TOC as drawer.

### Auth / Logout

- [ ] Logout returns to login page.
- [ ] Unauthenticated access redirects to login.

## How to report

After completing the checklist, reply with one of:

- `approved` — all blocking questions pass; commit can proceed.
- `approved_with_notes` — pass with minor non-blocking notes to record in evidence.
- `changes_requested` — fix items with concrete blockers; build agent will receive a fix request.
