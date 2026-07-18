# Phase 2 Decision Request

| Field | Value |
| --- | --- |
| Phase | 2 — LLM Wiki Quality |
| Source check report | `.code-planner/04-check/phase-2-check-report.md` |
| Issue kind | Pre-existing worktree state decisions |
| Blocking | Yes for Phase 2 commit policy |

## Problem target

- `.code-planner/04-check/recheck/phase-1-recheck-report.md` is modified in the working tree relative to the canonical Phase 1 commit `9d155a15a043eea37078e6a617d9900a516ccedb`.
- `.code-planner/01-ideation-approved.json`, `.code-planner/01-ideation-living-note.md`, `.code-planner/02-planning/` are untracked planning artifacts in the working tree.
- `testset/` is an untracked user-provided validation input.

## Reason

These items are not strictly fixable by the Build agent because they reflect either:

1. The user's planning workflow (`testset/`, planning artifacts) which lives outside runtime source.
2. Worktree state that pre-dates the Phase 2 build and is the user's process choice.

Reverting the Phase 1 recheck report is the safe option to keep the Phase 1 commit canonical. The planning artifacts must never be committed to runtime source.

## Improvement spec

The Build agent must NOT commit any of the following paths:

- `.code-planner/01-ideation-approved.json`
- `.code-planner/01-ideation-living-note.md`
- `.code-planner/02-planning/`
- `testset/`
- Any `.env` or other secret/env file

The Build agent must reconcile the worktree-local Phase 1 recheck report. The recommended resolution is one of:

1. `git restore --source 9d155a1 --worktree -- .code-planner/04-check/recheck/phase-1-recheck-report.md` before commit.
2. Document explicitly why the worktree-local edits are required and bundle them into the Phase 2 commit only with user approval.

## Suggested decision owner

User / planning owner (not Build).

## Validation required

- After the decision, run `git diff --stat` and confirm only Phase 2 in-scope files are present.
- `git status --short` must not show planning/testset paths added.

## Acceptance criteria

- Worktree either reverts the Phase 1 recheck report or includes a documented rationale.
- No planning/testset path is staged.
