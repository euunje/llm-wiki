# AGENTS.md — LLM-Wiki Schema & Conventions

> This file is the **contract** between you and the LLM agent that maintains
> this wiki. Read it before any ingest/query/lint operation. It tells you what
> the wiki looks like, where things go, how pages are formatted, and how to
> handle edge cases. Edit this file as conventions evolve.

## 1. Project layout

```
.
├── raw/         ← Source documents. IMMUTABLE. Read-only for the agent.
├── wiki/        ← LLM-maintained markdown. The agent owns generated pages here.
│   ├── index.md          ← Auto-maintained catalog of generated wiki pages.
│   ├── log.md            ← Append-only chronological history.
│   ├── sources/          ← One summary page per ingested source.
│   ├── entities/         ← People, places, organizations, models, products.
│   ├── concepts/         ← Topics, techniques, theories, ideas.
│   ├── synthesis/        ← Overview pages, comparisons, evolving theses.
│   └── non_categories/   ← Review queue for ambiguous or externally owned items.
└── schema/AGENTS.md      ← This file.
```

Configured installs may map these logical folders to different physical paths.
Always follow the project config rather than hard-coding `wiki/<folder>`.

## 2. Page conventions

Every generated wiki page must:

1. **Start with YAML frontmatter** containing at minimum:
   ```yaml
   ---
   title: "Page Title"
   type: source | entity | concept | synthesis | review
   pageKind: source | entity | concept | synthesis | review  # optional for legacy pages; required for review items
   tags: [tag1, tag2]
   created: YYYY-MM-DD
   updated: YYYY-MM-DD
   sources: ["sources/source-slug.md"]
   confidence: high | medium | low
   ---
   ```

2. **Use `[[wikilinks]]`** for every cross-reference. Never plain markdown
   links for pages inside the wiki. Wikilinks are what make the Obsidian graph
   view work.

3. **Cite sources** for every non-trivial claim using a footnote-style anchor:
   `Karpathy proposed the LLM-Wiki pattern in 2026[^source-llm-wiki-gist]`,
   with the footnote linking to a `sources/` page.

4. **Be incremental.** When updating a page, preserve existing structure. Add
   sections, don't rewrite from scratch. Use `## Updates` sub-sections with
   dates if a claim is being revised.

## 3. Page types

### `sources/<slug>.md`
A summary of one ingested source. Contains bibliographic info, 3–8 bullet key
takeaways, and related entity/concept pages touched by this source.

### `entities/<slug>.md`
A page about a single named thing (person, lab, model, product, place).

### `concepts/<slug>.md`
A page about an idea, technique, or topic.

### `synthesis/<slug>.md`
Overview pages, comparisons, and evolving theses across multiple sources.

### `non_categories/<slug>.md`
A pending review item. Use this for low-confidence, ambiguous, or externally
owned content. Review pages must have:

```yaml
type: review
pageKind: review
status: pending_review
```

If the item belongs to another system, include `suggestedExternalOwner`:

```yaml
suggestedExternalOwner: 8000-web-config  # guide-like operational/config/playbook content
suggestedExternalOwner: mcp-map          # map/MOC/navigation/graph content
```

## 4. Routing rules

The ingest extractor uses candidates with `pageKind`:

- `entity` → generate or merge an entity page.
- `concept` → generate or merge a concept page.
- `review` → create a deterministic review item in `non_categories/`; do not
  draft a normal wiki page for it.

Do **not** auto-generate static guide/map pages from ingest:

- Guide-like content — runbooks, tutorials, how-tos, cheatsheets, deployment
  notes, operational configs — should become `pageKind: review` with
  `suggestedExternalOwner: 8000-web-config`.
- Map/MOC-like content — navigation hubs, graph maps, relationship maps,
  index pages — should become `pageKind: review` with
  `suggestedExternalOwner: mcp-map`.

## 5. Naming rules

- **Slugs are kebab-case lowercase ASCII.** `karpathy.md`, not `Karpathy.md`
  or `andrej_karpathy.md`.
- **Use the most common/canonical name** as the slug. Disambiguate only when
  necessary (`apple-inc.md` vs `apple-fruit.md`).
- **Acronyms stay together** (`rag.md`, `llm.md`, not `r-a-g.md`).

## 6. Ingest workflow

When a new source arrives in `raw/`:

1. **Read** the full source.
2. **Extract candidates** with `pageKind: entity | concept | review`.
3. **Write** `sources/<slug>.md` with the summary.
4. **For each entity candidate:** merge/create under `entities/`.
5. **For each concept candidate:** merge/create under `concepts/`.
6. **For each review candidate:** create/update a pending review item under
   `non_categories/` without an extra LLM drafting call.
7. **Update `synthesis/`** pages only when explicitly requested or saved from a
   query result.
8. **Append to `log.md`** and **update `index.md`**.

A single source may create fewer normal wiki pages than older versions because
ambiguous, guide-like, or map-like material is now held for review instead of
being filed automatically.

## 7. Query workflow

When the user asks a question:

1. **Search** the wiki (BM25 + vector + rerank via QMD).
2. **Read** the top 5–10 most relevant pages in full.
3. **Synthesize** an answer in markdown.
4. **Cite every claim** with `[[wikilink]]` references.
5. **Offer to save** the answer back as a `synthesis/` page if it's a
   non-trivial new analysis.

## 8. Lint workflow

When the user runs `wiki lint`:

- **Contradictions:** Find pages making opposing claims. Flag them.
- **Orphans:** Pages with no inbound `[[wikilinks]]`. Suggest linking or
  deleting.
- **Stale claims:** Older claims contradicted by newer sources.
- **Missing pages:** Concepts mentioned repeatedly without their own page.
- **Review queue:** Keep `non_categories/` as pending review; promote only to
  `entities/`, `concepts/`, or `synthesis/` unless the project config says
  otherwise.

## 9. Contradiction handling

When new source contradicts existing wiki claim:

- **Don't silently overwrite.** That destroys provenance.
- **Add an `## Updates` section** to the existing page with the date and the
  new claim, citing the new source.
- **Flag in `log.md`** with `contradiction` tag so lint can find it.
- **Update `confidence:` frontmatter** to `medium` or `low` if the
  disagreement is significant.

## 10. Frontmatter date format

Always `YYYY-MM-DD` (ISO 8601 calendar date). Use timestamps only in machine
fields such as `processed_at`.

## 11. What the agent must never do

- ❌ **Never edit `raw/`.** Sources are immutable.
- ❌ **Never delete a wiki page** without explicit user confirmation.
- ❌ **Never overwrite existing claims silently.** Use `## Updates`.
- ❌ **Never invent citations.** If you don't know which source supports a
  claim, mark it `confidence: low` and leave the source field empty.
- ❌ **Never use plain markdown links** between wiki pages. Use `[[wikilinks]]`.
- ❌ **Never auto-file guide-like or map-like material as normal wiki pages.**
  Route it to review with the appropriate `suggestedExternalOwner`.

---

*This file is intentionally editable. As you and the agent figure out what
works for your domain, refine these conventions and commit the changes.*
