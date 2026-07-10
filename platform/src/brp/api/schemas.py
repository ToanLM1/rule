"""HTTP request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from brp.ir.models import DecisionContent, to_camel
from brp.repository.models import Decision, DecisionRevision, LifecycleEvent


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class DecisionCreateRequest(ApiModel):
    decision_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    content: DecisionContent
    effective_from: datetime
    effective_to: datetime | None = None


class RevisionCreateRequest(ApiModel):
    content: DecisionContent
    effective_from: datetime
    effective_to: datetime | None = None


class ReasonRequest(ApiModel):
    reason: str = Field(min_length=1)


class RevisionEnvelopeResponse(ApiModel):
    id: UUID
    decision_key: str
    revision: int
    lifecycle_status: str
    content_hash: str
    effective_from: datetime
    effective_to: datetime | None
    created_by: str
    submitted_by: str | None
    approved_by: str | None
    rejected_by: str | None
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None


class DecisionRevisionResponse(ApiModel):
    envelope: RevisionEnvelopeResponse
    content: DecisionContent

    @classmethod
    def from_record(cls, record: DecisionRevision) -> DecisionRevisionResponse:
        decision_key = record.decision.decision_key
        envelope = RevisionEnvelopeResponse(
            id=record.id,
            decision_key=decision_key,
            revision=record.revision,
            lifecycle_status=record.lifecycle_status,
            content_hash=record.content_hash,
            effective_from=record.effective_from,
            effective_to=record.effective_to,
            created_by=record.created_by,
            submitted_by=record.submitted_by,
            approved_by=record.approved_by,
            rejected_by=record.rejected_by,
            created_at=record.created_at,
            submitted_at=record.submitted_at,
            decided_at=record.decided_at,
        )
        return cls(
            envelope=envelope,
            content=DecisionContent.model_validate(record.content_blob.content),
        )


class DecisionSummaryResponse(ApiModel):
    decision_key: str
    name: str
    latest_revision: int
    latest_status: str

    @classmethod
    def from_record(cls, decision: Decision) -> DecisionSummaryResponse:
        latest = max(decision.revisions, key=lambda value: value.revision)
        return cls(
            decision_key=decision.decision_key,
            name=decision.name,
            latest_revision=latest.revision,
            latest_status=latest.lifecycle_status,
        )


class AuditEventResponse(ApiModel):
    id: int
    actor: str
    action: str
    from_status: str
    to_status: str
    reason: str | None
    content_hash: str
    correlation_id: UUID
    at: datetime

    @classmethod
    def from_record(cls, event: LifecycleEvent) -> AuditEventResponse:
        return cls.model_validate(event, from_attributes=True)


class ProblemResponse(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    extensions: dict[str, Any] = Field(default_factory=dict)
