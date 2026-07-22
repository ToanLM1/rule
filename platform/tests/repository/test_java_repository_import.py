import hashlib
import json
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brp.jobs import JobService, execute_leased_job
from brp.repository.models import (
    DEFAULT_SITE_ID,
    CandidateDecision,
    ImportRun,
    SiteProfileRevision,
)

ROOT = Path(__file__).resolve().parents[3]


def test_pinned_java_repository_import_creates_durable_candidates(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BRP_REPOSITORY_ROOT", str(ROOT))
    document = yaml.safe_load((ROOT / "config/sites/fixture.yaml").read_text(encoding="utf-8"))
    latest = session.scalar(
        select(func.max(SiteProfileRevision.revision)).where(
            SiteProfileRevision.site_id == DEFAULT_SITE_ID
        )
    )
    revision = (latest or 0) + 1
    rendered = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    profile = SiteProfileRevision(
        site_id=DEFAULT_SITE_ID,
        revision=revision,
        document=document,
        content_hash=hashlib.sha256(rendered.encode()).hexdigest(),
        created_by="maker-a",
    )
    session.add(profile)
    session.flush()
    service = JobService(session)
    job = service.enqueue(
        site_id=DEFAULT_SITE_ID,
        job_type="IMPORT_EXTRACT",
        payload={},
        actor="maker-a",
    )
    run = ImportRun(
        site_id=DEFAULT_SITE_ID,
        job_id=job.id,
        adapter="code-java",
        source_name="repository.java",
        source_revision="HEAD",
        created_by="maker-a",
    )
    session.add(run)
    session.flush()
    job.payload = {
        "importRunId": str(run.id),
        "adapter": "code-java",
        "profileRevision": revision,
        "repositoryAlias": "legacy-enrollment",
        "className": "legacy.EnrollmentValidator",
        "method": "evaluate",
    }
    job.status = "RUNNING"
    job.lease_owner = "test-worker"
    job.attempts = 1
    execute_leased_job(session, job, "test-worker")
    assert job.status == "SUCCEEDED"
    candidates = list(
        session.scalars(
            select(CandidateDecision)
            .where(CandidateDecision.import_run_id == run.id)
            .order_by(CandidateDecision.decision_key)
        )
    )
    assert [item.decision_key for item in candidates] == [
        "enrollment_eligibility",
        "premium_adjustments",
        "required_documents",
    ]
    assert all(item.source_snapshot["revision"] for item in candidates)
