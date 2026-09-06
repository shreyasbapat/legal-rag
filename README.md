# legal-rag

Retrieval-augmented generation over Indian Supreme Court and High Court
judgments (1947–present).

Naive semantic search is a poor fit for case law: a constitutional bench
judgment of the Supreme Court and a single-judge order of a High Court can
be textually similar and legally worlds apart, and a later judgment can
silently overrule an earlier one. This project treats structure and
precedent as first-class: judgments are stored at the paragraph level (the
unit lawyers actually cite), and a citation graph tracks which judgments
cite which, so retrieval can eventually rank by precedential authority and
filter out law that's no longer good law — not just by cosine similarity.

## Status

This repo currently implements the **structuring layer**: turning raw
judgment text into paragraphs and an extracted citation graph, persisted in
Postgres. Hybrid retrieval, authority-aware reranking, and generation are
not built yet — see [Roadmap](#roadmap).

## Architecture

```
raw judgment text (.txt + YAML front matter)
        │
        ▼
ParagraphParser        splits on native paragraph numbering ("1.", "2.", ...),
                        falling back to blank-line splitting when numbering
                        isn't reliably sequential
        │
        ▼
citation_extractor      pulls AIR / SCC / SCR citation strings out of each
                        paragraph's text
        │
        ▼
ingestion.pipeline      persists Judgment → Paragraph → Citation rows,
                        then resolves citation strings to the Judgment
                        they refer to (once that judgment is in the corpus)
        │
        ▼
   PostgreSQL           judgments, paragraphs, citations (see
                        src/legal_rag/db/models.py)
```

Why paragraphs, not fixed-size chunks: Indian judgments are natively
paragraph-numbered, and that numbering is exactly what later judgments and
counsel cite ("see para 42"). Chunking any other way throws away a
citation-grade retrieval unit for no benefit.

Why a citation graph up front: it's the basis for the two things a legal
RAG system gets wrong if it's missing — surfacing an overruled judgment as
if it were good law, and ranking a low-authority order above the
Supreme Court judgment that actually settled the question.

## Getting started

Requires Python 3.11+ and Docker (for Postgres).

```bash
git clone https://github.com/shreyasbapat/legal-rag.git
cd legal-rag

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env        # defaults match docker-compose.yml as-is

docker compose up -d        # starts Postgres on localhost:5432
alembic upgrade head         # creates the judgments/paragraphs/citations tables
```

Ingest the bundled example judgments:

```bash
legal-rag ingest examples/
```

This ingests two illustrative judgments (`AIR 1973 SC 1461` and
`AIR 1967 SC 1643`, the latter cited by the former) and reports how many
citations it was able to resolve to a judgment already in the corpus.

Ingest your own corpus the same way — point `legal-rag ingest` at a
directory of `.txt` files. Each file needs a YAML front matter header
followed by the judgment body; see [`examples/sample_judgment.txt`](examples/sample_judgment.txt)
for the exact shape:

```
---
court_level: SUPREME_COURT      # SUPREME_COURT | HIGH_COURT
court_name: Supreme Court of India
case_title: Kesavananda Bharati v. State of Kerala
citation: AIR 1973 SC 1461      # optional; omit if unreported
decision_date: 1973-04-24
bench: Sikri C.J., Shelat, Grover, JJ.   # optional
---
1. First paragraph of the judgment body.

2. Second paragraph.
```

Run `legal-rag ingest <path>` again after adding more files — citation
resolution is idempotent and re-running only picks up newly-resolvable
citations (e.g. a judgment that was ingested before the one it cites).

### Running the test suite

Tests run against an in-memory SQLite database and don't need Postgres or
Docker running:

```bash
pytest
ruff check .
mypy src
```

## Repository layout

```
src/legal_rag/
  config.py              environment-based settings (DATABASE_URL)
  db/
    models.py             Judgment, Paragraph, Citation ORM models
    guid.py                cross-dialect UUID column type (Postgres native, SQLite for tests)
    session.py             engine/session management
  ingestion/
    paragraph_parser.py    numbered-paragraph segmentation
    citation_extractor.py  AIR / SCC / SCR citation string extraction
    pipeline.py             front-matter parsing + orchestration + citation resolution
  cli.py                   `legal-rag ingest`
migrations/                Alembic migrations (source of truth for the Postgres schema)
examples/                  sample judgment files for `legal-rag ingest`
tests/
```

## Roadmap

1. **Citation relation classification** — classify each citation edge as
   `FOLLOWED` / `DISTINGUISHED` / `OVERRULED` / `REFERRED` (currently all
   land as `UNCLASSIFIED`). This is what lets retrieval exclude judgments
   that are no longer good law.
2. **Authority scoring** — PageRank-style score over the citation graph,
   weighted by court hierarchy (Supreme Court > High Court of the same
   jurisdiction > High Court of another jurisdiction).
3. **Hybrid retrieval** — BM25 + dense embeddings (a legal-domain
   embedding model, not a generic one — legal terminology needs exact-match
   recall that pure semantic search misses) with jurisdiction/date/"good
   law" filters and authority-weighted reranking.
4. **Generation with citation verification** — answers cite only retrieved
   paragraphs, with a second-pass check that each cited paragraph actually
   supports the sentence it's attached to.
5. Scale ingestion from Supreme Court only to major High Courts, then the
   remaining ones.
