from __future__ import annotations

import json
import signal
import struct
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from llm_wiki.common import new_id, sha256_text, utc_now
from llm_wiki.config import load_settings
from llm_wiki.db.schema import connect
from llm_wiki.jobs import create_job, record_artifact, update_job
from llm_wiki.pipeline.errors import UserInputError
from llm_wiki.workspace import WorkspacePaths


def _fallback_vector(text: str, dimension: int = 16) -> list[float]:
    floats: list[float] = []
    seed = sha256_text(text)
    material = seed
    while len(floats) < dimension:
        material = sha256_text(material + text)
        for idx in range(0, len(material), 8):
            piece = material[idx:idx + 8]
            if len(piece) < 8:
                continue
            number = int(piece, 16)
            floats.append(round((number / 0xFFFFFFFF) * 2 - 1, 6))
            if len(floats) >= dimension:
                break
    return floats


@contextmanager
def _time_limit(seconds: int):
    """Portable bounded-operation context manager.

    POSIX systems use SIGALRM for reliable async-safe interruption.
    Non-POSIX (e.g. Windows) fall back to a daemon Timer thread that
    raises TimeoutError from outside the monitored block — this means
    the block is given a chance to finish or check a flag, but if it
    truly hangs the TimeoutError will fire after the deadline.
    """
    if seconds <= 0:
        yield
        return

    if hasattr(signal, "SIGALRM"):

        def _handle_timeout(signum, frame):  # type: ignore[no-untyped-def]
            raise TimeoutError(f"fastembed operation exceeded {seconds}s")

        previous = signal.signal(signal.SIGALRM, _handle_timeout)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    else:
        # Non-POSIX: threading.Timer + daemon interrupt.
        # The operation may not be genuinely interruptible, but the
        # TimeoutError will fire on the Timer thread after the deadline.
        error: Exception | None = None

        def _raise_on_timer():
            nonlocal error
            error = TimeoutError(f"fastembed operation exceeded {seconds}s")
            raise error

        timer = threading.Timer(seconds, _raise_on_timer)
        timer.daemon = True
        timer.start()
        try:
            yield
        finally:
            timer.cancel()
            timer.join(timeout=1.0)


def _resolve_local_embedding_model(workspace: WorkspacePaths, embedding_settings: dict[str, Any], model_name: str) -> str:
    model_root = str(embedding_settings.get("model_root") or "data/models/embeddings").strip()
    if not model_root or not model_name:
        return model_name
    root = Path(model_root).expanduser()
    if not root.is_absolute():
        root = workspace.root / root
    candidate = Path(model_name).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return str(candidate.resolve())
    local = root / model_name
    if local.exists() and local.is_dir():
        return str(local.resolve())
    return model_name


def _embedding_model_root(workspace: WorkspacePaths, embedding_settings: dict[str, Any]) -> Path:
    model_root = str(embedding_settings.get("model_root") or "data/models/embeddings").strip()
    root = Path(model_root).expanduser()
    if not root.is_absolute():
        root = workspace.root / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _load_embedder(model_name: str, timeout_seconds: int, *, cache_dir: Path | None = None):
    try:
        from fastembed import TextEmbedding  # type: ignore

        with _time_limit(timeout_seconds):
            return TextEmbedding(model_name=model_name, cache_dir=str(cache_dir) if cache_dir else None), None
    except Exception as exc:  # pragma: no cover - optional dependency path
        return None, str(exc)


def _vector_blob(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _validate_embedder_output(
    vectors: object, expected_count: int
) -> tuple[list[list[float]] | None, str | None]:
    """Validate the structure of a fastembed output before persistence.

    Phase 1 must never persist an inconsistent embedding state. The
    embedder can occasionally return malformed output (empty list, short
    list due to early abort, mismatched dimensions across vectors, or an
    all-zero vector). ``zip`` would silently truncate such output and
    produce a partial set of embedding rows alongside an inconsistent
    dimension. This helper rejects those shapes before they reach SQLite.

    Returns ``(validated_vectors, None)`` on success or
    ``(None, reason)`` on any failure. The caller is expected to fall
    back to ``fallback-hash-v1`` on failure so the embed command is
    always terminal with a recorded ``backend_detail.reason``.
    """
    if not isinstance(vectors, list):
        return None, f"embedder output was {type(vectors).__name__}, expected list"
    if len(vectors) != expected_count:
        return (
            None,
            f"embedder returned {len(vectors)} vectors for {expected_count} targets",
        )
    if not vectors:
        return None, "embedder returned no vectors"
    expected_dimension = len(vectors[0])
    if expected_dimension <= 0:
        return None, "embedder returned vectors with zero dimension"
    cleaned: list[list[float]] = []
    for index, vector in enumerate(vectors):
        if not hasattr(vector, "__iter__") or isinstance(vector, (str, bytes)):
            return None, f"embedder vector {index} is not iterable"
        values: list[float] = []
        for value in vector:
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                return None, f"embedder vector {index} contains non-numeric values"
        if len(values) != expected_dimension:
            return (
                None,
                f"embedder vector {index} has dimension {len(values)}, "
                f"expected {expected_dimension}",
            )
        if not any(values):
            return None, f"embedder vector {index} is all-zero"
        cleaned.append(values)
    return cleaned, None


def _select_targets(conn, target: str) -> tuple[str, list[dict[str, Any]]]:
    if target.startswith("source:"):
        source_id = target.split(":", 1)[1]
        rows = conn.execute(
            "SELECT id, text, source_id FROM source_chunks WHERE source_id = ? ORDER BY chunk_index",
            (source_id,),
        ).fetchall()
        if not rows:
            raise UserInputError(f"No chunks found for source {source_id}")
        return source_id, [dict(row) for row in rows]
    if target.startswith("chunk:"):
        chunk_id = target.split(":", 1)[1]
        row = conn.execute(
            "SELECT id, text, source_id FROM source_chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if not row:
            raise UserInputError(f"Unknown chunk_id: {chunk_id}")
        return dict(row)["source_id"], [dict(row)]
    if target == "all":
        rows = conn.execute("SELECT id, text, source_id FROM source_chunks ORDER BY source_id, chunk_index").fetchall()
        if not rows:
            raise UserInputError("No chunks available to embed")
        return "all", [dict(row) for row in rows]
    raise UserInputError("Phase 1 embed supports source:<id>, chunk:<id>, or all")


def embed_target(workspace: WorkspacePaths, target: str) -> dict[str, object]:
    settings = load_settings(workspace.settings_file)
    embedding_settings = settings.get("embedding", {})
    model_name = embedding_settings.get("default_model") or ""
    model_load_name = _resolve_local_embedding_model(workspace, embedding_settings, str(model_name))
    model_cache_root = _embedding_model_root(workspace, embedding_settings)
    fallback_model = embedding_settings.get("fallback_model", "fallback-hash-v1")
    fastembed_timeout_seconds = max(1, int(embedding_settings.get("fastembed_timeout_seconds") or 30))
    job_id = create_job(workspace.db, "embed", target_type="embedding_target", target_id=target)
    update_job(workspace.db, job_id, status="running")
    conn = connect(workspace.db)
    try:
        source_scope, targets = _select_targets(conn, target)
        if model_load_name:
            try:
                embedder, embedder_error = _load_embedder(model_load_name, fastembed_timeout_seconds, cache_dir=model_cache_root)
            except TypeError as exc:
                if "cache_dir" not in str(exc):
                    raise
                embedder, embedder_error = _load_embedder(model_load_name, fastembed_timeout_seconds)
        else:
            embedder, embedder_error = (None, "no model configured")
        backend = "fastembed"
        model_used = model_name
        vectors: list[list[float]] = []
        if embedder is not None:
            raw_vectors: list[list[float]] = []
            try:
                with _time_limit(fastembed_timeout_seconds):
                    raw_vectors = [
                        list(map(float, vector))
                        for vector in embedder.embed([item["text"] for item in targets])
                    ]
            except Exception as exc:  # pragma: no cover - optional dependency path
                embedder = None
                embedder_error = str(exc)
            else:
                validated, validation_reason = _validate_embedder_output(
                    raw_vectors, expected_count=len(targets)
                )
                if validated is None:
                    embedder = None
                    embedder_error = (
                        f"embedder output invalid: {validation_reason}"
                    )
                else:
                    raw_vectors = validated
            if embedder is not None:
                vectors = raw_vectors
        if embedder is None:
            backend = "fallback_hash"
            model_used = fallback_model
            vectors = [_fallback_vector(item["text"]) for item in targets]
        dimension = len(vectors[0]) if vectors else 0
        now = utc_now()
        target_source_ids = set()
        embedding_ids: list[str] = []
        for item, vector in zip(targets, vectors):
            embedding_id = new_id("embedding")
            embedding_ids.append(embedding_id)
            target_source_ids.add(item["source_id"])
            conn.execute(
                "DELETE FROM embeddings WHERE target_type = 'chunk' AND target_id = ? AND model = ?",
                (item["id"], model_used),
            )
            conn.execute(
                """
                INSERT INTO embeddings (
                    id, target_type, target_id, model, backend, dimension, vector_blob, vector_json,
                    index_status, generated_at, created_at, updated_at
                ) VALUES (?, 'chunk', ?, ?, ?, ?, ?, ?, 'stored', ?, ?, ?)
                """,
                (
                    embedding_id,
                    item["id"],
                    model_used,
                    backend,
                    dimension,
                    _vector_blob(vector),
                    json.dumps(vector),
                    now,
                    now,
                    now,
                ),
            )
            conn.execute(
                "UPDATE source_chunks SET embedding_status = 'embedded', updated_at = ? WHERE id = ?",
                (now, item["id"]),
            )
        for source_id in target_source_ids:
            conn.execute("UPDATE sources SET pipeline_stage = 'embedded', updated_at = ? WHERE id = ?", (now, source_id))
        conn.commit()
        payload = {
            "status": "ok",
            "target": target,
            "source_scope": source_scope,
            "embedding_count": len(vectors),
            "dimension": dimension,
            "model": model_used,
            "backend": backend,
            "embedding_ids": embedding_ids,
        }
        if backend == "fallback_hash":
            payload["backend_detail"] = {
                "reason": embedder_error or "fastembed unavailable",
                "note": "Phase 1 deterministic fallback used explicitly; not an LLM-generated embedding.",
            }
        artifact = record_artifact(
            workspace,
            artifact_type="embedding_report",
            task_type="embed",
            payload=payload,
            target_type="embedding_target",
            target_id=target.replace(":", "_"),
        )
        update_job(workspace.db, job_id, status="succeeded", output_refs=[artifact])
        payload.update({"job_id": job_id, **artifact, "message": f"Embedded {len(vectors)} chunk targets"})
        return payload
    except Exception as exc:
        update_job(
            workspace.db,
            job_id,
            status="failed",
            error={"reason": str(exc), "type": exc.__class__.__name__},
        )
        raise
    finally:
        conn.close()
