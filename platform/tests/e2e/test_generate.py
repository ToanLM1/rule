import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from brp.config.models import load_site_profile
from brp.db import create_database_engine
from brp.generation import GenerationOrchestrator
from brp.generators.contracts import GeneratedArtifact
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.ir.models import DecisionContent
from brp.repository.errors import ApprovedRevisionNotFoundError
from brp.repository.lifecycle import LifecycleService
from brp.repository.service import RevisionRepository

PLATFORM = Path(__file__).resolve().parents[2]
ROOT = PLATFORM.parent
FIXTURE = PLATFORM / "tests/fixtures/conformance/premium_adjustments.json"


class Builder:
    name = "fixture-java"
    version = "1.0.0"

    def build(self, release):
        return [GeneratedArtifact.create("src/generated/java/Decision.java", release.release_hash)]


class FailingBuilder(Builder):
    def build(self, release):
        raise RuntimeError("planted generator failure")


def approved(session: Session, key: str) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["decisionId"] = key
    content = DecisionContent.model_validate(document)
    decision = RevisionRepository(session).create_decision(
        key, content, "maker", datetime(2026, 8, 1, tzinfo=UTC)
    )
    golden = GoldenRepository(session)
    suite = golden.create_revision(
        key,
        [
            GoldenCaseData(
                case_key="smoker",
                input={"age": 30, "productCode": "CANCER_BASIC", "smoker": True},
                expected=[{"premiumLoadingPct": 20}],
                provenance={"type": "LEGACY_TEST"},
            )
        ],
        "maker",
    )
    golden.submit(suite, "maker")
    golden.approve(suite, "checker")
    lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
    lifecycle.submit(decision, "maker")
    lifecycle.approve(decision, "checker")
    session.commit()


def test_generation_requires_approved_revision_and_is_atomic_deterministic(tmp_path: Path) -> None:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    profile = load_site_profile(ROOT / "config/sites/fixture.yaml")
    key = f"generate_{uuid4().hex}"
    with Session(engine) as session:
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        document["decisionId"] = f"draft_{uuid4().hex}"
        draft_key = document["decisionId"]
        RevisionRepository(session).create_decision(
            draft_key,
            DecisionContent.model_validate(document),
            "maker",
            datetime(2026, 8, 1, tzinfo=UTC),
        )
        with pytest.raises(ApprovedRevisionNotFoundError):
            GenerationOrchestrator(session, Builder()).generate(
                profile, draft_key, tmp_path, revision=1
            )
        session.rollback()
        approved(session, key)
        orchestrator = GenerationOrchestrator(session, Builder())
        first = orchestrator.generate(profile, key, tmp_path, revision=1)
        before = {
            file.relative_to(first): file.read_bytes()
            for file in first.rglob("*")
            if file.is_file()
        }
        second = orchestrator.generate(profile, key, tmp_path, revision=1)
        after = {
            file.relative_to(second): file.read_bytes()
            for file in second.rglob("*")
            if file.is_file()
        }
        assert before == after
        failed_key = f"failed_{uuid4().hex}"
        approved(session, failed_key)
        with pytest.raises(RuntimeError, match="planted"):
            GenerationOrchestrator(session, FailingBuilder()).generate(
                profile, failed_key, tmp_path, revision=1
            )
        assert not (tmp_path / failed_key).exists()
    engine.dispose()
