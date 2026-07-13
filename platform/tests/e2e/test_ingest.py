import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from brp.adapters.contracts import CandidateDecision, ExtractionBatch, SourceSnapshot
from brp.db import create_database_engine
from brp.ingestion import IngestionRunner
from brp.ir.models import DecisionContent
from brp.repository.service import RevisionRepository

PLATFORM = Path(__file__).resolve().parents[2]
FIXTURE = PLATFORM / "tests/fixtures/conformance/enrollment_eligibility.json"


def batch(key: str, snapshot: str, *, minimum_age: int = 18) -> ExtractionBatch:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["decisionId"] = key
    document["rules"][0]["when"]["all"][0]["right"]["value"] = minimum_age
    return ExtractionBatch(
        adapter="code-java",
        decisions=[
            CandidateDecision(decision_key=key, content=DecisionContent.model_validate(document))
        ],
        source_snapshot=SourceSnapshot(
            source_id="git:fixture",
            revision=snapshot,
            content_hash=snapshot,
            captured_at=datetime.now(UTC),
        ),
        diagnostics=[],
    )


def test_identical_rerun_inserts_nothing_and_changed_source_creates_draft() -> None:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    key = f"ingest_{uuid4().hex}"
    with Session(engine) as session:
        runner = IngestionRunner(session)
        first = runner.ingest(
            [batch(key, "a" * 64)],
            actor="ingest-maker",
            effective_from=datetime(2026, 10, 1, tzinfo=UTC),
        )
        same = runner.ingest(
            [batch(key, "a" * 64)],
            actor="ingest-maker",
            effective_from=datetime(2026, 10, 1, tzinfo=UTC),
        )
        changed = runner.ingest(
            [batch(key, "b" * 64, minimum_age=19)],
            actor="ingest-maker",
            effective_from=datetime(2026, 11, 1, tzinfo=UTC),
        )
        assert first.inserted_revisions == [(key, 1)]
        assert same.inserted_revisions == [] and same.skipped == 1
        assert changed.inserted_revisions == [(key, 2)]
        repository = RevisionRepository(session)
        assert repository.get_revision(key, 2).lifecycle_status == "DRAFT"
        assert len(repository.get_audit(key)) == 2
    engine.dispose()
