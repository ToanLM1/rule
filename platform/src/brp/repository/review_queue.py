"""Persistent review queue for source fragments outside the restricted IR profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from brp.repository.errors import (
    IllegalReviewDispositionError,
    ReviewQueueItemNotFoundError,
)
from brp.repository.models import DEFAULT_SITE_ID, ReviewQueueItem


class ReviewStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class BatchReviewDisposition:
    item_id: UUID
    status: ReviewStatus
    reason: str


class ReviewQueueService:
    def __init__(self, session: Session, *, site_id: UUID = DEFAULT_SITE_ID) -> None:
        self.session = session
        self.site_id = site_id

    def add(
        self,
        *,
        adapter: str,
        source_snapshot_hash: str,
        raw_fragment: str,
        provenance: dict[str, Any],
        reason_code: str,
        actor: str,
        correlation_id: UUID | None = None,
        import_run_id: UUID | None = None,
    ) -> ReviewQueueItem:
        correlation = correlation_id or uuid4()
        item = ReviewQueueItem(
            site_id=self.site_id,
            import_run_id=import_run_id,
            adapter=adapter,
            source_snapshot_hash=source_snapshot_hash,
            raw_fragment=raw_fragment,
            provenance=provenance,
            reason_code=reason_code,
            status=ReviewStatus.OPEN,
            disposition_history=[
                self._history("OPEN", actor, "candidate requires review", correlation)
            ],
        )
        self.session.add(item)
        self.session.flush()
        return item

    def dispose(
        self,
        item_id: UUID,
        *,
        status: ReviewStatus,
        actor: str,
        reason: str,
        correlation_id: UUID | None = None,
    ) -> ReviewQueueItem:
        item = self.get(item_id)
        if item.status not in {ReviewStatus.OPEN, ReviewStatus.DEFERRED}:
            raise IllegalReviewDispositionError(f"item is already {item.status}")
        if status is ReviewStatus.OPEN:
            raise IllegalReviewDispositionError("disposition cannot return an item to OPEN")
        if not reason.strip():
            raise ValueError("disposition reason is required")
        item.status = status
        item.disposition_history = [
            *item.disposition_history,
            self._history(status, actor, reason, correlation_id or uuid4()),
        ]
        self.session.flush()
        return item

    def dispose_batch(
        self,
        dispositions: list[BatchReviewDisposition],
        *,
        actor: str,
        correlation_id: UUID | None = None,
    ) -> list[ReviewQueueItem]:
        if not dispositions:
            raise ValueError("batch dispositions are required")
        identifiers = [item.item_id for item in dispositions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("batch item IDs must be unique")
        records = list(
            self.session.scalars(
                select(ReviewQueueItem)
                .where(
                    ReviewQueueItem.site_id == self.site_id,
                    ReviewQueueItem.id.in_(identifiers),
                )
                .order_by(ReviewQueueItem.id)
                .with_for_update()
            )
        )
        by_id = {item.id: item for item in records}
        missing = [item_id for item_id in identifiers if item_id not in by_id]
        if missing:
            raise ReviewQueueItemNotFoundError(str(missing[0]))
        for disposition in dispositions:
            record = by_id[disposition.item_id]
            if record.status not in {ReviewStatus.OPEN, ReviewStatus.DEFERRED}:
                raise IllegalReviewDispositionError(f"item is already {record.status}")
            if disposition.status is ReviewStatus.OPEN:
                raise IllegalReviewDispositionError("disposition cannot return an item to OPEN")
            if not disposition.reason.strip():
                raise ValueError("disposition reason is required")
        correlation = correlation_id or uuid4()
        for disposition in dispositions:
            record = by_id[disposition.item_id]
            record.status = disposition.status
            record.disposition_history = [
                *record.disposition_history,
                self._history(disposition.status, actor, disposition.reason, correlation),
            ]
        self.session.flush()
        return [by_id[item_id] for item_id in identifiers]

    def get(self, item_id: UUID) -> ReviewQueueItem:
        item = self.session.scalar(
            select(ReviewQueueItem).where(
                ReviewQueueItem.site_id == self.site_id,
                ReviewQueueItem.id == item_id,
            )
        )
        if item is None:
            raise ReviewQueueItemNotFoundError(str(item_id))
        return item

    def list_open(self) -> list[ReviewQueueItem]:
        return list(
            self.session.scalars(
                select(ReviewQueueItem)
                .where(
                    ReviewQueueItem.site_id == self.site_id,
                    ReviewQueueItem.status.in_([ReviewStatus.OPEN, ReviewStatus.DEFERRED]),
                )
                .order_by(ReviewQueueItem.created_at, ReviewQueueItem.id)
            )
        )

    @staticmethod
    def _history(action: str, actor: str, reason: str, correlation_id: UUID) -> dict[str, str]:
        return {
            "action": action,
            "actor": actor,
            "reason": reason,
            "correlationId": str(correlation_id),
            "at": datetime.now(UTC).isoformat(),
        }
