"""Maker-checker lifecycle transitions with effective interval protection."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from brp.repository.errors import (
    ApprovalEvidenceError,
    EffectiveIntervalOverlapError,
    IllegalLifecycleTransitionError,
    SelfApprovalError,
    SubmissionActorError,
)
from brp.repository.models import DecisionRevision, LifecycleEvent


class LifecycleStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class ReleaseEvidencePolicy(Protocol):
    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None: ...


class DenyMissingReleaseEvidence:
    """Safe default until T-402 wires the governed golden-suite repository."""

    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        del session, revision
        raise ApprovalEvidenceError("approved golden-suite evidence is required")


class LifecycleService:
    def __init__(self, session: Session, evidence_policy: ReleaseEvidencePolicy) -> None:
        self.session = session
        self.evidence_policy = evidence_policy

    def submit(
        self, revision: DecisionRevision, actor: str, *, correlation_id: UUID | None = None
    ) -> DecisionRevision:
        self._require_status(revision, LifecycleStatus.DRAFT)
        if actor != revision.created_by:
            raise SubmissionActorError("only the revision creator may submit in Phase 1")
        revision.submitted_by = actor
        revision.submitted_at = datetime.now(UTC)
        return self._transition(
            revision,
            LifecycleStatus.SUBMITTED,
            actor,
            action="SUBMIT",
            correlation_id=correlation_id,
        )

    def approve(
        self, revision: DecisionRevision, actor: str, *, correlation_id: UUID | None = None
    ) -> DecisionRevision:
        self._require_status(revision, LifecycleStatus.SUBMITTED)
        if actor in {revision.created_by, revision.submitted_by}:
            raise SelfApprovalError("approver must differ from creator and submitter")
        self.evidence_policy.require_approved_evidence(self.session, revision)
        self._require_no_approved_overlap(revision)
        revision.approved_by = actor
        revision.decided_at = datetime.now(UTC)
        return self._transition(
            revision,
            LifecycleStatus.APPROVED,
            actor,
            action="APPROVE",
            correlation_id=correlation_id,
        )

    def reject(
        self,
        revision: DecisionRevision,
        actor: str,
        *,
        reason: str,
        correlation_id: UUID | None = None,
    ) -> DecisionRevision:
        self._require_status(revision, LifecycleStatus.SUBMITTED)
        if actor in {revision.created_by, revision.submitted_by}:
            raise SelfApprovalError("rejector must differ from creator and submitter")
        if not reason.strip():
            raise ValueError("rejection reason is required")
        revision.rejected_by = actor
        revision.decided_at = datetime.now(UTC)
        return self._transition(
            revision,
            LifecycleStatus.REJECTED,
            actor,
            action="REJECT",
            reason=reason,
            correlation_id=correlation_id,
        )

    def retire(
        self,
        revision: DecisionRevision,
        actor: str,
        *,
        reason: str,
        correlation_id: UUID | None = None,
    ) -> DecisionRevision:
        self._require_status(revision, LifecycleStatus.APPROVED)
        if not reason.strip():
            raise ValueError("retirement reason is required")
        return self._transition(
            revision,
            LifecycleStatus.RETIRED,
            actor,
            action="RETIRE",
            reason=reason,
            correlation_id=correlation_id,
        )

    def _transition(
        self,
        revision: DecisionRevision,
        to_status: LifecycleStatus,
        actor: str,
        *,
        action: str,
        reason: str | None = None,
        correlation_id: UUID | None = None,
    ) -> DecisionRevision:
        from_status = revision.lifecycle_status
        self.session.add(
            LifecycleEvent(
                revision_id=revision.id,
                actor=actor,
                action=action,
                from_status=from_status,
                to_status=to_status,
                reason=reason,
                content_hash=revision.content_hash,
                correlation_id=correlation_id or uuid4(),
            )
        )
        revision.lifecycle_status = to_status
        self.session.flush()
        return revision

    @staticmethod
    def _require_status(revision: DecisionRevision, expected: LifecycleStatus) -> None:
        if revision.lifecycle_status != expected:
            raise IllegalLifecycleTransitionError(
                f"expected {expected}, got {revision.lifecycle_status}"
            )

    def _require_no_approved_overlap(self, revision: DecisionRevision) -> None:
        query = select(DecisionRevision.id).where(
            DecisionRevision.decision_id == revision.decision_id,
            DecisionRevision.id != revision.id,
            DecisionRevision.lifecycle_status == LifecycleStatus.APPROVED,
            or_(
                DecisionRevision.effective_to.is_(None),
                DecisionRevision.effective_to > revision.effective_from,
            ),
        )
        if revision.effective_to is not None:
            query = query.where(DecisionRevision.effective_from < revision.effective_to)
        if self.session.scalar(query.limit(1)) is not None:
            raise EffectiveIntervalOverlapError(
                "approved effective interval overlaps another approved revision"
            )
