# Phase 6 — Test reset guide (test setup only)

## Purpose and non-negotiable scope

This document describes a **manual, one-time test-setup procedure** for preparing an LLM-Wiki project so that the Phase 6 end-to-end Inbox-first validation matrix can be executed against a known starting state.

> **THIS IS NOT A PRODUCT FEATURE AND NOT A PRODUCT COMMAND.**
>
> `llm-wiki` does not ship a "reset" command, will not ship one in Phase 6,
> and shipping such a command was explicitly excluded by
> `.code-planner/02-planning/phases/phase-6-test-reset-validation.md`
> ("제외 기능: 반복 가능한 reset command / 운영 자동 reset").
>
> The procedure below is a checklist for the human tester to perform on a
> **throwaway test vault** (or on a real vault after explicit backup and
> confirmation). Do not script this into a CI step. Do not run any of the
> destructive steps below against a vault that contains irreplaceable
> Wiki pages or Raw Sources.

## Hard rules (read before touching anything)

1. **Never run this on a vault you cannot lose.** Treat the test vault as
   disposable. If the vault holds anything you care about, follow the backup
   steps in §3 first.
2. **No automated/destructive flag.** The procedure never uses
   `rm -rf`, `git reset --hard`, `git clean -fdx`, or any
   "force" / destructive flag. Every destructive step is a deliberate,
   individually-confirmed shell command.
3. **User confirmation is required.** Every step below that moves or deletes
   user data has a confirmation checkpoint. Stop at the checkpoint, get an
   explicit "go", then continue.
4. **Destructive operations are one-way.** Once a path is moved into the
   quarantine / backup area it is **not** automatically recovered. The
   recoverability of any deleted Wiki page is whatever your backup gives
   you, nothing more.
5. **Out-of-band LLM calls are out of scope.** Manual E2E items in
   `phase-6-e2e-validation-checklist.md` that require a real Ollama /
   provider call are not covered by this reset guide; they require an
   explicit "real-provider LLM" approval per
   `.code-planner/03-build/phases/phase-6-execution-brief.md`
   ("Real provider LLM calls unless the user explicitly provides
   environment/approval").
6. **No commit from this guide.** This guide produces no code changes and no
   file moves outside of the user's explicit approval. Per
   `phase-6-execution-brief.md` the user has explicitly requested
   "do not commit until the current full work is complete" — this guide
   never creates a commit.

---

## 1. Decide which vault you are resetting

Before anything else, pick exactly one of the following paths. The choice is
made **once** for the entire Phase 6 session; do not mix them.

### Path A — disposable test vault (preferred)

Use this when you can afford to lose the vault.

- A scratch folder, e.g. `~/Documents/llm-wiki-phase6-test`.
- The vault is created from scratch by `wiki init` and never holds any
  real Wiki content.
- This path does **not** require backup or destructive moves.

### Path B — real vault with backup (use only when A is impossible)

Use this only when the Inbox-first flow must be validated against the
existing real vault (Raw Sources already populated, real Wiki pages already
present).

- The vault root is the same one used for daily work.
- §3 backup steps are mandatory and must complete successfully **before**
  any destructive step in §4.
- §4 destructive steps require an additional user "go" at each
  checkpoint.

---

## 2. Non-destructive pre-flight (always run)

These steps are read-only and do not modify the vault. They are the only
section that can be automated into a script later, and even then only with
explicit operator approval.

### 2.1 Confirm project structure

```sh
# From inside the vault root (the folder containing .wiki/ or config.yml).
ls -la
ls -la Inbox/ 2>/dev/null   || echo "Inbox/ missing — wiki init has not been run yet"
ls -la raw/ 2>/dev/null     || echo "raw/ missing"
ls -la wiki/ 2>/dev/null    || echo "wiki/ missing"
ls -la .wiki/ 2>/dev/null   || echo ".wiki/ missing"
```

Expected for a Phase 6-ready vault (created by `wiki init`):

```text
Inbox/{Files,Markdown,Text,_Failed,_Review}/   ← directories may be empty
raw/                                           ← may be empty for Path A
wiki/{sources,entities,concepts,synthesis}/    ← may be empty
.wiki/{config.yml,state.sqlite}
schema/AGENTS.md
```

> **Heads-up:** if `Inbox/` is missing entirely, run `wiki init .` once
> (Path A) or follow your normal `wiki init` flow for an existing vault.
> Do not re-create `Inbox/` by hand unless you also regenerate the
> Inbox `_Failed`/`_Review` subfolders; `inbox._ensure_inbox_dirs` is the
> only function that knows the canonical layout.

### 2.2 Confirm versions and config

```sh
wiki version
wiki status
```

Verify that `wiki status` reports an Inbox table with `Pending`,
`Processing`, `Review`, `Failed` counters. If those rows are missing, the
installed CLI predates the Phase 5B Inbox-first work and Phase 6 cannot be
exercised on this checkout.

### 2.3 Confirm LLM availability (informational only — no calls)

```sh
# Does NOT call the model. Just checks the host responds.
wiki status    # exits non-zero if LLM host is unreachable
```

If `wiki status` exits non-zero on the LLM check, decide:

- Run with `--no-discover`/`--batch` against a test stub later, **or**
- Have the user provide explicit approval + endpoint credentials before
  real-provider LLM calls.

This guide never invokes a real LLM automatically.

### 2.4 Snapshot git state (no commit, just snapshot)

```sh
git status --short
git log --oneline -1
git diff --stat HEAD
```

Record these outputs in
`.code-planner/03-build/evidence/phase-6-build-evidence.md`
(they confirm "no uncommitted changes from this reset" — destructive
moves in §4 must be visible in `git status`).

---

## 3. Backup (Path B only — mandatory before any destructive step)

> **STOP.** If you are on Path A, skip to §4. If you are on Path B,
> every step below must succeed **before** continuing. Do not improvise.

### 3.1 Cold snapshot of the vault

```sh
# 1. Confirm the parent directory you will snapshot into.
ls -la "$(dirname "$(pwd)")"

# 2. Snapshot using your OS tool of choice. Examples:
#    macOS Time Machine, Borg, Restic, rsync — pick one that you trust.
rsync -aPh --delete-excluded \
    "$(pwd)/" \
    "$(dirname "$(pwd)")/llm-wiki-backup-$(date +%Y%m%d-%H%M%S)/"
```

> **Confirmation checkpoint 3.1 — explicit user "go" required before §3.2.**
> The backup destination must exist on disk with non-zero size
> (`du -sh <backup-path>`).

### 3.2 Verify backup integrity

```sh
diff -r --brief \
    "$(pwd)/wiki" \
    "<backup-path>/wiki" \
    | tee /tmp/backup-diff-wiki.log

diff -r --brief \
    "$(pwd)/raw" \
    "<backup-path>/raw" \
    | tee /tmp/backup-diff-raw.log

diff -r --brief \
    "$(pwd)/Inbox" \
    "<backup-path>/Inbox" \
    | tee /tmp/backup-diff-inbox.log

diff -r --brief \
    "$(pwd)/.wiki" \
    "<backup-path>/.wiki" \
    | tee /tmp/backup-diff-internal.log
```

The four `diff` runs must produce **empty output** (zero lines). If any of
them report differences, **stop** and re-do §3.1 with the OS tool's verify
flag.

> **Confirmation checkpoint 3.2 — explicit user "go" required before §4.**
> `wc -l /tmp/backup-diff-*.log` must show `0 0 0 0`.

### 3.3 Snapshot .obsidian and any external config (Path B only)

If you use `LLM_WIKI_CONFIG` or Obsidian settings:

```sh
echo "${LLM_WIKI_CONFIG:-not set}"
ls -la .obsidian 2>/dev/null || echo "no .obsidian in vault root"
```

Hand-copy those into the backup path; `rsync` above already covered them
because it runs inside the vault root.

---

## 4. Destructive test-setup steps (Path B only; Path A uses §5 directly)

> **Every numbered step below is a one-way operation against the vault.**
> Do not run them blind. They are written so each step is small enough to
> be reviewed before execution.

### 4.1 Clear `.wiki/state.sqlite` (Inbox + sources + jobs metadata)

This drops the SQLite state DB. Wiki pages and Raw files on disk are NOT
touched. The DB will be rebuilt lazily by the next `wiki add` / `wiki
ingest`.

```sh
# Confirmation checkpoint 4.1 — explicit user "go" required.
ls -la .wiki/state.sqlite
mv .wiki/state.sqlite .wiki/state.sqlite.bak-phase6-$(date +%Y%m%d-%H%M%S)
ls -la .wiki/    # confirm .bak file exists and no state.sqlite
```

If the result is wrong, restore with
`mv .wiki/state.sqlite.bak-phase6-<ts> .wiki/state.sqlite`.

> **No `rm`.** We use `mv` to a `.bak-phase6-<timestamp>` sibling so the
> step is recoverable by hand. The `.bak` file is the user's responsibility
> to delete after they confirm the test ran cleanly.

### 4.2 Empty `Inbox/` (Files / Markdown / Text / _Failed / _Review)

Each subfolder is moved to its own quarantine area, never deleted
in-place.

```sh
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p .phase6-quarantine/"$TS"

# Confirmation checkpoint 4.2 — explicit user "go" required.
for sub in Files Markdown Text _Failed _Review; do
    if [ -d "Inbox/$sub" ] && [ -n "$(ls -A "Inbox/$sub" 2>/dev/null)" ]; then
        mv "Inbox/$sub" ".phase6-quarantine/$TS/Inbox-$sub"
    fi
done

ls -la Inbox/
ls -la .phase6-quarantine/"$TS"/
```

`Inbox/` should now show five empty folders (or be missing entirely if the
vault had no `Inbox/` before — `wiki init` will recreate the structure on
the next CLI run).

> **No `rm -rf`.** Each non-empty subfolder is moved into
> `.phase6-quarantine/<timestamp>/Inbox-<sub>/` so the user can recover by
> hand.

### 4.3 (Optional) Move existing `raw/` Raw Sources out of the way

> **Important.** Per the Phase 5A contract, "기존 Raw Sources 문서는 정상
> 처리 queue가 아니라 Inbox로 가져오는 import/migration 대상이다." The
> test-prep step here is the safe way to validate that contract. We do
> **not** delete the Raw files; we move them to a quarantine area, then
> later §5 re-imports them through the Inbox route.

```sh
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p .phase6-quarantine/"$TS"

# Confirmation checkpoint 4.3 — explicit user "go" required.
if [ -d raw ] && [ -n "$(ls -A raw 2>/dev/null)" ]; then
    mv raw .phase6-quarantine/"$TS"/raw
    mkdir -p raw
fi

ls -la raw/
ls -la .phase6-quarantine/"$TS"/
```

> **No `rm`.** `raw/` is moved whole into
> `.phase6-quarantine/<timestamp>/raw/`.

### 4.4 (Optional) Move existing `wiki/` pages out of the way

Only do this if your E2E matrix requires Wiki pages to start empty. The
default Phase 6 matrix does **not** require emptying `wiki/`.

```sh
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p .phase6-quarantine/"$TS"

# Confirmation checkpoint 4.4 — explicit user "go" required.
if [ -d wiki ] && [ -n "$(ls -A wiki 2>/dev/null)" ]; then
    mv wiki .phase6-quarantine/"$TS"/wiki
    # Do NOT recreate wiki/. Phase 6 will rebuild it via ingest.
fi

ls -la .phase6-quarantine/"$TS"/
```

> **No `rm`.** `wiki/` is moved whole into
> `.phase6-quarantine/<timestamp>/wiki/`.

### 4.5 Record the destructive summary

Append the timestamped destructive actions to
`.code-planner/03-build/evidence/phase-6-build-evidence.md` §"Destructive
test-setup performed" so the check phase can see exactly which subfolders
moved.

---

## 5. Raw Sources -> Inbox test preparation

This is the Inbox-first test seeding step. It does **not** delete or move
existing files; it copies them through the Inbox-first registration
contract.

### 5.1 Prepare test fixtures

Place at least one file of each input type in a scratch folder:

```sh
mkdir -p /tmp/llm-wiki-phase6-fixtures

# Document file (PDF/DOCX/HTML/TXT — pick any supported parser).
cp /path/to/real-doc.pdf /tmp/llm-wiki-phase6-fixtures/sample-doc.pdf

# Markdown scrape.
cat > /tmp/llm-wiki-phase6-fixtures/sample-markdown.md <<'MD'
---
title: Sample markdown note
---

# Sample Markdown

Some short text from a "scraped" Markdown note.
MD

# Pasted text input (no file, will be POSTed via Web UI paste form).
echo 'Paste-text fixture — fill in body via the Web UI paste form.'

# Large document for chunked-extraction path.
cp /path/to/large-doc.pdf /tmp/llm-wiki-phase6-fixtures/sample-large.pdf

# Failure-route fixture (a deliberately malformed PDF).
printf 'not a real pdf' > /tmp/llm-wiki-phase6-fixtures/sample-bad.pdf
```

> The Phase 6 validation matrix relies on these per-fixture inputs:
> document file, markdown scrape, pasted text, large document
> (chunked extraction), failure route, review route, archive move,
> existing Raw Sources import before processing, Wiki page create /
> update, Raw archive movement.

### 5.2 Register fixtures through the Inbox-first API

Use the canonical CLI / Web-UI paths. **Do not** bypass them by writing
files directly into `Inbox/Files/` etc. — that would skip the dedup,
events, and `InboxState` transitions.

```sh
# (a) Document file + markdown scrape via CLI `wiki add`.
wiki add /tmp/llm-wiki-phase6-fixtures/sample-doc.pdf
wiki add /tmp/llm-wiki-phase6-fixtures/sample-markdown.md

# (b) Pasted text via the Web UI `/ingest` paste form, or, if you must
#     use the CLI directly, use the `register_pasted_text` helper only
#     inside a test harness — do NOT write a custom shell wrapper for
#     the manual reset.

# (c) Large document (will exercise chunked extraction path).
wiki add /tmp/llm-wiki-phase6-fixtures/sample-large.pdf

# (d) Failure-route fixture (malformed PDF).
wiki add /tmp/llm-wiki-phase6-fixtures/sample-bad.pdf

# (e) Existing Raw Sources -> Inbox import (Phase 5A contract).
#     If §4.3 quarantined `raw/`, copy a single file back so the
#     /ingest/scan -> /ingest/start round-trip can be observed.
mkdir -p raw
cp /tmp/llm-wiki-phase6-fixtures/sample-doc.pdf raw/existing-raw.pdf

# Then start the Web UI and click "Raw Sources에서 Inbox로 가져오기",
# OR call /ingest/scan via curl with cookie/CSRF handling. The CLI does
# not expose a `wiki raw import` command — that is intentional per the
# Inbox-first contract.
```

### 5.3 Verify Inbox pending counts before processing

```sh
wiki status
# Expect:
#   Inbox
#     Pending     >= 5   (sample-doc, sample-markdown, sample-large,
#                         sample-bad, existing-raw)
#     Processing   0
#     Review       0
#     Failed       0
```

If `Pending` is not as expected, stop and inspect
`.code-planner/03-build/evidence/phase-6-build-evidence.md` §"Test prep
anomalies" before proceeding to the E2E checklist.

### 5.4 Hand-off to E2E checklist

When §5.3 reports the expected pending counts, open
`.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
and walk the matrix.

---

## 6. Cleanup of test-setup artifacts (after the E2E pass)

After all E2E items have been signed off in
`phase-6-e2e-validation-checklist.md`:

```sh
TS="$(date +%Y%m%d-%H%M%S)"

# 6.1 Confirm quarantine still exists before deleting.
ls -la .phase6-quarantine/

# Confirmation checkpoint 6.1 — explicit user "go" required.
# 6.2 Move the entire quarantine tree into a final archive named with
#     the session timestamp; do NOT rm -rf.
mv .phase6-quarantine .phase6-quarantine-final-"$TS"

# 6.3 Move the .bak SQLite file into the same final archive.
ls -la .wiki/state.sqlite.bak-* 2>/dev/null
# Confirmation checkpoint 6.3 — explicit user "go" required.
mv .wiki/state.sqlite.bak-phase6-* .phase6-quarantine-final-"$TS"/ 2>/dev/null || true

ls -la .phase6-quarantine-final-"$TS"/
```

The `.phase6-quarantine-final-<ts>/` directory is now a single folder the
user can keep, archive, or delete manually. **This guide never deletes
that folder on its own.**

> **No `rm -rf`.** The whole quarantine is preserved under a single
> final timestamped folder. Recovery is by manual folder move.

---

## 7. What this guide does NOT do

- It does not run any product command named "reset", "wipe", "clean", or
  similar.
- It does not introduce a `wiki reset` CLI subcommand. The grep below
  must remain empty after this guide lands:

  ```sh
  grep -RIn "def reset\|@app.command.*reset" src/llm_wiki || echo "no reset command"
  ```

- It does not delete Wiki pages, Raw files, Inbox subfolders, or the
  SQLite state DB. Every destructive step uses `mv` into a timestamped
  quarantine area, never `rm`.
- It does not invoke real-provider LLM calls.
- It does not commit anything. The user is responsible for committing
  after the Phase 6 work is fully complete (per
  `.code-planner/03-build/phases/phase-6-execution-brief.md`).

## 8. Evidence paths defined by this guide

- **Test setup log:** `.code-planner/03-build/evidence/phase-6-build-evidence.md`
  §"Destructive test-setup performed" — timestamped log of every `mv`
  performed under §4 and §6.
- **E2E results:** `.code-planner/03-build/evidence/phase-6-e2e-validation-checklist.md`
  §"Per-row results" — one row per Phase 6 matrix item.
- **Quarantine area:** `.phase6-quarantine/<ts>/` (during the session)
  → `.phase6-quarantine-final-<ts>/` (after sign-off).
- **SQLite backup:** `.wiki/state.sqlite.bak-phase6-<ts>` during the
  session, moved into the final quarantine on sign-off.

## 9. Confirmation checkpoint summary

| Step | Risk | Required action |
| --- | --- | --- |
| §3.1 cold snapshot | Lost writes if backup incomplete | User "go" before §3.2 |
| §3.2 verify backup integrity | Diff non-empty means stale backup | User "go" before §4 |
| §4.1 SQLite DB quarantine | Inbox/sources/jobs lost from view | User "go" before §4.2 |
| §4.2 Inbox subfolder quarantine | Files staged for Inbox processing lost | User "go" before §4.3 |
| §4.3 Raw quarantine | Raw files move out of `raw/` | User "go" before §4.4 |
| §4.4 Wiki quarantine | Wiki pages move out of `wiki/` | User "go" before §5 |
| §5.2 Inbox-first registration | None — additive only | No "go" needed |
| §6.1 final quarantine naming | Final archive lost | User "go" before §6.2 |
| §6.3 SQLite backup final move | `.bak` lost from `.wiki/` | User "go" before file exit |
