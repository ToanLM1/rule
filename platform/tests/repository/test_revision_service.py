import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from brp.db import create_database_engine
from brp.ir.models import DecisionContent
from brp.repository.errors import ApprovedRevisionNotFoundError
from brp.repository.models import DecisionContentBlob, DecisionRevision, LifecycleEvent
from brp.repository.service import RevisionRepository

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


def content() -> DecisionContent:
    return DecisionContent.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def unique_key() -> str:
    return f"revision-{uuid4()}"


def create(repository: RevisionRepository, key: str, actor: str = "maker-a") -> DecisionRevision:
    return repository.create_decision(
        key,
        content(),
        actor,
        datetime(2026, 8, 1, tzinfo=UTC),
    )


def raw_transition(session: Session, revision: DecisionRevision, to_status: str) -> None:
    session.add(
        LifecycleEvent(
            revision_id=revision.id,
            actor="checker-b",
            action=to_status,
            from_status=revision.lifecycle_status,
            to_status=to_status,
            content_hash=revision.content_hash,
        )
    )
    session.execute(
        text("UPDATE decision_revisions SET lifecycle_status = :status WHERE id = :id"),
        {"status": to_status, "id": revision.id},
    )
    session.commit()
    session.refresh(revision)


def test_create_assigns_revision_and_content_hash(session: Session) -> None:
    repository = RevisionRepository(session)
    revision = create(repository, unique_key())
    session.commit()
    assert revision.revision == 1
    assert len(revision.content_hash) == 64
    assert revision.lifecycle_status == "DRAFT"
    assert (
        repository.get_revision(revision.decision.decision_key, 1).content_blob.content[
            "decisionName"
        ]
        == "가입 자격 판정"
    )


def test_content_blobs_are_deduplicated(session: Session) -> None:
    repository = RevisionRepository(session)
    unique_content = content().model_copy(update={"decision_name": f"중복-{uuid4()}"})
    before = session.scalar(select(func.count()).select_from(DecisionContentBlob))
    for _ in range(2):
        repository.create_decision(
            unique_key(),
            unique_content,
            "maker-a",
            datetime(2026, 8, 1, tzinfo=UTC),
        )
    session.commit()
    after = session.scalar(select(func.count()).select_from(DecisionContentBlob))
    assert before is not None and after == before + 1


def test_add_revision_is_server_numbered(session: Session) -> None:
    key = unique_key()
    repository = RevisionRepository(session)
    create(repository, key)
    session.commit()
    second = repository.add_revision(key, content(), "maker-a", datetime(2026, 9, 1, tzinfo=UTC))
    session.commit()
    assert second.revision == 2


def test_list_and_get_decision(session: Session) -> None:
    key = unique_key()
    repository = RevisionRepository(session)
    create(repository, key)
    session.commit()
    assert repository.get_decision(key).decision_key == key
    assert key in {decision.decision_key for decision in repository.list_decisions()}


def test_resolve_approved_by_as_of(session: Session) -> None:
    key = unique_key()
    repository = RevisionRepository(session)
    revision = repository.create_decision(
        key,
        content(),
        "maker-a",
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC),
    )
    session.commit()
    raw_transition(session, revision, "APPROVED")
    resolved = repository.resolve_approved(key, as_of=datetime(2026, 8, 15, tzinfo=UTC))
    assert resolved.id == revision.id
    with pytest.raises(ApprovedRevisionNotFoundError):
        repository.resolve_approved(key, as_of=datetime(2026, 9, 1, tzinfo=UTC))


def test_explicit_resolution_rejects_draft(session: Session) -> None:
    key = unique_key()
    repository = RevisionRepository(session)
    revision = create(repository, key)
    session.commit()
    with pytest.raises(ApprovedRevisionNotFoundError):
        repository.resolve_approved(key, revision=revision.revision)


def test_concurrent_revision_creation_gets_unique_numbers(session: Session) -> None:
    key = unique_key()
    repository = RevisionRepository(session)
    create(repository, key)
    session.commit()
    barrier = threading.Barrier(2)

    def add() -> int:
        engine = create_database_engine()
        try:
            with Session(engine) as worker_session:
                barrier.wait(timeout=10)
                record = RevisionRepository(worker_session).add_revision(
                    key,
                    content(),
                    "maker-a",
                    datetime(2026, 9, 1, tzinfo=UTC),
                )
                worker_session.commit()
                return record.revision
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        numbers = sorted(executor.map(lambda _: add(), range(2)))
    assert numbers == [2, 3]
