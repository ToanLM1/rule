"""Transactional revision repository over immutable canonical content."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from brp.ir.canonical import canonical_bytes
from brp.ir.models import DecisionContent
from brp.repository.errors import (
    AmbiguousEffectiveRevisionError,
    ApprovedRevisionNotFoundError,
    DecisionNotFoundError,
    InvalidEffectiveIntervalError,
    RevisionNotFoundError,
)
from brp.repository.models import (
    Decision,
    DecisionContentBlob,
    DecisionRevision,
    LifecycleEvent,
)


class RevisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_decision(
        self,
        decision_key: str,
        content: DecisionContent,
        actor: str,
        effective_from: datetime,
        effective_to: datetime | None = None,
    ) -> DecisionRevision:
        self._validate_interval(effective_from, effective_to)
        content_hash, document = self._store_content(content)
        decision = Decision(
            decision_key=decision_key,
            name=content.decision_name,
            created_by=actor,
        )
        revision = DecisionRevision(
            decision=decision,
            revision=1,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor,
        )
        self.session.add_all((decision, revision))
        self.session.flush()
        self._record_creation(revision, actor)
        content_blob = self.session.get(DecisionContentBlob, content_hash)
        assert content_blob is not None and content_blob.content == document
        revision.content_blob = content_blob
        return revision

    def add_revision(
        self,
        decision_key: str,
        content: DecisionContent,
        actor: str,
        effective_from: datetime,
        effective_to: datetime | None = None,
    ) -> DecisionRevision:
        self._validate_interval(effective_from, effective_to)
        decision = self.session.scalar(
            select(Decision).where(Decision.decision_key == decision_key).with_for_update()
        )
        if decision is None:
            raise DecisionNotFoundError(decision_key)
        latest = self.session.scalar(
            select(func.max(DecisionRevision.revision)).where(
                DecisionRevision.decision_id == decision.id
            )
        )
        content_hash, _ = self._store_content(content)
        revision = DecisionRevision(
            decision_id=decision.id,
            revision=(latest or 0) + 1,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor,
        )
        self.session.add(revision)
        self.session.flush()
        self._record_creation(revision, actor)
        return revision

    def get_decision(self, decision_key: str) -> Decision:
        result = self.session.execute(
            select(Decision)
            .options(joinedload(Decision.revisions))
            .where(Decision.decision_key == decision_key)
        )
        decision = result.unique().scalar_one_or_none()
        if decision is None:
            raise DecisionNotFoundError(decision_key)
        return decision

    def get_revision(self, decision_key: str, revision: int) -> DecisionRevision:
        record = self.session.scalar(
            self._revision_query(decision_key).where(DecisionRevision.revision == revision)
        )
        if record is None:
            raise RevisionNotFoundError(f"{decision_key}@{revision}")
        return record

    def list_decisions(self) -> list[Decision]:
        return list(self.session.scalars(select(Decision).order_by(Decision.decision_key)))

    def get_audit(self, decision_key: str) -> list[LifecycleEvent]:
        return list(
            self.session.scalars(
                select(LifecycleEvent)
                .join(DecisionRevision)
                .join(Decision)
                .where(Decision.decision_key == decision_key)
                .order_by(LifecycleEvent.id)
            )
        )

    def resolve_approved(
        self,
        decision_key: str,
        *,
        revision: int | None = None,
        as_of: datetime | None = None,
    ) -> DecisionRevision:
        query = self._revision_query(decision_key).where(
            DecisionRevision.lifecycle_status == "APPROVED"
        )
        if revision is not None:
            record = self.session.scalar(query.where(DecisionRevision.revision == revision))
            if record is None:
                raise ApprovedRevisionNotFoundError(f"{decision_key}@{revision}")
            return record

        timestamp = as_of or datetime.now(UTC)
        effective = and_(
            DecisionRevision.effective_from <= timestamp,
            or_(
                DecisionRevision.effective_to.is_(None),
                DecisionRevision.effective_to > timestamp,
            ),
        )
        records = list(
            self.session.scalars(query.where(effective).order_by(DecisionRevision.revision))
        )
        if not records:
            raise ApprovedRevisionNotFoundError(f"{decision_key} at {timestamp.isoformat()}")
        if len(records) > 1:
            raise AmbiguousEffectiveRevisionError(
                f"{decision_key} has {len(records)} approved revisions at {timestamp.isoformat()}"
            )
        return records[0]

    def _revision_query(self, decision_key: str) -> Select[tuple[DecisionRevision]]:
        return (
            select(DecisionRevision)
            .join(Decision)
            .options(joinedload(DecisionRevision.content_blob))
            .where(Decision.decision_key == decision_key)
        )

    def _store_content(self, content: DecisionContent) -> tuple[str, dict[str, object]]:
        rendered = canonical_bytes(content)
        content_hash = hashlib.sha256(rendered).hexdigest()
        document = content.model_dump(mode="json", by_alias=True, exclude_none=True)
        if self.session.get(DecisionContentBlob, content_hash) is None:
            self.session.add(DecisionContentBlob(content_hash=content_hash, content=document))
            self.session.flush()
        return content_hash, document

    def _record_creation(
        self, revision: DecisionRevision, actor: str, correlation_id: UUID | None = None
    ) -> None:
        self.session.add(
            LifecycleEvent(
                revision_id=revision.id,
                actor=actor,
                action="CREATE_REVISION",
                from_status="DRAFT",
                to_status="DRAFT",
                content_hash=revision.content_hash,
                correlation_id=correlation_id or uuid4(),
            )
        )
        self.session.flush()

    @staticmethod
    def _validate_interval(effective_from: datetime, effective_to: datetime | None) -> None:
        if effective_from.tzinfo is None:
            raise InvalidEffectiveIntervalError("effective_from must be timezone-aware")
        if effective_to is not None:
            if effective_to.tzinfo is None:
                raise InvalidEffectiveIntervalError("effective_to must be timezone-aware")
            if effective_to <= effective_from:
                raise InvalidEffectiveIntervalError("effective_to must be after effective_from")
