"""Orchestrates ingestion: parse a judgment source file, persist it, extract citations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import frontmatter
from sqlalchemy import select
from sqlalchemy.orm import Session

from legal_rag.db.models import Citation, CourtLevel, Judgment, Paragraph
from legal_rag.ingestion.citation_extractor import extract_citations
from legal_rag.ingestion.paragraph_parser import ParagraphParser

_REQUIRED_FIELDS = ("court_level", "court_name", "case_title", "decision_date")


class JudgmentFileError(ValueError):
    """Raised when a judgment source file has missing or malformed front matter."""


@dataclass(frozen=True)
class JudgmentInput:
    court_level: CourtLevel
    court_name: str
    case_title: str
    decision_date: date
    raw_text: str
    citation: str | None = None
    bench: str | None = None
    source_path: str | None = None


def load_judgment_file(path: Path) -> JudgmentInput:
    """Parse a judgment source file: YAML front matter for metadata, body for judgment text.

    See examples/sample_judgment.txt for the expected format.
    """
    post = frontmatter.load(path)
    missing = [field for field in _REQUIRED_FIELDS if field not in post.metadata]
    if missing:
        raise JudgmentFileError(
            f"{path}: missing required front matter field(s): {', '.join(missing)}"
        )

    raw_court_level = str(post.metadata["court_level"])
    try:
        court_level = CourtLevel(raw_court_level)
    except ValueError as exc:
        valid = ", ".join(level.value for level in CourtLevel)
        raise JudgmentFileError(
            f"{path}: invalid court_level {raw_court_level!r}, expected one of: {valid}"
        ) from exc

    decision_date = post.metadata["decision_date"]
    if not isinstance(decision_date, date):
        raise JudgmentFileError(f"{path}: decision_date must be an ISO date (YYYY-MM-DD)")

    body = post.content.strip()
    if not body:
        raise JudgmentFileError(f"{path}: judgment body is empty")

    citation = post.metadata.get("citation")
    bench = post.metadata.get("bench")

    return JudgmentInput(
        court_level=court_level,
        court_name=str(post.metadata["court_name"]),
        case_title=str(post.metadata["case_title"]),
        decision_date=decision_date,
        raw_text=body,
        citation=str(citation) if citation is not None else None,
        bench=str(bench) if bench is not None else None,
        source_path=str(path),
    )


def ingest_judgment(
    session: Session, data: JudgmentInput, *, paragraph_parser: ParagraphParser | None = None
) -> Judgment:
    """Persist a judgment, its paragraphs, and citations extracted from those paragraphs.

    Does not resolve citations to their target judgments -- call
    resolve_citations() once per batch instead of after each judgment,
    since a judgment ingested earlier in the batch may cite one that
    arrives later in the same batch.
    """
    parser = paragraph_parser or ParagraphParser()

    judgment = Judgment(
        court_level=data.court_level,
        court_name=data.court_name,
        case_title=data.case_title,
        citation=data.citation,
        decision_date=data.decision_date,
        bench=data.bench,
        source_path=data.source_path,
        raw_text=data.raw_text,
    )
    session.add(judgment)
    session.flush()  # assign judgment.id, needed as a foreign key below

    for parsed in parser.parse(data.raw_text):
        paragraph = Paragraph(judgment_id=judgment.id, para_number=parsed.number, text=parsed.text)
        session.add(paragraph)
        session.flush()  # assign paragraph.id

        for raw_citation in extract_citations(parsed.text):
            session.add(
                Citation(
                    source_judgment_id=judgment.id,
                    source_paragraph_id=paragraph.id,
                    raw_text=raw_citation,
                )
            )

    session.flush()
    return judgment


def resolve_citations(session: Session) -> int:
    """Link unresolved citations to their target Judgment by matching raw_text to Judgment.citation.

    Idempotent and safe to re-run as more judgments are ingested (recall
    only improves over time; already-resolved citations are left alone).
    Returns the number of citations newly resolved.
    """
    unresolved = session.scalars(select(Citation).where(Citation.cited_judgment_id.is_(None))).all()
    if not unresolved:
        return 0

    citation_lookup = {
        judgment.citation: judgment.id
        for judgment in session.scalars(select(Judgment).where(Judgment.citation.is_not(None)))
    }

    resolved_count = 0
    for citation in unresolved:
        target_id = citation_lookup.get(citation.raw_text)
        if target_id is not None and target_id != citation.source_judgment_id:
            citation.cited_judgment_id = target_id
            resolved_count += 1

    session.flush()
    return resolved_count
