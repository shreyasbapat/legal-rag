"""initial schema: judgments, paragraphs, citations

Revision ID: 0001
Revises:
Create Date: 2026-09-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

court_level_enum = postgresql.ENUM("SUPREME_COURT", "HIGH_COURT", name="courtlevel")
citation_relation_enum = postgresql.ENUM(
    "UNCLASSIFIED", "FOLLOWED", "DISTINGUISHED", "OVERRULED", "REFERRED", name="citationrelation"
)


def upgrade() -> None:
    bind = op.get_bind()
    court_level_enum.create(bind, checkfirst=True)
    citation_relation_enum.create(bind, checkfirst=True)

    op.create_table(
        "judgments",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("court_level", court_level_enum, nullable=False),
        sa.Column("court_name", sa.Text(), nullable=False),
        sa.Column("case_title", sa.Text(), nullable=False),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("bench", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_judgments_citation", "judgments", ["citation"])

    op.create_table(
        "paragraphs",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "judgment_id",
            postgresql.UUID(),
            sa.ForeignKey("judgments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("para_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("judgment_id", "para_number", name="uq_paragraph_judgment_number"),
    )
    op.create_index("ix_paragraphs_judgment_id", "paragraphs", ["judgment_id"])

    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column(
            "source_judgment_id",
            postgresql.UUID(),
            sa.ForeignKey("judgments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_paragraph_id",
            postgresql.UUID(),
            sa.ForeignKey("paragraphs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "cited_judgment_id",
            postgresql.UUID(),
            sa.ForeignKey("judgments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "relation_type", citation_relation_enum, nullable=False, server_default="UNCLASSIFIED"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_citations_source_judgment_id", "citations", ["source_judgment_id"])
    op.create_index("ix_citations_source_paragraph_id", "citations", ["source_paragraph_id"])
    op.create_index("ix_citations_cited_judgment_id", "citations", ["cited_judgment_id"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("paragraphs")
    op.drop_table("judgments")
    citation_relation_enum.drop(op.get_bind(), checkfirst=True)
    court_level_enum.drop(op.get_bind(), checkfirst=True)
