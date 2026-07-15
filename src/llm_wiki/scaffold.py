"""Scaffolding logic for `wiki init` — creates the folder structure, copies
templates, configures Obsidian, and initializes the state DB.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from . import config as cfg
from . import db


class ScaffoldError(Exception):
    """Raised when scaffolding cannot proceed (e.g. existing wiki, no perms)."""


def _read_template(name: str) -> str:
    """Read a template file shipped inside the package."""
    files = resources.files("llm_wiki.templates")
    return (files / name).read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _base_paths_config(
    *,
    wiki_dir: str,
    raw_dir: str,
    schema_dir: str,
    internal_dir: str,
    sources_dir: str | None,
    entities_dir: str | None,
    concepts_dir: str | None,
    synthesis_dir: str | None,
    non_categories_dir: str | None,
    assets_dir: str | None,
    index_file: str | None,
    log_file: str | None,
    agents_file: str | None,
    config_file: str | None,
    state_db: str | None,
    obsidian_dir: str | None,
    obsidian_create: bool,
) -> dict:
    page_dirs = cfg.default_page_dirs(wiki_dir)
    for key, value in {
        "sources": sources_dir,
        "entities": entities_dir,
        "concepts": concepts_dir,
        "synthesis": synthesis_dir,
        "non_categories": non_categories_dir,
        "assets": assets_dir,
    }.items():
        if value:
            page_dirs[key] = value

    files = cfg.default_files(wiki_dir, schema_dir, internal_dir)
    for key, value in {
        "index": index_file,
        "log": log_file,
        "agents": agents_file,
        "config": config_file,
        "state_db": state_db,
    }.items():
        if value:
            files[key] = value

    return {
        "wiki_dir": wiki_dir,
        "raw_dir": raw_dir,
        "schema_dir": schema_dir,
        "internal_dir": internal_dir,
        "page_dirs": page_dirs,
        "files": files,
        "obsidian": {
            "create": obsidian_create,
            "dir": obsidian_dir or f"{wiki_dir}/{cfg.OBSIDIAN_DIR}",
        },
    }


def scaffold(
    root: Path,
    force: bool = False,
    wiki_dir: str = "wiki",
    raw_dir: str = "raw",
    schema_dir: str = "schema",
    internal_dir: str = ".wiki",
    sources_dir: str | None = None,
    entities_dir: str | None = None,
    concepts_dir: str | None = None,
    synthesis_dir: str | None = None,
    non_categories_dir: str | None = None,
    assets_dir: str | None = None,
    index_file: str | None = None,
    log_file: str | None = None,
    agents_file: str | None = None,
    config_file: str | None = None,
    state_db: str | None = None,
    obsidian_dir: str | None = None,
    obsidian_create: bool = True,
) -> cfg.WikiPaths:
    """Create a fresh LLM-Wiki project at `root`.

    All user-visible folders/files can be mapped during onboarding.  Legacy
    callers that only pass raw/wiki/schema dirs keep the original layout.
    """
    root = root.resolve()
    paths = cfg.WikiPaths(root=root)

    if paths.is_initialized() and not force:
        raise ScaffoldError(
            f"This folder is already an LLM-Wiki project (found "
            f"{paths.config_file.relative_to(root)}).\n"
            f"Use --force to re-scaffold."
        )

    # 1. Save config first so paths resolve correctly.  Bootstrap config is
    # still written through WikiPaths so future path properties use the map.
    root.mkdir(parents=True, exist_ok=True)
    config = dict(cfg.DEFAULT_CONFIG)
    config["paths"] = _base_paths_config(
        wiki_dir=wiki_dir,
        raw_dir=raw_dir,
        schema_dir=schema_dir,
        internal_dir=internal_dir,
        sources_dir=sources_dir,
        entities_dir=entities_dir,
        concepts_dir=concepts_dir,
        synthesis_dir=synthesis_dir,
        non_categories_dir=non_categories_dir,
        assets_dir=assets_dir,
        index_file=index_file,
        log_file=log_file,
        agents_file=agents_file,
        config_file=config_file,
        state_db=state_db,
        obsidian_dir=obsidian_dir,
        obsidian_create=obsidian_create,
    )
    # Write to the default bootstrap location first so WikiPaths can read it.
    bootstrap = root / cfg.INTERNAL_DIR / cfg.CONFIG_FILE
    bootstrap.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    with bootstrap.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)
    cfg.save_config(paths, config)

    # Refuse to clobber an existing wiki unless explicitly forced
    if paths.wiki.exists() and any(paths.wiki.iterdir()) and not force:
        raise ScaffoldError(
            f"Wiki folder already exists and is not empty: {paths.wiki}\n"
            f"Use --force to scaffold anyway (may overwrite files)."
        )

    # 2. Top-level folders
    paths.raw.mkdir(parents=True, exist_ok=True)
    paths.wiki.mkdir(parents=True, exist_ok=True)
    paths.schema.mkdir(parents=True, exist_ok=True)
    paths.internal.mkdir(parents=True, exist_ok=True)

    # 3. Configured page/output directories
    (paths.raw / ".gitkeep").touch()
    for d in [paths.sources, paths.entities, paths.concepts, paths.synthesis, paths.non_categories, paths.assets]:
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()

    for d in [paths.inbox, paths.inbox_files, paths.inbox_markdown, paths.inbox_text, paths.inbox_failed, paths.inbox_review]:
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()

    # 4. Wiki seed files (index.md, log.md)
    _write(paths.index, _read_template("index.md"))
    _write(paths.log, _read_template("log.md"))

    # 5. Schema (AGENTS.md)
    _write(paths.agents, _read_template("AGENTS.md"))

    # 6. Obsidian config (optional for existing vault integrations)
    if paths.obsidian_create:
        paths.obsidian.mkdir(parents=True, exist_ok=True)
        _write(paths.obsidian / "app.json", _read_template("obsidian_app.json"))
        _write(paths.obsidian / "graph.json", _read_template("obsidian_graph.json"))

    # 7. Initialize state DB
    db.init_db(paths.state_db)

    return paths
