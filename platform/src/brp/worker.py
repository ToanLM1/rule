"""Standalone durable-job worker process."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from brp.db import create_database_engine
from brp.jobs import JobService, execute_leased_job
from brp.repository.models import WorkerHeartbeat
from brp.settings import RuntimeSettings


def run(*, once: bool = False) -> int:
    engine = create_database_engine()
    worker_id = os.getenv("BRP_WORKER_ID", f"{socket.gethostname()}-{uuid4().hex[:8]}")
    poll_seconds = float(os.getenv("BRP_WORKER_POLL_SECONDS", "1"))
    processed = 0
    started_at = datetime.now(UTC)
    stopped = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(engine, worker_id, started_at, stopped),
        name="brp-worker-heartbeat",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        while True:
            with Session(engine) as session:
                _record_heartbeat(session, worker_id, started_at)
                service = JobService(session)
                service.recover_abandoned()
                job = service.lease_next(worker_id)
                job_id = job.id if job is not None else None
                job_status = job.status if job is not None else None
                session.commit()
                if job_id is not None and job_status != "CANCELLED":
                    with Session(engine) as work_session:
                        leased = JobService(work_session).get(job_id)
                        execute_leased_job(work_session, leased, worker_id)
                        work_session.commit()
                    processed += 1
            if once:
                return processed
            if job is None:
                time.sleep(poll_seconds)
    finally:
        stopped.set()
        heartbeat_thread.join(timeout=5)
        engine.dispose()


def _record_heartbeat(session: Session, worker_id: str, started_at: datetime) -> None:
    heartbeat = session.get(WorkerHeartbeat, worker_id)
    if heartbeat is None:
        session.add(
            WorkerHeartbeat(
                worker_id=worker_id,
                last_seen_at=datetime.now(UTC),
                started_at=started_at,
                worker_metadata={"host": socket.gethostname(), "pid": os.getpid()},
            )
        )
    else:
        heartbeat.last_seen_at = datetime.now(UTC)


def _heartbeat_loop(
    engine: Engine, worker_id: str, started_at: datetime, stopped: threading.Event
) -> None:
    while not stopped.is_set():
        try:
            with Session(engine) as session:
                _record_heartbeat(session, worker_id, started_at)
                session.commit()
        except Exception:
            pass
        stopped.wait(10)


def health() -> int:
    worker_id = os.getenv("BRP_WORKER_ID", "")
    if not worker_id:
        return 1
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            last_seen = session.scalar(
                select(WorkerHeartbeat.last_seen_at).where(WorkerHeartbeat.worker_id == worker_id)
            )
            stale = datetime.now(UTC) - timedelta(
                seconds=RuntimeSettings.from_environment().worker_stale_seconds
            )
            return 0 if last_seen is not None and last_seen >= stale else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    if "--health" in sys.argv:
        raise SystemExit(health())
    run(once=os.getenv("BRP_WORKER_ONCE", "").lower() == "true")
