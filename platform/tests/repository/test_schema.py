import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from brp.ir.canonical import canonical_bytes
from brp.repository.models import (
    Decision,
    DecisionContentBlob,
    DecisionRevision,
    LifecycleEvent,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


def insert_revision(session: Session) -> DecisionRevision:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    content_hash = hashlib.sha256(canonical_bytes(document)).hexdigest()
    session.merge(DecisionContentBlob(content_hash=content_hash, content=document))
    decision = Decision(
        decision_key=f"schema-{uuid4()}", name=document["decisionName"], created_by="maker-a"
    )
    revision = DecisionRevision(
        decision=decision,
        revision=1,
        content_hash=content_hash,
        lifecycle_status="DRAFT",
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        created_by="maker-a",
    )
    session.add(revision)
    session.commit()
    return revision


def test_expected_tables_exist(session: Session) -> None:
    tables = set(inspect(session.get_bind()).get_table_names())
    assert {
        "decisions",
        "decision_contents",
        "decision_revisions",
        "lifecycle_events",
        "review_queue_items",
        "golden_suites",
        "golden_suite_revisions",
        "golden_cases",
        "lookup_snapshots",
        "mode_a_publications",
    }.issubset(tables)


def test_content_blob_update_is_blocked(session: Session) -> None:
    revision = insert_revision(session)
    with pytest.raises(DBAPIError, match="BRP_IMMUTABLE_RECORD"):
        session.execute(
            text("UPDATE decision_contents SET content = '{}' WHERE content_hash = :hash"),
            {"hash": revision.content_hash},
        )
        session.commit()
    session.rollback()


@pytest.mark.parametrize("assignment", ["revision = 99", "effective_from = now()"])
def test_revision_identity_updates_are_blocked(session: Session, assignment: str) -> None:
    revision = insert_revision(session)
    with pytest.raises(DBAPIError, match="BRP_IMMUTABLE_REVISION_FIELDS"):
        session.execute(
            text(f"UPDATE decision_revisions SET {assignment} WHERE id = :id"),
            {"id": revision.id},
        )
        session.commit()
    session.rollback()


def test_status_update_without_matching_event_is_blocked(session: Session) -> None:
    revision = insert_revision(session)
    with pytest.raises(DBAPIError, match="BRP_LIFECYCLE_EVENT_REQUIRED"):
        session.execute(
            text("UPDATE decision_revisions SET lifecycle_status = 'SUBMITTED' WHERE id = :id"),
            {"id": revision.id},
        )
        session.commit()
    session.rollback()


def test_status_update_with_same_transaction_event_succeeds(session: Session) -> None:
    revision = insert_revision(session)
    session.add(
        LifecycleEvent(
            revision_id=revision.id,
            actor="maker-a",
            action="SUBMIT",
            from_status="DRAFT",
            to_status="SUBMITTED",
            content_hash=revision.content_hash,
        )
    )
    session.execute(
        text("UPDATE decision_revisions SET lifecycle_status = 'SUBMITTED' WHERE id = :id"),
        {"id": revision.id},
    )
    session.commit()
    status = session.scalar(
        select(DecisionRevision.lifecycle_status).where(DecisionRevision.id == revision.id)
    )
    assert status == "SUBMITTED"


def test_korean_content_round_trips_jsonb(session: Session) -> None:
    revision = insert_revision(session)
    content = session.scalar(
        select(DecisionContentBlob.content).where(
            DecisionContentBlob.content_hash == revision.content_hash
        )
    )
    assert content is not None
    assert content["decisionName"] == "가입 자격 판정"
