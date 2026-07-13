"""Business Rules Platform local orchestration commands."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from brp_mcp_db import DatabaseConnector
from sqlalchemy.orm import Session

from brp.adapters.code_java import JavaRuleMiner
from brp.adapters.contracts import ExtractionBatch
from brp.adapters.db_postgres import PostgresTableAdapter
from brp.adapters.docs_manual import ManualDocumentAdapter
from brp.adapters.joern import JoernLocator, JoernSlicer
from brp.config.models import load_site_profile
from brp.db import create_database_engine
from brp.generation import GenerationOrchestrator, JavaCliReleaseBuilder
from brp.ingestion import IngestionRunner

app = typer.Typer(no_args_is_help=True, help="Governed business-rules platform")


@app.callback()
def main() -> None:
    """Run governed extraction, generation, and delivery workflows."""


@app.command("ingest")
def ingest_command(
    site: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Site YAML profile")],
    actor: Annotated[str, typer.Option(help="Maker actor recorded in audit")] = "fixture-ingest",
) -> None:
    """Discover configured sources and idempotently ingest candidate batches."""
    site = site.resolve()
    root = _repository_root(site)
    profile = load_site_profile(site)
    batches: list[ExtractionBatch] = []
    if "db-postgres" in profile.adapters:
        raw_url = os.getenv(profile.source.db.connection_env)
        if raw_url is None:
            raise typer.BadParameter(
                f"environment variable {profile.source.db.connection_env} is required"
            )
        connector = DatabaseConnector(raw_url.replace("postgresql+psycopg://", "postgresql://"))
        adapter = PostgresTableAdapter(connector, profile, root / profile.mapping_spec)
        batches.extend(adapter.extract(source) for source in adapter.discover(profile))
    if "code-java" in profile.adapters:
        miner = JavaRuleMiner(root / "platform/tests/fixtures/conformance")
        for repository in profile.source.repositories:
            locator = JoernLocator(root / repository.path, repository.alias, repository.revision)
            for context in profile.source.program_contexts:
                if context.repository != repository.alias:
                    continue
                manifest = JoernSlicer().slice(locator.locate(context.class_name, context.method))
                batches.append(miner.mine(manifest))
    if "docs-manual" in profile.adapters:
        manual_paths = [
            *sorted((root / "fixtures/manual").glob("*.docx")),
            *sorted((root / "fixtures/manual").glob("*.xlsx")),
        ]
        manual = ManualDocumentAdapter(manual_paths)
        batches.extend(manual.extract(source) for source in manual.discover(profile))
    engine = create_database_engine()
    with Session(engine) as session:
        result = IngestionRunner(session).ingest(
            batches, actor=actor, effective_from=datetime.now(UTC)
        )
    engine.dispose()
    typer.echo(
        f"INGESTED: revisions={len(result.inserted_revisions)} "
        f"review_items={result.review_items} skipped={result.skipped}"
    )


def _repository_root(site: Path) -> Path:
    for parent in [site.parent, *site.parents]:
        if (parent / "IMPLEMENTATION_PLAN.md").is_file():
            return parent
    raise typer.BadParameter("site profile must live inside a BRP repository checkout")


@app.command("generate")
def generate_command(
    site: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Site YAML profile")],
    decision: Annotated[str, typer.Option(help="Decision key")],
    revision: Annotated[int | None, typer.Option(min=1)] = None,
    as_of: Annotated[datetime | None, typer.Option()] = None,
    output: Annotated[Path, typer.Option(help="Versioned generation root")] = Path("out/generated"),
) -> None:
    """Generate an approved, effective decision and its authoritative tests."""
    site = site.resolve()
    root = _repository_root(site)
    profile = load_site_profile(site)
    engine = create_database_engine()
    with Session(engine) as session:
        destination = GenerationOrchestrator(session, JavaCliReleaseBuilder(root)).generate(
            profile,
            decision,
            (root / output).resolve() if not output.is_absolute() else output,
            revision=revision,
            as_of=as_of,
        )
    engine.dispose()
    typer.echo(f"GENERATED: {destination}")
