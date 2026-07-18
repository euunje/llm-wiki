from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    vault: Path
    inbox_memo: Path
    inbox_files: Path
    inbox_text: Path
    wiki_concepts: Path
    wiki_sources: Path
    wiki_claims: Path
    wiki_pages: Path
    review_candidates: Path
    review_mapping: Path
    review_rejected: Path
    raws: Path
    settings_dir: Path
    templates: Path
    prompts: Path
    ontology: Path
    data: Path
    db: Path
    raw: Path
    normalized: Path
    artifacts: Path
    exports: Path
    cache: Path
    settings_file: Path
    env_file: Path


def resolve_workspace(path: str | Path | None) -> WorkspacePaths:
    root = Path(path or ".").expanduser().resolve()
    vault = root / "vault"
    settings_dir = vault / "90_Settings"
    data = root / "data"
    return WorkspacePaths(
        root=root,
        vault=vault,
        inbox_memo=vault / "00_Inbox" / "memo",
        inbox_files=vault / "00_Inbox" / "files",
        inbox_text=vault / "00_Inbox" / "text",
        wiki_concepts=vault / "10_Wiki" / "concepts",
        wiki_sources=vault / "10_Wiki" / "sources",
        wiki_claims=vault / "10_Wiki" / "claims",
        wiki_pages=vault / "10_Wiki" / "pages",
        review_candidates=vault / "20_Review" / "candidates",
        review_mapping=vault / "20_Review" / "mapping",
        review_rejected=vault / "20_Review" / "rejected",
        raws=vault / "80_Raws",
        settings_dir=settings_dir,
        templates=settings_dir / "templates",
        prompts=settings_dir / "prompts",
        ontology=settings_dir / "ontology",
        data=data,
        db=data / "wiki.sqlite",
        raw=data / "raw",
        normalized=data / "normalized",
        artifacts=data / "artifacts",
        exports=data / "exports",
        cache=data / "cache",
        settings_file=settings_dir / "settings.yaml",
        env_file=root / ".env",
    )


def required_directories(paths: WorkspacePaths) -> list[Path]:
    return [
        paths.inbox_memo,
        paths.inbox_files,
        paths.inbox_text,
        paths.wiki_concepts,
        paths.wiki_sources,
        paths.wiki_claims,
        paths.wiki_pages,
        paths.review_candidates,
        paths.review_mapping,
        paths.review_rejected,
        paths.raws,
        paths.templates,
        paths.prompts,
        paths.ontology,
        paths.raw,
        paths.normalized,
        paths.artifacts,
        paths.exports,
        paths.cache,
    ]
