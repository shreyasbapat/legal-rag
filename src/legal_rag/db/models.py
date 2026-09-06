"""ORM models for the judgment corpus.

Schema shape, in one paragraph: a ``Judgment`` is split into numbered
``Paragraph`` rows (Indian judgments are natively para-numbered, so we use
that as the retrieval chunk unit rather than re-chunking by token count). A
``Citation`` is a directed edge from a source paragraph to another judgment,
extracted from raw text and optionally resolved to that judgment's row. The
citation graph this produces is what later lets retrieval rank by precedent
authority and filter out overruled law, rather than by semantic similarity
alone.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from legal_rag.db.base import Base
from legal_rag.db.guid import GUID


class CourtLevel(enum.StrEnum):
    """Coarse court hierarchy. High Court identity itself is free text on
    Judgment.court_name (there are 25 of them and the list changes; an enum
    would need editing every time a new bench is added, which defeats the
    purpose of an enum)."""

    SUPREME_COURT = "SUPREME_COURT"
    HIGH_COURT = "HIGH_COURT"


class CitationRelation(enum.StrEnum):
    """How a citing paragraph treats the cited judgment.

    UNCLASSIFIED is the default at extraction time; classifying the rest
    requires reading the surrounding text (LLM-assisted, future work) and is
    the single highest-leverage feature for not surfacing overruled law.
    """

    UNCLASSIFIED = "UNCLASSIFIED"
    FOLLOWED = "FOLLOWED"
    DISTINGUISHED = "DISTINGUISHED"
    OVERRULED = "OVERRULED"
    REFERRED = "REFERRED"


class Judgment(Base):
    __tablename__ = "judgments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    court_level: Mapped[CourtLevel] = mapped_column(Enum(CourtLevel), nullable=False)
    court_name: Mapped[str] = mapped_column(Text, nullable=False)
    case_title: Mapped[str] = mapped_column(Text, nullable=False)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    bench: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    paragraphs: Mapped[list[Paragraph]] = relationship(
        back_populates="judgment", cascade="all, delete-orphan", order_by="Paragraph.para_number"
    )
    citations_made: Mapped[list[Citation]] = relationship(
        back_populates="source_judgment",
        foreign_keys="Citation.source_judgment_id",
        cascade="all, delete-orphan",
    )
    citations_received: Mapped[list[Citation]] = relationship(
        back_populates="cited_judgment",
        foreign_keys="Citation.cited_judgment_id",
    )

    def __repr__(self) -> str:
        return (
            f"Judgment(id={self.id!r}, case_title={self.case_title!r}, "
            f"citation={self.citation!r})"
        )


class Paragraph(Base):
    __tablename__ = "paragraphs"
    __table_args__ = (
        UniqueConstraint("judgment_id", "para_number", name="uq_paragraph_judgment_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    judgment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    para_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    judgment: Mapped[Judgment] = relationship(back_populates="paragraphs")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="source_paragraph", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"Paragraph(id={self.id!r}, judgment_id={self.judgment_id!r}, "
            f"para_number={self.para_number!r})"
        )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_judgment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("judgments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_paragraph_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("paragraphs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cited_judgment_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("judgments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    relation_type: Mapped[CitationRelation] = mapped_column(
        Enum(CitationRelation), nullable=False, default=CitationRelation.UNCLASSIFIED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_judgment: Mapped[Judgment] = relationship(
        back_populates="citations_made", foreign_keys=[source_judgment_id]
    )
    source_paragraph: Mapped[Paragraph | None] = relationship(back_populates="citations")
    cited_judgment: Mapped[Judgment | None] = relationship(
        back_populates="citations_received", foreign_keys=[cited_judgment_id]
    )

    def __repr__(self) -> str:
        return (
            f"Citation(raw_text={self.raw_text!r}, "
            f"resolved={self.cited_judgment_id is not None})"
        )
