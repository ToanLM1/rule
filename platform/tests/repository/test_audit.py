from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from brp.ir.models import DecisionContent
from brp.repository.lifecycle import LifecycleService
from brp.repository.models import LifecycleEvent
from brp.repository.service import RevisionRepository

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


class Evidence:
    def require_approved_evidence(self, session: Session, revision: object) -> None:
        del session, revision


def content() -> DecisionContent:
    return DecisionContent.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_revision_creation_and_transitions_are_fully_audited(session: Session) -> None:
    key = f"audit-{uuid4()}"
    repository = RevisionRepository(session)
    revision = repository.create_decision(
        key,
        content(),
        "maker-a",
        datetime(2026, 8, 1, tzinfo=UTC),
    )
    session.commit()
    correlation = uuid4()
    lifecycle = LifecycleService(session, Evidence())
    lifecycle.submit(revision, "maker-a", correlation_id=correlation)
    session.commit()

    events = repository.get_audit(key)
    assert [event.action for event in events] == ["CREATE_REVISION", "SUBMIT"]
    assert events[0].actor == "maker-a"
    assert events[0].content_hash == revision.content_hash
    assert events[1].correlation_id == correlation
    assert events[1].from_status == "DRAFT"
    assert events[1].to_status == "SUBMITTED"


def test_rejection_reason_preserves_korean(session: Session) -> None:
    key = f"audit-reject-{uuid4()}"
    repository = RevisionRepository(session)
    revision = repository.create_decision(
        key, content(), "maker-a", datetime(2026, 8, 1, tzinfo=UTC)
    )
    session.commit()
    lifecycle = LifecycleService(session, Evidence())
    lifecycle.submit(revision, "maker-a")
    session.commit()
    lifecycle.reject(revision, "checker-b", reason="근거 문서 부족")
    session.commit()
    assert repository.get_audit(key)[-1].reason == "근거 문서 부족"


def test_audit_events_are_immutable(session: Session) -> None:
    key = f"audit-immutable-{uuid4()}"
    repository = RevisionRepository(session)
    repository.create_decision(key, content(), "maker-a", datetime(2026, 8, 1, tzinfo=UTC))
    session.commit()
    event = repository.get_audit(key)[0]
    with pytest.raises(DBAPIError, match="BRP_IMMUTABLE_RECORD"):
        session.execute(
            text("UPDATE lifecycle_events SET actor = 'tampered' WHERE id = :id"),
            {"id": event.id},
        )
        session.commit()
    session.rollback()


def test_correlation_ids_are_uuid_values() -> None:
    event = LifecycleEvent(correlation_id=uuid4())
    assert isinstance(event.correlation_id, UUID)
