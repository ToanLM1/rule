from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from brp.repository.errors import (
    IllegalReviewDispositionError,
    ReviewQueueItemNotFoundError,
)
from brp.repository.review_queue import ReviewQueueService, ReviewStatus


def test_add_and_dispose_unmappable_fragment(session: Session) -> None:
    service = ReviewQueueService(session)
    correlation = uuid4()
    item = service.add(
        adapter="code-java",
        source_snapshot_hash="a" * 64,
        raw_fragment='notifyExternalSystem("가입 거절")',
        provenance={"file": "EnrollmentValidator.java", "lines": [70, 71]},
        reason_code="SIDE_EFFECT",
        actor="miner",
        correlation_id=correlation,
    )
    session.commit()
    assert item.status == "OPEN"
    assert item.disposition_history[0]["correlationId"] == str(correlation)
    assert item in service.list_open()

    service.dispose(
        item.id,
        status=ReviewStatus.REJECTED,
        actor="reviewer-b",
        reason="restricted profile excludes external calls",
    )
    session.commit()
    assert item.status == "REJECTED"
    assert len(item.disposition_history) == 2
    assert item not in service.list_open()


def test_disposition_requires_reason_and_terminal_items_are_closed(session: Session) -> None:
    service = ReviewQueueService(session)
    item = service.add(
        adapter="code-java",
        source_snapshot_hash="b" * 64,
        raw_fragment="call()",
        provenance={"file": "Legacy.java", "lines": [1, 1]},
        reason_code="CALL",
        actor="miner",
    )
    with pytest.raises(ValueError, match="reason"):
        service.dispose(item.id, status=ReviewStatus.DEFERRED, actor="reviewer", reason="")
    service.dispose(
        item.id,
        status=ReviewStatus.ACCEPTED,
        actor="reviewer",
        reason="handled outside IR",
    )
    with pytest.raises(IllegalReviewDispositionError):
        service.dispose(
            item.id,
            status=ReviewStatus.REJECTED,
            actor="reviewer",
            reason="second decision",
        )


def test_missing_item_raises_typed_error(session: Session) -> None:
    with pytest.raises(ReviewQueueItemNotFoundError):
        ReviewQueueService(session).get(uuid4())
