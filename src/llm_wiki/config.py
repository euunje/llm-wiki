"""Path constants and config loading for an LLM-Wiki project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Folder layout (relative to a wiki project root)
# ---------------------------------------------------------------------------

RAW_DIR = "raw"
WIKI_DIR = "wiki"
SCHEMA_DIR = "schema"
INTERNAL_DIR = ".wiki"

WIKI_SUBDIRS = ("sources", "entities", "concepts", "synthesis")

INDEX_FILE = "index.md"
LOG_FILE = "log.md"
AGENTS_FILE = "AGENTS.md"
CONFIG_FILE = "config.yml"
STATE_DB = "state.sqlite"

OBSIDIAN_DIR = ".obsidian"


def _resolve_under(root: Path, value: str | None, default: str) -> Path:
    """Resolve a user-configured path.

    Config paths are stored relative to project root by default, but absolute
    paths are accepted for existing-vault integrations.
    """
    raw = value or default
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def default_page_dirs(wiki_dir: str = WIKI_DIR) -> dict[str, str]:
    """Default page directory map shown during onboarding and written to config."""
    return {
        "sources": f"{wiki_dir}/sources",
        "entities": f"{wiki_dir}/entities",
        "concepts": f"{wiki_dir}/concepts",
        "synthesis": f"{wiki_dir}/synthesis",
        "non_categories": f"{wiki_dir}/non_categories",
        "assets": f"{wiki_dir}/assets",
    }


def default_files(wiki_dir: str = WIKI_DIR, schema_dir: str = SCHEMA_DIR, internal_dir: str = INTERNAL_DIR) -> dict[str, str]:
    """Default file map shown during onboarding and written to config."""
    return {
        "index": f"{wiki_dir}/{INDEX_FILE}",
        "log": f"{wiki_dir}/{LOG_FILE}",
        "agents": f"{schema_dir}/{AGENTS_FILE}",
        "config": f"{internal_dir}/{CONFIG_FILE}",
        "state_db": f"{internal_dir}/{STATE_DB}",
    }


@dataclass
class WikiPaths:
    """Resolved absolute paths for a wiki project."""

    root: Path

    def _load_raw_config(self) -> dict:
        # Bootstrap from the default config location.  The config itself may
        # then redirect state DB and generated-file paths elsewhere.
        config_file = self.root / INTERNAL_DIR / CONFIG_FILE
        if not config_file.exists():
            return {}
        try:
            with config_file.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _paths_config(self) -> dict:
        return self._load_raw_config().get("paths", {})

    def _page_dirs_config(self) -> dict:
        paths = self._paths_config()
        configured = paths.get("page_dirs") or {}
        legacy_wiki = paths.get("wiki_dir", WIKI_DIR)
        merged = default_page_dirs(legacy_wiki)
        merged.update(configured)
        return merged

    def _files_config(self) -> dict:
        paths = self._paths_config()
        configured = paths.get("files") or {}
        legacy_wiki = paths.get("wiki_dir", WIKI_DIR)
        legacy_schema = paths.get("schema_dir", SCHEMA_DIR)
        legacy_internal = paths.get("internal_dir", INTERNAL_DIR)
        merged = default_files(legacy_wiki, legacy_schema, legacy_internal)
        merged.update(configured)
        return merged

    @property
    def raw(self) -> Path:
        rel = self._paths_config().get("raw_dir", RAW_DIR)
        return _resolve_under(self.root, rel, RAW_DIR)

    @property
    def wiki(self) -> Path:
        rel = self._paths_config().get("wiki_dir", WIKI_DIR)
        return _resolve_under(self.root, rel, WIKI_DIR)

    @property
    def schema(self) -> Path:
        rel = self._paths_config().get("schema_dir", SCHEMA_DIR)
        return _resolve_under(self.root, rel, SCHEMA_DIR)

    @property
    def internal(self) -> Path:
        rel = self._paths_config().get("internal_dir", INTERNAL_DIR)
        return _resolve_under(self.root, rel, INTERNAL_DIR)

    def page_dir(self, name: str) -> Path:
        configured = self._page_dirs_config().get(name)
        fallback = default_page_dirs().get(name, f"{WIKI_DIR}/{name}")
        return _resolve_under(self.root, configured, fallback)

    @property
    def sources(self) -> Path:
        return self.page_dir("sources")

    @property
    def entities(self) -> Path:
        return self.page_dir("entities")

    @property
    def concepts(self) -> Path:
        return self.page_dir("concepts")

    @property
    def synthesis(self) -> Path:
        return self.page_dir("synthesis")

    @property
    def non_categories(self) -> Path:
        return self.page_dir("non_categories")

    @property
    def assets(self) -> Path:
        return self.page_dir("assets")

    def mapped_file(self, name: str) -> Path:
        configured = self._files_config().get(name)
        fallback = default_files().get(name, name)
        return _resolve_under(self.root, configured, fallback)

    @property
    def index(self) -> Path:
        return self.mapped_file("index")

    @property
    def log(self) -> Path:
        return self.mapped_file("log")

    @property
    def agents(self) -> Path:
        return self.mapped_file("agents")

    @property
    def config_file(self) -> Path:
        return self.mapped_file("config")

    @property
    def state_db(self) -> Path:
        return self.mapped_file("state_db")

    @property
    def obsidian(self) -> Path:
        obsidian_cfg = self._paths_config().get("obsidian", {})
        rel = obsidian_cfg.get("dir") if isinstance(obsidian_cfg, dict) else None
        return _resolve_under(self.root, rel, f"{WIKI_DIR}/{OBSIDIAN_DIR}")

    @property
    def obsidian_create(self) -> bool:
        obsidian_cfg = self._paths_config().get("obsidian", {})
        if isinstance(obsidian_cfg, dict) and "create" in obsidian_cfg:
            return bool(obsidian_cfg["create"])
        return True

    def is_initialized(self) -> bool:
        """A folder counts as initialized if its config file exists."""
        return (self.root / INTERNAL_DIR / CONFIG_FILE).exists() or self.config_file.exists()


# ---------------------------------------------------------------------------
# Default config (written on `wiki init`)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "version": 1,
    "llm": {
        "provider": "ollama",
        "model": "qwen3:14b",
        "host": "http://localhost:11434",
        "temperature": 0.3,
        # Qwen3 thinking mode — useful for synthesis/lint, slower for routine ops
        "thinking": True,
    },
    "search": {
        "backend": "qmd",
        "rerank": True,
    },
    "ingest": {
        "interactive": True,
        "auto_update_index": True,
        "auto_update_log": True,
    },
}


def load_config(paths: WikiPaths) -> dict:
    """Load the wiki's config.yml, falling back to defaults for missing keys."""
    if not paths.config_file.exists():
        return dict(DEFAULT_CONFIG)
    with paths.config_file.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(loaded)
    return merged


def save_config(paths: WikiPaths, config: dict) -> None:
    """Write config to disk, creating the internal directory if needed."""
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    with paths.config_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)


def find_wiki_root(start: Path | None = None) -> Path | None:
    """Walk upward from `start` looking for a `.wiki/config.yml`. Returns the
    project root if found, else None.
    """
    import os
    env_root = os.environ.get("WIKI_ROOT")
    if env_root:
        return Path(env_root).resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / INTERNAL_DIR / CONFIG_FILE).exists():
            return candidate
    return None
