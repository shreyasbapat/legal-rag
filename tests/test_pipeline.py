from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from legal_rag.db.models import CourtLevel
from legal_rag.ingestion.pipeline import (
    JudgmentFileError,
    JudgmentInput,
    ingest_judgment,
    load_judgment_file,
    resolve_citations,
)


def _sc_judgment(citation: str | None, raw_text: str, title: str = "State v. Doe") -> JudgmentInput:
    return JudgmentInput(
        court_level=CourtLevel.SUPREME_COURT,
        court_name="Supreme Court of India",
        case_title=title,
        decision_date=date(1973, 4, 24),
        raw_text=raw_text,
        citation=citation,
    )


def test_ingest_judgment_persists_paragraphs_and_citations(db_session: Session) -> None:
    text = "1. The facts are undisputed.\n\n2. As held in AIR 1971 SC 100, this is settled law."
    judgment = ingest_judgment(db_session, _sc_judgment("AIR 1973 SC 1461", text))

    assert len(judgment.paragraphs) == 2
    assert judgment.paragraphs[1].para_number == 2
    assert len(judgment.citations_made) == 1
    assert judgment.citations_made[0].raw_text == "AIR 1971 SC 100"
    assert judgment.citations_made[0].cited_judgment_id is None


def test_resolve_citations_links_to_matching_judgment(db_session: Session) -> None:
    older = ingest_judgment(
        db_session, _sc_judgment("AIR 1971 SC 100", "1. An earlier ruling.", title="Older v. State")
    )
    newer_text = "1. As held in AIR 1971 SC 100, this is settled law."
    newer = ingest_judgment(
        db_session, _sc_judgment("AIR 1973 SC 1461", newer_text, title="Newer v. State")
    )

    resolved_count = resolve_citations(db_session)

    assert resolved_count == 1
    assert newer.citations_made[0].cited_judgment_id == older.id


def test_resolve_citations_is_idempotent(db_session: Session) -> None:
    ingest_judgment(db_session, _sc_judgment("AIR 1971 SC 100", "1. An earlier ruling."))
    ingest_judgment(db_session, _sc_judgment("AIR 1973 SC 1461", "1. As held in AIR 1971 SC 100."))

    first_pass = resolve_citations(db_session)
    second_pass = resolve_citations(db_session)

    assert first_pass == 1
    assert second_pass == 0


def test_load_judgment_file_parses_front_matter(tmp_path: Path) -> None:
    content = """---
court_level: SUPREME_COURT
court_name: Supreme Court of India
case_title: Kesavananda Bharati v. State of Kerala
citation: AIR 1973 SC 1461
decision_date: 1973-04-24
bench: Sikri C.J., Shelat J.
---
1. This is the first paragraph of the judgment.

2. This is the second.
"""
    path = tmp_path / "judgment.txt"
    path.write_text(content)

    data = load_judgment_file(path)

    assert data.case_title == "Kesavananda Bharati v. State of Kerala"
    assert data.decision_date == date(1973, 4, 24)
    assert data.court_level is CourtLevel.SUPREME_COURT
    assert "This is the first paragraph" in data.raw_text


def test_load_judgment_file_rejects_missing_required_field(tmp_path: Path) -> None:
    content = """---
court_name: Supreme Court of India
case_title: Missing Court Level
decision_date: 1973-04-24
---
1. Body text.
"""
    path = tmp_path / "bad.txt"
    path.write_text(content)

    with pytest.raises(JudgmentFileError, match="court_level"):
        load_judgment_file(path)


def test_load_judgment_file_rejects_invalid_court_level(tmp_path: Path) -> None:
    content = """---
court_level: DISTRICT_COURT
court_name: Some District Court
case_title: Invalid Level
decision_date: 1973-04-24
---
1. Body text.
"""
    path = tmp_path / "bad.txt"
    path.write_text(content)

    with pytest.raises(JudgmentFileError, match="invalid court_level"):
        load_judgment_file(path)
