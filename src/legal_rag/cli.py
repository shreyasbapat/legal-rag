"""Command-line entry point: `legal-rag ingest <path>`."""

from __future__ import annotations

from pathlib import Path

import click

from legal_rag.db.session import session_scope
from legal_rag.ingestion.pipeline import (
    JudgmentFileError,
    ingest_judgment,
    load_judgment_file,
    resolve_citations,
)


@click.group()
def cli() -> None:
    """legal-rag: ingest and query Indian Supreme Court and High Court judgments."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def ingest(path: Path) -> None:
    """Ingest a single judgment file, or every .txt file under a directory.

    Each file must be a plain-text judgment with a YAML front matter header
    -- see examples/sample_judgment.txt for the expected format.
    """
    files = sorted(path.glob("**/*.txt")) if path.is_dir() else [path]
    if not files:
        raise click.ClickException(f"No .txt files found under {path}")

    ingested, failed = 0, 0
    with session_scope() as session:
        for file_path in files:
            try:
                data = load_judgment_file(file_path)
                ingest_judgment(session, data)
            except JudgmentFileError as exc:
                click.echo(f"skip: {exc}", err=True)
                failed += 1
                continue
            ingested += 1
            click.echo(f"ingested: {file_path} -> {data.case_title}")

        resolved = resolve_citations(session)

    click.echo(f"\n{ingested} ingested, {failed} skipped, {resolved} citation(s) resolved.")


if __name__ == "__main__":
    cli()
