"""Durable PostgreSQL-backed work queue and production import handlers."""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from brp.adapters.code_java import JavaRuleMiner
from brp.adapters.joern import JoernLocator, JoernSlicer
from brp.artifacts import artifact_store
from brp.config.models import SiteProfile
from brp.delivery import publish_delivery_branch, transactional_delivery_gate
from brp.delivery_providers import ChangeRequestProvider, GitHubProvider, GitLabProvider
from brp.generation import GenerationOrchestrator, JavaCliReleaseBuilder
from brp.governance.golden import GoldenRepository
from brp.governance.runner import run_zen_advisory
from brp.mode_a import ModeAService
from brp.orchestration import extract_inline
from brp.repository.models import (
    Artifact,
    CandidateDecision,
    DeliveryRecord,
    ImportRun,
    Job,
    SiteProfileRevision,
)
from brp.repository.review_queue import ReviewQueueService
from brp.repository.service import RevisionRepository
from brp.secrets import resolve_secret
from brp.settings import RuntimeSettings

TERMINAL_JOB_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


class JobNotFoundError(LookupError):
    pass


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        *,
        site_id: UUID,
        job_type: str,
        payload: dict[str, Any],
        actor: str,
        max_attempts: int = 3,
    ) -> Job:
        job = Job(
            site_id=site_id,
            job_type=job_type,
            payload=payload,
            created_by=actor,
            max_attempts=max_attempts,
            correlation_id=uuid4(),
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get(self, job_id: UUID, *, site_id: UUID | None = None) -> Job:
        query = select(Job).where(Job.id == job_id)
        if site_id is not None:
            query = query.where(Job.site_id == site_id)
        job = self.session.scalar(query)
        if job is None:
            raise JobNotFoundError(str(job_id))
        return job

    def list(self, *, site_id: UUID, limit: int = 50) -> list[Job]:
        return list(
            self.session.scalars(
                select(Job)
                .where(Job.site_id == site_id)
                .order_by(Job.created_at.desc())
                .limit(limit)
            )
        )

    def request_cancel(self, job_id: UUID, *, site_id: UUID) -> Job:
        job = self.get(job_id, site_id=site_id)
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        job.cancel_requested = True
        job.updated_at = datetime.now(UTC)
        self.session.flush()
        return job

    def lease_next(self, worker_id: str, *, lease_seconds: int = 60) -> Job | None:
        now = datetime.now(UTC)
        job = self.session.scalar(
            select(Job)
            .where(
                Job.attempts < Job.max_attempts,
                or_(
                    Job.status == "QUEUED",
                    (Job.status == "RUNNING") & (Job.lease_expires_at < now),
                ),
            )
            .order_by(Job.created_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        if job.cancel_requested:
            job.status = "CANCELLED"
            job.finished_at = now
            job.progress = 100
            self.session.flush()
            return job
        job.status = "RUNNING"
        job.attempts += 1
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.started_at = job.started_at or now
        job.updated_at = now
        self.session.flush()
        return job

    def heartbeat(self, job: Job, worker_id: str, *, progress: int) -> None:
        if job.lease_owner != worker_id or job.status != "RUNNING":
            raise RuntimeError("job lease is not owned by this worker")
        job.progress = max(0, min(progress, 99))
        job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=60)
        job.updated_at = datetime.now(UTC)
        self.session.flush()

    def recover_abandoned(self) -> int:
        now = datetime.now(UTC)
        records = list(
            self.session.scalars(
                select(Job)
                .where(Job.status == "RUNNING", Job.lease_expires_at < now)
                .with_for_update(skip_locked=True)
            )
        )
        for job in records:
            exhausted = job.attempts >= job.max_attempts
            job.status = "FAILED" if exhausted else "QUEUED"
            job.error_code = "LEASE_EXPIRED"
            job.error_detail = "worker lease expired; job recovered"
            job.lease_owner = None
            job.lease_expires_at = None
            job.finished_at = now if exhausted else None
            job.updated_at = now
        self.session.flush()
        return len(records)

    def succeed(self, job: Job, result: dict[str, Any]) -> None:
        job.status = "SUCCEEDED"
        job.result = result
        job.progress = 100
        job.finished_at = datetime.now(UTC)
        job.lease_owner = None
        job.lease_expires_at = None
        job.error_code = None
        job.error_detail = None
        job.updated_at = datetime.now(UTC)
        self.session.flush()

    def fail(self, job: Job, *, code: str, detail: str) -> None:
        retry = job.attempts < job.max_attempts and not job.cancel_requested
        job.status = "QUEUED" if retry else ("CANCELLED" if job.cancel_requested else "FAILED")
        job.error_code = code
        job.error_detail = detail[-4000:]
        job.lease_owner = None
        job.lease_expires_at = None
        job.finished_at = None if retry else datetime.now(UTC)
        job.updated_at = datetime.now(UTC)
        self.session.flush()


JobHandler = Callable[[Session, Job, str], dict[str, Any]]


def handle_import(session: Session, job: Job, worker_id: str) -> dict[str, Any]:
    service = JobService(session)
    service.heartbeat(job, worker_id, progress=10)
    payload = job.payload
    if payload["adapter"] == "code-java":
        batch = _extract_java_repository(session, job, worker_id)
    else:
        batch = extract_inline(
            adapter=str(payload["adapter"]),
            content=str(payload["content"]),
            filename=str(payload["filename"]),
            revision=str(payload["revision"]),
            connection_alias=str(payload["connectionAlias"]),
            schema_name=str(payload["schemaName"]),
            object_name=str(payload["objectName"]),
        )
    run_id = UUID(str(payload["importRunId"]))
    run = session.get(ImportRun, run_id)
    if run is None or run.site_id != job.site_id:
        raise RuntimeError("import run does not belong to the leased job")
    service.heartbeat(job, worker_id, progress=55)
    snapshot = batch.source_snapshot.model_dump(mode="json", by_alias=True)
    diagnostics = [item.model_dump(mode="json", by_alias=True) for item in batch.diagnostics]
    for candidate in batch.decisions:
        session.add(
            CandidateDecision(
                site_id=job.site_id,
                import_run_id=run.id,
                decision_key=candidate.decision_key,
                content=candidate.content.model_dump(mode="json", by_alias=True, exclude_none=True),
                source_snapshot=snapshot,
                diagnostics=diagnostics,
            )
        )
    review = ReviewQueueService(session, site_id=job.site_id)
    for item in batch.unmappable:
        review.add(
            adapter=batch.adapter,
            source_snapshot_hash=batch.source_snapshot.content_hash,
            raw_fragment=item.raw_fragment,
            provenance=item.provenance,
            reason_code=item.reason_code,
            actor=job.created_by,
            import_run_id=run.id,
        )
    run.status = "SUCCEEDED"
    run.completed_at = datetime.now(UTC)
    session.flush()
    return {
        "importRunId": str(run.id),
        "candidateCount": len(batch.decisions),
        "reviewCount": len(batch.unmappable),
        "sourceHash": batch.source_snapshot.content_hash,
    }


def _extract_java_repository(session: Session, job: Job, worker_id: str) -> Any:
    payload = job.payload
    profile = session.scalar(
        select(SiteProfileRevision).where(
            SiteProfileRevision.site_id == job.site_id,
            SiteProfileRevision.revision == int(payload["profileRevision"]),
        )
    )
    if profile is None:
        raise LookupError("site profile revision not found")
    document = SiteProfile.model_validate(profile.document)
    alias = str(payload["repositoryAlias"])
    repository = next((item for item in document.source.repositories if item.alias == alias), None)
    context = next(
        (
            item
            for item in document.source.program_contexts
            if item.repository == alias
            and item.class_name == payload["className"]
            and item.method == payload["method"]
        ),
        None,
    )
    if repository is None or context is None:
        raise ValueError("repository or program context is not declared by the profile")
    settings = RuntimeSettings.from_environment()
    root = settings.repository_root.resolve()
    source = (root / repository.path).resolve()
    if root != source and root not in source.parents:
        raise ValueError("source repository escapes BRP_REPOSITORY_ROOT")
    if not source.is_dir():
        raise FileNotFoundError("configured source repository is unavailable")
    resolved = subprocess.run(
        ["git", "rev-parse", f"{repository.revision}^{{commit}}"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ValueError("source revision does not resolve to an immutable commit")
    git_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve()
    if root != git_root and root not in git_root.parents:
        raise ValueError("Git repository escapes BRP_REPOSITORY_ROOT")
    source_relative = source.relative_to(git_root)
    JobService(session).heartbeat(job, worker_id, progress=20)
    with tempfile.TemporaryDirectory(prefix="brp-java-source-") as directory:
        checkout = Path(directory) / "repository"
        subprocess.run(
            ["git", "clone", "--no-checkout", str(git_root), str(checkout)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", "--detach", resolved],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        )
        repository_checkout = checkout / source_relative
        methods = JoernLocator(repository_checkout, alias).locate(
            context.class_name, context.method
        )
        manifest = JoernSlicer().slice(methods)
        fixtures = Path(__file__).resolve().parents[2] / "tests/fixtures/conformance"
        return JavaRuleMiner(fixtures).mine(manifest)


def handle_golden_run(session: Session, job: Job, worker_id: str) -> dict[str, Any]:
    service = JobService(session)
    service.heartbeat(job, worker_id, progress=20)
    payload = job.payload
    decision_key = str(payload["decisionKey"])
    decision = RevisionRepository(session, site_id=job.site_id).get_revision(
        decision_key, int(payload["decisionRevision"])
    )
    suite = GoldenRepository(session, site_id=job.site_id).get_revision(
        decision_key, int(payload["suiteRevision"])
    )
    service.heartbeat(job, worker_id, progress=60)
    return run_zen_advisory(session, decision, suite)


def handle_mode_a_publish(session: Session, job: Job, worker_id: str) -> dict[str, Any]:
    JobService(session).heartbeat(job, worker_id, progress=25)
    payload = job.payload
    publication = ModeAService(session, site_id=job.site_id).publish(
        str(payload["decisionKey"]),
        int(payload["revision"]),
        int(payload["suiteRevision"]),
        job.created_by,
        channel=str(payload["channel"]),
    )
    return {
        "publicationId": publication.id,
        "action": publication.action,
        "artifactHash": publication.jdm_hash,
    }


def handle_mode_a_rollback(session: Session, job: Job, worker_id: str) -> dict[str, Any]:
    JobService(session).heartbeat(job, worker_id, progress=25)
    payload = job.payload
    publication = ModeAService(session, site_id=job.site_id).rollback(
        str(payload["decisionKey"]),
        int(payload["targetPublicationId"]),
        job.created_by,
        channel=str(payload["channel"]),
    )
    return {
        "publicationId": publication.id,
        "action": publication.action,
        "artifactHash": publication.jdm_hash,
    }


def handle_mode_b_delivery(session: Session, job: Job, worker_id: str) -> dict[str, Any]:
    payload = job.payload
    decision_key = str(payload["decisionKey"])
    revision_number = int(payload["revision"])
    profile_revision = int(payload["profileRevision"])
    profile_record = session.scalar(
        select(SiteProfileRevision).where(
            SiteProfileRevision.site_id == job.site_id,
            SiteProfileRevision.revision == profile_revision,
        )
    )
    if profile_record is None:
        raise LookupError("site profile revision not found")
    profile = SiteProfile.model_validate(profile_record.document)
    if profile.delivery_mode.value != "B" or profile.target is None:
        raise ValueError("Mode-B delivery requires a Mode-B site profile")
    if profile.language.value != "java":
        raise ValueError("C# delivery is non-authoritative until a pinned SDK is configured")

    settings = RuntimeSettings.from_environment()
    repository_root = settings.repository_root.resolve()
    remote = (repository_root / profile.target.repository).resolve()
    if repository_root != remote and repository_root not in remote.parents:
        raise ValueError("target repository escapes BRP_REPOSITORY_ROOT")
    if not remote.exists():
        raise FileNotFoundError("configured target repository is unavailable")

    stage = settings.artifact_root.resolve() / "staging" / str(job.id)
    stage.mkdir(parents=True, exist_ok=False)
    service = JobService(session)
    service.heartbeat(job, worker_id, progress=10)
    generated = GenerationOrchestrator(
        session,
        JavaCliReleaseBuilder(repository_root),
        site_id=job.site_id,
    ).generate(profile, decision_key, stage / "generated", revision=revision_number)
    service.heartbeat(job, worker_id, progress=40)
    gate = transactional_delivery_gate(
        remote,
        profile.target.base_branch,
        generated,
        stage / "gate",
    )
    delivery = publish_delivery_branch(gate, decision_key, revision_number, {})
    service.heartbeat(job, worker_id, progress=75)

    external_url: str | None = None
    external_id: str | None = None
    provider_name = profile.target.pr_provider
    if provider_name in {"github", "gitlab"}:
        assert profile.target.token_secret_ref is not None
        assert profile.target.provider_repository is not None
        token = resolve_secret(profile.target.token_secret_ref)
        if provider_name == "github":
            provider = cast(ChangeRequestProvider, GitHubProvider(token))
        else:
            provider = cast(
                ChangeRequestProvider,
                GitLabProvider(
                    token,
                    base_url=profile.target.provider_api_url or "https://gitlab.com/api/v4",
                ),
            )
        change = provider.ensure_change_request(
            repository=profile.target.provider_repository,
            head=delivery.branch,
            base=profile.target.base_branch,
            title=f"Generate {decision_key} r{revision_number}",
            body=delivery.review_report.read_text(encoding="utf-8"),
        )
        external_url = change.url
        external_id = change.external_id

    archive = _deterministic_zip(generated)
    stored = artifact_store(settings).put(
        f"deliveries/{job.id}/{decision_key}-r{revision_number}.zip", archive
    )
    artifact = Artifact(
        site_id=job.site_id,
        job_id=job.id,
        kind="MODE_B_RELEASE",
        storage_key=stored.storage_key,
        filename=f"{decision_key}-r{revision_number}.zip",
        content_hash=stored.content_hash,
        size_bytes=stored.size_bytes,
        artifact_metadata={"manifestHash": gate.manifest_hash},
    )
    revision = RevisionRepository(session, site_id=job.site_id).get_revision(
        decision_key, revision_number
    )
    record = DeliveryRecord(
        site_id=job.site_id,
        job_id=job.id,
        decision_revision_id=revision.id,
        provider=provider_name,
        status="DELIVERED",
        branch=delivery.branch,
        external_url=external_url,
        evidence={
            "baseCommit": delivery.base_commit,
            "headCommit": delivery.head_commit,
            "manifestHash": gate.manifest_hash,
            "tests": list(gate.tests),
            "externalId": external_id,
        },
    )
    session.add_all([artifact, record])
    session.flush()
    return {
        "deliveryId": str(record.id),
        "artifactId": str(artifact.id),
        "artifactHash": stored.content_hash,
        "branch": delivery.branch,
        "externalUrl": external_url,
        "evidence": record.evidence,
    }


def _deterministic_zip(root: Path) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            info = ZipInfo(path.relative_to(root).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return stream.getvalue()


HANDLERS: dict[str, JobHandler] = {
    "IMPORT_EXTRACT": handle_import,
    "GOLDEN_RUN": handle_golden_run,
    "MODE_A_PUBLISH": handle_mode_a_publish,
    "MODE_A_ROLLBACK": handle_mode_a_rollback,
    "MODE_B_DELIVERY": handle_mode_b_delivery,
}


def execute_leased_job(session: Session, job: Job, worker_id: str) -> None:
    service = JobService(session)
    if job.status == "CANCELLED":
        return
    handler = HANDLERS.get(job.job_type)
    if handler is None:
        service.fail(
            job, code="UNSUPPORTED_JOB_TYPE", detail=f"unsupported job type: {job.job_type}"
        )
        return
    try:
        result = handler(session, job, worker_id)
        if job.cancel_requested:
            service.fail(job, code="CANCELLED", detail="job was cancelled")
        else:
            service.succeed(job, result)
    except Exception as exc:
        if job.job_type == "IMPORT_EXTRACT":
            run_id = job.payload.get("importRunId")
            run = session.get(ImportRun, UUID(str(run_id))) if run_id else None
            if run is not None:
                run.status = "FAILED"
                run.completed_at = datetime.now(UTC)
        service.fail(job, code=type(exc).__name__.upper(), detail=str(exc))
