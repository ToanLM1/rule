from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from brp.db import create_database_engine
from brp.repository.errors import IllegalReviewDispositionError
from brp.repository.review_queue import (
    BatchReviewDisposition,
    ReviewQueueService,
    ReviewStatus,
)

PLATFORM = Path(__file__).resolve().parents[2]


def add(service: ReviewQueueService, suffix: str):
    return service.add(
        adapter="code-java",
        source_snapshot_hash=suffix * 64,
        raw_fragment=f"unsupported_{suffix}()",
        provenance={"file": "Synthetic.java", "line": 1},
        reason_code="UNSUPPORTED_CALL",
        actor="miner",
    )


def test_batch_review_is_atomic_when_any_item_is_invalid() -> None:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    with Session(engine) as session:
        service = ReviewQueueService(session)
        terminal = add(service, "a")
        open_item = add(service, "b")
        service.dispose(
            terminal.id,
            status=ReviewStatus.REJECTED,
            actor="reviewer",
            reason="known unsupported construct",
        )
        session.commit()
        with pytest.raises(IllegalReviewDispositionError, match="already REJECTED"):
            service.dispose_batch(
                [
                    BatchReviewDisposition(terminal.id, ReviewStatus.ACCEPTED, "reconsider"),
                    BatchReviewDisposition(open_item.id, ReviewStatus.ACCEPTED, "map manually"),
                ],
                actor="reviewer-2",
            )
        session.refresh(open_item)
        assert open_item.status == "OPEN"
        assert len(open_item.disposition_history) == 1
    engine.dispose()


def test_successful_batch_uses_one_auditable_correlation() -> None:
    engine = create_database_engine()
    with Session(engine) as session:
        service = ReviewQueueService(session)
        first = add(service, "c")
        second = add(service, "d")
        correlation = uuid4()
        records = service.dispose_batch(
            [
                BatchReviewDisposition(first.id, ReviewStatus.ACCEPTED, "mapped"),
                BatchReviewDisposition(second.id, ReviewStatus.DEFERRED, "needs SME"),
            ],
            actor="reviewer",
            correlation_id=correlation,
        )
        session.commit()
        assert [item.status for item in records] == ["ACCEPTED", "DEFERRED"]
        assert {item.disposition_history[-1]["correlationId"] for item in records} == {
            str(correlation)
        }
    engine.dispose()
