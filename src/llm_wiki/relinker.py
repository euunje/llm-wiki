"""Safe re-linking logic for LLM-Wiki.

Handles rewriting wikilinks and relative links when promoting files
from `non_categories/` to standard categories.
"""

from __future__ import annotations

import re
import datetime
import shutil
from pathlib import Path
from . import db
from .page_writer import read_page, rebuild_index


def relink_references(wiki_dir: Path, old_slug: str, new_folder: str) -> int:
    """Scan all markdown files in `wiki_dir` recursively and rewrite wikilinks
    and relative markdown links referring to `old_slug` or `non_categories/old_slug`
    to point to `{new_folder}/{old_slug}`.

    Returns the number of files updated.
    """
    # Wikilink pattern matching: [[some-doc]], [[non_categories/some-doc]]
    # with optional display text, e.g. [[some-doc|display]]
    wikilink_pat = re.compile(
        rf"\[\[(?:non_categories/)?{re.escape(old_slug)}(\|[^\]]*)?\]\]"
    )
    
    # Markdown relative link pattern matching: ](../non_categories/some-doc.md) or ](non_categories/some-doc.md)
    markdown_pat = re.compile(
        rf"\]\(\.\./non_categories/{re.escape(old_slug)}\.md\)"
    )
    markdown_pat_alt = re.compile(
        rf"\]\(non_categories/{re.escape(old_slug)}\.md\)"
    )

    modified_count = 0
    
    for md_file in wiki_dir.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        
        new_content = content
        
        # Replace wikilinks
        def replace_wikilink(match):
            display = match.group(1) or ""
            return f"[[{new_folder}/{old_slug}{display}]]"
        
        new_content = wikilink_pat.sub(replace_wikilink, new_content)
        
        # Replace relative markdown links
        new_content = markdown_pat.sub(f"](../{new_folder}/{old_slug}.md)", new_content)
        new_content = markdown_pat_alt.sub(f"]({new_folder}/{old_slug}.md)", new_content)
        
        if new_content != content:
            md_file.write_text(new_content, encoding="utf-8")
            modified_count += 1
            
    return modified_count


def _mapped_folder(paths, folder: str) -> Path:
    return {
        "sources": paths.sources,
        "entities": paths.entities,
        "concepts": paths.concepts,
        "synthesis": paths.synthesis,
        "non_categories": paths.non_categories,
    }.get(folder, paths.wiki / folder)


def promote_file(paths, old_slug: str, new_folder: str) -> bool:
    """Move a file from the configured review folder to a mapped page folder."""
    old_path = paths.non_categories / f"{old_slug}.md"
    if not old_path.exists():
        return False
    
    new_dir = _mapped_folder(paths, new_folder)
    new_dir.mkdir(parents=True, exist_ok=True)
    new_path = new_dir / f"{old_slug}.md"
    
    # Read page and update frontmatter
    parsed = read_page(old_path)
    if parsed:
        parsed.frontmatter["status"] = "approved"
        # Determine the target type (entity vs concept vs synthesis)
        parsed.frontmatter["type"] = "entity" if new_folder == "entities" else ("concept" if new_folder == "concepts" else "synthesis")
        parsed.frontmatter["updated"] = datetime.date.today().isoformat()
        old_path.write_text(parsed.to_markdown(), encoding="utf-8")
    
    # Move the file on disk
    shutil.move(str(old_path), str(new_path))
    
    # Rewrite referencing links in other files
    relink_references(paths.wiki, old_slug, new_folder)
    
    # Update SQLite database references
    old_wiki_path = f"non_categories/{old_slug}.md"
    new_wiki_path = f"{new_folder}/{old_slug}.md"
    with db.connect(paths.state_db) as conn:
        conn.execute(
            "UPDATE source_pages SET wiki_path = ? WHERE wiki_path = ?",
            (new_wiki_path, old_wiki_path)
        )
    
    # Rebuild index
    rebuild_index(paths, datetime.date.today().isoformat())
    return True
