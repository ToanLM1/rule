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
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.ir.models import DecisionContent
from brp.mode_a import ModeAService
from brp.repository.errors import DecisionNotFoundError, ModeAPublicationError
from brp.repository.lifecycle import LifecycleService
from brp.repository.service import RevisionRepository

PLATFORM = Path(__file__).resolve().parents[2]
FIXTURE = PLATFORM / "tests/fixtures/conformance/enrollment_eligibility.json"
NOW = datetime(2026, 8, 15, tzinfo=UTC)


def content(key: str) -> DecisionContent:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["decisionId"] = key
    return DecisionContent.model_validate(document)


def golden_case(*, expected_reason: str = "UNDER_AGE") -> GoldenCaseData:
    return GoldenCaseData(
        case_key="미성년-서울",
        input={"age": 17, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
        expected={"eligible": False, "reasonCode": expected_reason},
        provenance={"type": "SYNTHETIC", "label": "서울 가입 경계"},
    )


def prepare(
    session: Session,
    *,
    effective_from: datetime = datetime(2026, 8, 1, tzinfo=UTC),
    expected_reason: str = "UNDER_AGE",
    approve_decision: bool = True,
) -> tuple[str, int, int, str]:
    key = f"mode_a_{uuid4().hex}"
    decision = RevisionRepository(session).create_decision(
        key, content(key), "maker", effective_from
    )
    golden = GoldenRepository(session)
    snapshot = golden.snapshot_lookup(
        "지역 자격",
        [{"region_code": "SEOUL", "eligible": True, "name": "서울"}],
        {"ref": "lookup://region_eligibility", "source": "한국 지역 기준"},
        approved=True,
    )
    suite = golden.create_revision(
        key,
        [golden_case(expected_reason=expected_reason)],
        "maker",
        lookup_snapshot_hashes=[snapshot.content_hash],
    )
    golden.submit(suite, "maker")
    golden.approve(suite, "checker")
    if approve_decision:
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        lifecycle.submit(decision, "maker")
        lifecycle.approve(decision, "checker")
    return key, decision.revision, suite.revision, snapshot.content_hash


@pytest.fixture(scope="module", autouse=True)
def migrate() -> None:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")


@pytest.fixture
def session() -> Session:
    engine = create_database_engine()
    with Session(engine) as database_session:
        yield database_session
        database_session.rollback()
    engine.dispose()


def test_publish_execute_audit_korean_snapshot_and_immutable_history(
    session: Session,
) -> None:
    key, revision, suite, snapshot_hash = prepare(session)
    service = ModeAService(session)
    publication = service.publish(key, revision, suite, "deployer", as_of=NOW)
    session.commit()

    execution = service.execute(
        key, {"age": 17, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"}
    )
    assert execution == {
        "executor": "ZEN",
        "authority": "AUTHORITATIVE",
        "publicationId": publication.id,
        "decisionRevision": 1,
        "result": {"eligible": False, "reasonCode": "UNDER_AGE"},
    }
    assert publication.lookup_snapshot_hashes == [snapshot_hash]
    assert publication.validation_result["authority"] == "AUTHORITATIVE"
    assert [item.action for item in service.history(key)] == ["PUBLISH"]
    with pytest.raises(ProgrammingError, match="BRP_IMMUTABLE_RECORD"):
        session.execute(
            text("UPDATE mode_a_publications SET actor = 'other' WHERE id = :id"),
            {"id": publication.id},
        )
        session.flush()
    session.rollback()


def test_publish_denies_draft_ineffective_missing_suite_and_failed_golden(
    session: Session,
) -> None:
    draft_key, revision, suite, _ = prepare(session, approve_decision=False)
    with pytest.raises(ModeAPublicationError, match="approved decision"):
        ModeAService(session).publish(draft_key, revision, suite, "deployer", as_of=NOW)

    future_key, revision, suite, _ = prepare(
        session, effective_from=datetime(2026, 9, 1, tzinfo=UTC)
    )
    with pytest.raises(ModeAPublicationError, match="effective decision"):
        ModeAService(session).publish(future_key, revision, suite, "deployer", as_of=NOW)

    with pytest.raises(DecisionNotFoundError, match="golden suite"):
        ModeAService(session).publish(future_key, revision, 999, "deployer", as_of=NOW)

    failed_key, revision, suite, _ = prepare(session, expected_reason="WRONG")
    with pytest.raises(ModeAPublicationError, match="golden validation failed"):
        ModeAService(session).publish(failed_key, revision, suite, "deployer", as_of=NOW)


def test_rollback_appends_and_reactivates_previously_validated_release(
    session: Session,
) -> None:
    key, revision, suite, _ = prepare(session)
    golden = GoldenRepository(session)
    second_suite = golden.create_revision(
        key,
        [golden_case()],
        "maker-2",
        lookup_snapshot_hashes=[golden.get_revision(key, suite).lookup_snapshot_hashes[0]],
    )
    golden.submit(second_suite, "maker-2")
    golden.approve(second_suite, "checker-2")
    service = ModeAService(session)
    first = service.publish(key, revision, suite, "deployer", as_of=NOW)
    second = service.publish(key, revision, second_suite.revision, "deployer", as_of=NOW)
    rollback = service.rollback(key, first.id, "incident-manager")
    session.commit()

    assert rollback.action == "ROLLBACK"
    assert rollback.previous_publication_id == second.id
    assert rollback.source_publication_id == first.id
    assert service.active(key).id == rollback.id
    assert [item.action for item in service.history(key)] == [
        "PUBLISH",
        "PUBLISH",
        "ROLLBACK",
    ]
