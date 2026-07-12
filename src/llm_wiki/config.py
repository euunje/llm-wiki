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
        # Bootstrap from the default config location, or from LLM_WIKI_CONFIG
        # external runtime config when set.  The config itself may then redirect
        # state DB and generated-file paths elsewhere.
        config_file = self._resolve_config_file()
        if config_file is None or not config_file.exists():
            return {}
        try:
            with config_file.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _resolve_config_file(self) -> Path | None:
        """Return the config file path to use.

        ``LLM_WIKI_CONFIG`` is allowed to point at an external runtime config
        file that may not exist yet (for example during setup/save).  Reading
        callers must still check ``exists()`` before loading it.
        """
        path = external_config_path(require_exists=False)
        if path is not None:
            return path
        return self.root / INTERNAL_DIR / CONFIG_FILE

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
        """Return the config file path: ``LLM_WIKI_CONFIG`` if set, else mapped config."""
        path = external_config_path(require_exists=False)
        if path is not None:
            return path
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
        """A folder counts as initialized if its active config file exists.

        When ``LLM_WIKI_CONFIG`` is set, that external config file is the active
        config; this keeps runtime state outside the vault.
        """
        path = external_config_path(require_exists=False)
        if path is not None:
            return path.is_file()
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

    When LLM_WIKI_CONFIG is set to an external config file path, the wiki root
    is inferred from that file's parent directory (one level up from the
    directory containing the config file).
    """
    import os
    env_root = os.environ.get("WIKI_ROOT")
    if env_root:
        return Path(env_root).resolve()

    # Support LLM_WIKI_CONFIG=/path/to/external/config.yml pointing to an
    # external runtime config file. Prefer an explicit root in that config when
    # present; otherwise fall back to the previous runtime-parent heuristic.
    env_config_path = external_config_path(require_exists=True)
    if env_config_path is not None:
        try:
            with env_config_path.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            paths_cfg = loaded.get("paths", {}) if isinstance(loaded, dict) else {}
            explicit_root = paths_cfg.get("root") or paths_cfg.get("root_dir")
            if explicit_root:
                return Path(str(explicit_root)).expanduser().resolve()
        except Exception:
            pass
        # Backward-compatible fallback for existing external runtime layouts.
        return env_config_path.parent.parent

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / INTERNAL_DIR / CONFIG_FILE).exists():
            return candidate
    return None


def external_config_path(require_exists: bool = True) -> Path | None:
    """Return the resolved path for ``LLM_WIKI_CONFIG``, or None.

    ``require_exists=False`` is useful for setup/save paths where the external
    config file is about to be created.
    """
    import os
    env_config = os.environ.get("LLM_WIKI_CONFIG")
    if not env_config:
        return None
    path = Path(env_config).expanduser().resolve()
    if require_exists and not path.is_file():
        return None
    return path
