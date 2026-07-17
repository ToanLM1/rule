from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from brp.jobs import JobService
from brp.repository.models import DEFAULT_SITE_ID


def test_job_lease_heartbeat_success_and_cancellation(session: Session) -> None:
    service = JobService(session)
    queued = service.enqueue(
        site_id=DEFAULT_SITE_ID,
        job_type="TEST",
        payload={"value": 1},
        actor="maker-a",
    )
    queued.created_at = datetime(2000, 1, 1, tzinfo=UTC)
    cancelled = service.enqueue(
        site_id=DEFAULT_SITE_ID,
        job_type="TEST",
        payload={},
        actor="maker-a",
    )
    service.request_cancel(cancelled.id, site_id=DEFAULT_SITE_ID)
    session.flush()

    leased = service.lease_next("worker-1", lease_seconds=60)
    assert leased is not None
    assert leased.id == queued.id
    assert leased.status == "RUNNING"
    assert leased.attempts == 1
    service.heartbeat(leased, "worker-1", progress=55)
    assert leased.progress == 55
    service.succeed(leased, {"ok": True})
    assert leased.status == "SUCCEEDED"
    assert leased.result == {"ok": True}


def test_abandoned_job_is_recovered_with_bounded_retry(session: Session) -> None:
    service = JobService(session)
    job = service.enqueue(
        site_id=DEFAULT_SITE_ID,
        job_type="TEST",
        payload={},
        actor="maker-a",
        max_attempts=2,
    )
    job.status = "RUNNING"
    job.attempts = 1
    job.lease_owner = "dead-worker"
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()

    assert service.recover_abandoned() == 1
    assert job.status == "QUEUED"
    job.status = "RUNNING"
    job.attempts = 2
    job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    assert service.recover_abandoned() == 1
    assert job.status == "FAILED"
    assert job.error_code == "LEASE_EXPIRED"
