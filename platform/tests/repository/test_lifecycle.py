from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brp.ir.models import DecisionContent
from brp.repository.errors import (
    ApprovalEvidenceError,
    EffectiveIntervalOverlapError,
    IllegalLifecycleTransitionError,
    SelfApprovalError,
    SubmissionActorError,
)
from brp.repository.lifecycle import LifecycleService
from brp.repository.models import DecisionRevision, LifecycleEvent
from brp.repository.service import RevisionRepository

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


class EvidencePolicy:
    def __init__(self, approved: bool = True) -> None:
        self.approved = approved

    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        del session, revision
        if not self.approved:
            raise ApprovalEvidenceError("missing suite")


def content() -> DecisionContent:
    return DecisionContent.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def draft(
    session: Session,
    *,
    key: str | None = None,
    effective_from: datetime = datetime(2026, 8, 1, tzinfo=UTC),
    effective_to: datetime | None = None,
) -> DecisionRevision:
    repository = RevisionRepository(session)
    record = repository.create_decision(
        key or f"lifecycle-{uuid4()}",
        content(),
        "maker-a",
        effective_from,
        effective_to,
    )
    session.commit()
    return record


def service(session: Session, *, evidence: bool = True) -> LifecycleService:
    return LifecycleService(session, EvidencePolicy(evidence))


def submit(session: Session, revision: DecisionRevision) -> LifecycleService:
    lifecycle = service(session)
    lifecycle.submit(revision, "maker-a")
    session.commit()
    return lifecycle


def approve(session: Session, revision: DecisionRevision) -> None:
    service(session).approve(revision, "checker-b")
    session.commit()


def test_submit_requires_creator(session: Session) -> None:
    revision = draft(session)
    with pytest.raises(SubmissionActorError):
        service(session).submit(revision, "other-maker")
    assert revision.lifecycle_status == "DRAFT"


def test_submit_records_actor_event_and_projection(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    assert revision.lifecycle_status == "SUBMITTED"
    assert revision.submitted_by == "maker-a"
    event = session.scalar(select(LifecycleEvent).where(LifecycleEvent.revision_id == revision.id))
    assert event is not None and event.action == "SUBMIT"


def test_creator_and_submitter_cannot_approve(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    with pytest.raises(SelfApprovalError):
        service(session).approve(revision, "maker-a")


def test_checker_approves_with_evidence(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    approve(session, revision)
    assert revision.lifecycle_status == "APPROVED"
    assert revision.approved_by == "checker-b"
    assert revision.decided_at is not None


def test_approval_requires_release_evidence(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    with pytest.raises(ApprovalEvidenceError):
        service(session, evidence=False).approve(revision, "checker-b")


def test_reject_requires_checker_and_reason(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    with pytest.raises(ValueError, match="reason"):
        service(session).reject(revision, "checker-b", reason=" ")
    service(session).reject(revision, "checker-b", reason="근거 부족")
    session.commit()
    assert revision.lifecycle_status == "REJECTED"


def test_retire_requires_approved_revision_and_reason(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    approve(session, revision)
    with pytest.raises(ValueError, match="reason"):
        service(session).retire(revision, "checker-c", reason="")
    service(session).retire(revision, "checker-c", reason="상품 종료")
    session.commit()
    assert revision.lifecycle_status == "RETIRED"


def test_illegal_transition_is_rejected(session: Session) -> None:
    revision = draft(session)
    with pytest.raises(IllegalLifecycleTransitionError):
        service(session).approve(revision, "checker-b")


def test_overlapping_approved_intervals_are_rejected(session: Session) -> None:
    key = f"overlap-{uuid4()}"
    first = draft(
        session,
        key=key,
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        effective_to=datetime(2026, 10, 1, tzinfo=UTC),
    )
    submit(session, first)
    approve(session, first)

    second = RevisionRepository(session).add_revision(
        key,
        content(),
        "maker-a",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 11, 1, tzinfo=UTC),
    )
    session.commit()
    submit(session, second)
    with pytest.raises(EffectiveIntervalOverlapError):
        service(session).approve(second, "checker-b")


def test_each_successful_transition_has_one_event(session: Session) -> None:
    revision = draft(session)
    submit(session, revision)
    approve(session, revision)
    count = session.scalar(
        select(func.count())
        .select_from(LifecycleEvent)
        .where(LifecycleEvent.revision_id == revision.id)
    )
    assert count == 2
