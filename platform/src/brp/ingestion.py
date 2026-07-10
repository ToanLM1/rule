"""Transactional, idempotent extraction-batch ingestion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from brp.adapters.contracts import ExtractionBatch, UnmappableItem
from brp.ir.canonical import canonical_bytes
from brp.repository.errors import DecisionNotFoundError
from brp.repository.models import IngestionFingerprint
from brp.repository.review_queue import ReviewQueueService
from brp.repository.service import RevisionRepository


@dataclass
class IngestionResult:
    inserted_revisions: list[tuple[str, int]] = field(default_factory=list)
    review_items: int = 0
    skipped: int = 0


class IngestionRunner:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ingest(
        self,
        batches: list[ExtractionBatch],
        *,
        actor: str,
        effective_from: datetime | None = None,
    ) -> IngestionResult:
        effective = effective_from or datetime.now(UTC)
        repository = RevisionRepository(self.session)
        queue = ReviewQueueService(self.session)
        result = IngestionResult()
        for batch in batches:
            for candidate in batch.decisions:
                candidate_hash = hashlib.sha256(canonical_bytes(candidate.content)).hexdigest()
                fingerprint = _fingerprint(batch, candidate_hash)
                if self._exists(fingerprint):
                    result.skipped += 1
                    continue
                try:
                    repository.get_decision(candidate.decision_key)
                except DecisionNotFoundError:
                    revision = repository.create_decision(
                        candidate.decision_key, candidate.content, actor, effective
                    )
                else:
                    revision = repository.add_revision(
                        candidate.decision_key, candidate.content, actor, effective
                    )
                self._record(
                    batch,
                    fingerprint,
                    candidate_hash,
                    decision_key=candidate.decision_key,
                    revision_id=revision.id,
                )
                result.inserted_revisions.append((candidate.decision_key, revision.revision))
            for item in batch.unmappable:
                candidate_hash = _unmappable_hash(item)
                fingerprint = _fingerprint(batch, candidate_hash)
                if self._exists(fingerprint):
                    result.skipped += 1
                    continue
                queue.add(
                    adapter=batch.adapter,
                    source_snapshot_hash=batch.source_snapshot.content_hash,
                    raw_fragment=item.raw_fragment,
                    provenance=item.provenance,
                    reason_code=item.reason_code,
                    actor=actor,
                )
                self._record(batch, fingerprint, candidate_hash)
                result.review_items += 1
        self.session.commit()
        return result

    def _exists(self, fingerprint: str) -> bool:
        return (
            self.session.scalar(
                select(IngestionFingerprint.id).where(
                    IngestionFingerprint.fingerprint == fingerprint
                )
            )
            is not None
        )

    def _record(
        self,
        batch: ExtractionBatch,
        fingerprint: str,
        candidate_hash: str,
        *,
        decision_key: str | None = None,
        revision_id: object | None = None,
    ) -> None:
        self.session.add(
            IngestionFingerprint(
                fingerprint=fingerprint,
                adapter=batch.adapter,
                capability_version=batch.capability_version,
                source_snapshot_hash=batch.source_snapshot.content_hash,
                candidate_hash=candidate_hash,
                decision_key=decision_key,
                revision_id=revision_id,
            )
        )
        self.session.flush()


def _fingerprint(batch: ExtractionBatch, candidate_hash: str) -> str:
    value = "\0".join(
        (
            batch.source_snapshot.content_hash,
            batch.capability_version,
            candidate_hash,
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unmappable_hash(item: UnmappableItem) -> str:
    document = item.model_dump(mode="json", by_alias=True)
    rendered = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()
