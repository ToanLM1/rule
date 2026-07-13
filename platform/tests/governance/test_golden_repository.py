import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from brp.db import create_database_engine
from brp.governance.golden import (
    GoldenCaseData,
    GoldenRepository,
    GoldenSuiteEvidencePolicy,
)
from brp.ir.models import DecisionContent
from brp.repository.errors import ApprovalEvidenceError, SelfApprovalError
from brp.repository.lifecycle import LifecycleService
from brp.repository.service import RevisionRepository

PLATFORM = Path(__file__).resolve().parents[2]
FIXTURE = PLATFORM / "tests/fixtures/conformance/enrollment_eligibility.json"


def content(key: str) -> DecisionContent:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["decisionId"] = key
    return DecisionContent.model_validate(document)


def case() -> GoldenCaseData:
    return GoldenCaseData(
        case_key="under-age",
        input={"age": 17, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
        expected={"eligible": False, "reasonCode": "UNDER_AGE"},
        provenance={"type": "LEGACY_BEHAVIOR", "test": "EnrollmentValidatorTest#underAge"},
    )


def test_suite_maker_checker_lookup_determinism_and_release_evidence() -> None:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    key = f"golden_{uuid4().hex}"
    with Session(engine) as session:
        revision = RevisionRepository(session).create_decision(
            key, content(key), "maker", datetime(2026, 8, 1, tzinfo=UTC)
        )
        golden = GoldenRepository(session)
        rows = [
            {"region_code": "SEOUL", "eligible": True, "name": "서울"},
            {"region_code": "JEJU", "eligible": False, "name": "제주"},
        ]
        first = golden.snapshot_lookup(
            "region", rows, {"table": "region_eligibility"}, approved=True
        )
        second = golden.snapshot_lookup(
            "region", list(reversed(rows)), {"table": "region_eligibility"}, approved=True
        )
        assert first.id == second.id
        suite = golden.create_revision(
            key, [case()], "maker", lookup_snapshot_hashes=[first.content_hash]
        )
        golden.submit(suite, "maker")
        with pytest.raises(SelfApprovalError):
            golden.approve(suite, "maker")
        golden.approve(suite, "checker")
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        lifecycle.submit(revision, "maker")
        lifecycle.approve(revision, "checker")
        session.commit()
        assert revision.lifecycle_status == "APPROVED"
    engine.dispose()


def test_decision_approval_fails_without_approved_suite() -> None:
    engine = create_database_engine()
    key = f"no_evidence_{uuid4().hex}"
    with Session(engine) as session:
        revision = RevisionRepository(session).create_decision(
            key, content(key), "maker", datetime(2026, 8, 1, tzinfo=UTC)
        )
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        lifecycle.submit(revision, "maker")
        with pytest.raises(ApprovalEvidenceError):
            lifecycle.approve(revision, "checker")
        session.rollback()
    engine.dispose()


def test_golden_cases_reject_mutation() -> None:
    engine = create_database_engine()
    key = f"immutable_suite_{uuid4().hex}"
    with Session(engine) as session:
        RevisionRepository(session).create_decision(
            key, content(key), "maker", datetime(2026, 8, 1, tzinfo=UTC)
        )
        suite = GoldenRepository(session).create_revision(key, [case()], "maker")
        session.commit()
        with pytest.raises(ProgrammingError, match="BRP_IMMUTABLE_RECORD"):
            session.execute(
                text("UPDATE golden_cases SET case_key = 'changed' WHERE suite_revision_id = :id"),
                {"id": suite.id},
            )
            session.flush()
        session.rollback()
    engine.dispose()


def test_configurable_release_evidence_case_and_lookup_requirements() -> None:
    engine = create_database_engine()
    key = f"configured_evidence_{uuid4().hex}"
    with Session(engine) as session:
        decision = RevisionRepository(session).create_decision(
            key, content(key), "maker", datetime(2026, 8, 1, tzinfo=UTC)
        )
        golden = GoldenRepository(session)
        suite = golden.create_revision(key, [case()], "maker")
        golden.submit(suite, "maker")
        golden.approve(suite, "checker")
        with pytest.raises(ApprovalEvidenceError, match="at least 2"):
            GoldenSuiteEvidencePolicy(minimum_cases=2).require_approved_evidence(session, decision)
        with pytest.raises(ApprovalEvidenceError, match="lookup snapshot"):
            GoldenSuiteEvidencePolicy(require_lookup_snapshot=True).require_approved_evidence(
                session, decision
            )
    engine.dispose()
