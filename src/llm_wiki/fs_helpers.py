"""Safe filesystem helpers for Phase 3 UI (vault browser, settings, etc.)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class DirectoryPermissionError(PermissionError):
    """Raised when a directory cannot be listed due to filesystem permissions."""


def safe_list_dir(
    base_path: Path,
    relative_to: Path | None = None,
    *,
    include_hidden: bool = False,
    unauthorized_paths: set[Path] | None = None,
    raise_on_permission: bool = False,
) -> list[dict[str, Any]]:
    """List a directory safely, hiding hidden entries and unauthorized paths.

    Applies path traversal constraints when relative_to is specified.

    Args:
        base_path: Directory to list.
        relative_to: If provided, returned paths are relative to this root.
                     Also enforces that base_path is under relative_to.
        include_hidden: If True, entries starting with '.' are included.
        unauthorized_paths: Set of paths that should be excluded even if visible.
                            Paths should be absolute or normalized relative to base_path.
        raise_on_permission: If True, raise DirectoryPermissionError instead of
                             silently returning an empty listing.

    Returns:
        List of dicts with keys: name, path, is_dir, is_hidden.
    """
    if unauthorized_paths is None:
        unauthorized_paths = set()

    base_path = base_path.resolve()
    normalized_unauthorized = {path.resolve() for path in unauthorized_paths}

    if relative_to is not None:
        root = relative_to.resolve()
        try:
            base_path.relative_to(root)
        except ValueError:
            raise ValueError(f"base_path {base_path} is not under relative_to root {root}")
        effective_root = root
    else:
        effective_root = base_path

    if not base_path.is_dir():
        return []

    entries: list[dict[str, Any]] = []

    try:
        for name in os.listdir(base_path):
            if not include_hidden and name.startswith("."):
                continue

            entry_path = (base_path / name).resolve()

            try:
                relative_entry = entry_path.relative_to(effective_root)
            except ValueError:
                continue

            if not include_hidden and any(part.startswith(".") for part in relative_entry.parts if part):
                continue

            if entry_path in normalized_unauthorized:
                continue

            is_dir = entry_path.is_dir()
            entries.append({
                "name": name,
                "path": str(relative_entry) if effective_root != entry_path else name,
                "is_dir": is_dir,
                "is_hidden": name.startswith("."),
            })
    except PermissionError:
        if raise_on_permission:
            raise DirectoryPermissionError(f"Permission denied: {base_path}")
        return []

    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def is_path_under_directory(path: Path, root: Path) -> bool:
    """Check if path is under root directory (no path traversal).

    Args:
        path: Path to check.
        root: Root directory that path should be under.

    Returns:
        True if path is safely under root, False otherwise.
    """
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
