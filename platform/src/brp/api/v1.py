"""Versioned production API for the multi-site enterprise console."""

import asyncio
import hashlib
import json
import re
import subprocess
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from brp.api.schemas import (
    ApiModel,
    BatchReviewRequest,
    DecisionRevisionResponse,
    GoldenSuiteCreateRequest,
)
from brp.artifacts import artifact_store, safe_storage_key
from brp.config.models import SiteProfile
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.ir.models import DecisionContent
from brp.jobs import JobService
from brp.mode_a import ModeAService
from brp.repository.lifecycle import LifecycleService
from brp.repository.models import (
    Artifact,
    CandidateDecision,
    Decision,
    DecisionRevision,
    DeliveryRecord,
    GoldenSuite,
    GoldenSuiteRevision,
    ImportRun,
    Job,
    LookupSnapshot,
    ReviewQueueItem,
    Site,
    SiteProfileRevision,
    Workspace,
)
from brp.repository.review_queue import BatchReviewDisposition, ReviewQueueService, ReviewStatus
from brp.repository.service import RevisionRepository
from brp.security import RequestAuthenticator
from brp.settings import RuntimeSettings


class ImportRunRequest(ApiModel):
    site_id: UUID
    adapter: Literal[
        "db-postgres-stored-object",
        "ui-html-validation",
        "engine-native",
        "engine-dmn",
        "code-java",
    ]
    content: str | None = Field(default=None, min_length=1, max_length=1_000_000)
    filename: str = Field(min_length=1, max_length=200)
    revision: str = Field(default="uploaded-v1", min_length=1, max_length=200)
    connection_alias: str = Field(default="LOCAL_INLINE", pattern=r"^[A-Z][A-Z0-9_]*$")
    schema_name: str = Field(default="public", pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    object_name: str = Field(default="eligibility", pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    profile_revision: int | None = Field(default=None, ge=1)
    repository_alias: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    class_name: str | None = Field(
        default=None, pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*$"
    )
    method: str | None = Field(default=None, pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")

    @model_validator(mode="after")
    def source_shape(self) -> Self:
        if self.adapter == "code-java":
            if not all(
                (self.profile_revision, self.repository_alias, self.class_name, self.method)
            ):
                raise ValueError(
                    "code-java requires profileRevision, repositoryAlias, className and method"
                )
        elif self.content is None:
            raise ValueError("inline adapters require source content")
        return self


class CandidatePromotionRequest(ApiModel):
    effective_from: datetime
    effective_to: datetime | None = None
    base_revision: int | None = Field(default=None, ge=1)
    product_key: str | None = Field(default=None, max_length=200)
    flow_key: str | None = Field(default=None, max_length=200)


class SiteProfileRequest(ApiModel):
    document: dict[str, Any]


class DecisionRevisionRequest(ApiModel):
    content: DecisionContent
    effective_from: datetime
    effective_to: datetime | None = None
    base_revision: int = Field(ge=1)


class LifecycleRequest(ApiModel):
    reason: str | None = Field(default=None, max_length=2000)


class GoldenRunRequest(ApiModel):
    decision_revision: int = Field(ge=1)
    suite_revision: int = Field(ge=1)


class LookupSnapshotRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=100_000)
    source: dict[str, Any]


class ModeAPublishRequest(ApiModel):
    revision: int = Field(ge=1)
    suite_revision: int = Field(ge=1)
    channel: str = Field(default="production", min_length=1, max_length=100)


class ModeARollbackRequest(ApiModel):
    target_publication_id: int = Field(ge=1)
    channel: str = Field(default="production", min_length=1, max_length=100)


class ModeBDeliveryRequest(ApiModel):
    revision: int = Field(ge=1)
    profile_revision: int = Field(ge=1)


def build_v1_router(
    factory: sessionmaker[Session], request_authenticator: RequestAuthenticator
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    def get_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    SessionDependency = Annotated[Session, Depends(get_session)]

    def actor_for(role: str) -> Any:
        def dependency(request: Request) -> str:
            principal = request_authenticator.authenticate(
                authorization=request.headers.get("Authorization"),
                development_actor=request.headers.get("X-BRP-Actor"),
                development_roles=request.headers.get("X-BRP-Roles"),
            )
            return request_authenticator.require_role(principal, role)

        return dependency

    MakerActor = Annotated[str, Depends(actor_for("maker"))]
    ReviewerActor = Annotated[str, Depends(actor_for("reviewer"))]
    DeployerActor = Annotated[str, Depends(actor_for("deployer"))]

    @router.get("/context")
    def context(session: SessionDependency) -> dict[str, object]:
        workspaces = list(session.scalars(select(Workspace).order_by(Workspace.name)))
        sites = list(session.scalars(select(Site).order_by(Site.name)))
        return {
            "workspaces": [workspace_response(item) for item in workspaces],
            "sites": [site_response(item) for item in sites],
            "authentication": "DEVELOPMENT_IDENTITY",
            "productionBlocked": True,
        }

    @router.get("/overview")
    def overview(site_id: UUID, session: SessionDependency) -> dict[str, object]:
        decision_count = session.scalar(
            select(func.count()).select_from(Decision).where(Decision.site_id == site_id)
        )
        open_reviews = session.scalar(
            select(func.count())
            .select_from(ReviewQueueItem)
            .where(
                ReviewQueueItem.site_id == site_id, ReviewQueueItem.status.in_(["OPEN", "DEFERRED"])
            )
        )
        running_jobs = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.site_id == site_id, Job.status.in_(["QUEUED", "RUNNING"]))
        )
        failed_jobs = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.site_id == site_id, Job.status == "FAILED")
        )
        return {
            "decisions": decision_count or 0,
            "openReviews": open_reviews or 0,
            "activeJobs": running_jobs or 0,
            "failedJobs": failed_jobs or 0,
        }

    @router.get("/workspaces")
    def workspaces(session: SessionDependency) -> list[dict[str, object]]:
        return [
            workspace_response(item)
            for item in session.scalars(select(Workspace).order_by(Workspace.name))
        ]

    @router.get("/sites")
    def sites(
        session: SessionDependency, workspace_id: UUID | None = None
    ) -> list[dict[str, object]]:
        query = select(Site).order_by(Site.name)
        if workspace_id is not None:
            query = query.where(Site.workspace_id == workspace_id)
        return [site_response(item) for item in session.scalars(query)]

    @router.get("/sites/{site_id}/profiles")
    def site_profiles(site_id: UUID, session: SessionDependency) -> list[dict[str, object]]:
        records = session.scalars(
            select(SiteProfileRevision)
            .where(SiteProfileRevision.site_id == site_id)
            .order_by(SiteProfileRevision.revision.desc())
        )
        return [profile_response(item) for item in records]

    @router.post("/sites/{site_id}/profiles", status_code=201)
    def create_site_profile(
        site_id: UUID, body: SiteProfileRequest, actor: MakerActor, session: SessionDependency
    ) -> dict[str, object]:
        require_site(session, site_id)
        validated = SiteProfile.model_validate(body.document)
        document = validated.model_dump(mode="json", by_alias=True, exclude_none=True)
        latest = session.scalar(
            select(func.max(SiteProfileRevision.revision)).where(
                SiteProfileRevision.site_id == site_id
            )
        )
        canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        record = SiteProfileRevision(
            site_id=site_id,
            revision=(latest or 0) + 1,
            document=document,
            content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
            created_by=actor,
        )
        session.add(record)
        session.commit()
        return profile_response(record)

    @router.get("/decisions")
    def decisions(
        site_id: UUID,
        session: SessionDependency,
        q: str | None = None,
        status: str | None = None,
        product: str | None = None,
        flow: str | None = None,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, object]:
        latest_revision = (
            select(func.max(DecisionRevision.revision))
            .where(DecisionRevision.decision_id == Decision.id)
            .correlate(Decision)
            .scalar_subquery()
        )
        query = (
            select(Decision, DecisionRevision)
            .join(
                DecisionRevision,
                (DecisionRevision.decision_id == Decision.id)
                & (DecisionRevision.revision == latest_revision),
            )
            .where(Decision.site_id == site_id)
        )
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(
                or_(Decision.name.ilike(pattern), Decision.decision_key.ilike(pattern))
            )
        if status:
            query = query.where(DecisionRevision.lifecycle_status == status)
        if product:
            query = query.where(Decision.product_key == product)
        if flow:
            query = query.where(Decision.flow_key == flow)
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(
            query.order_by(Decision.name, Decision.decision_key)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [decision_summary(item, revision) for item, revision in rows],
            "page": page,
            "pageSize": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size,
        }

    @router.get("/decisions/{decision_key}", response_model=DecisionRevisionResponse)
    def decision_detail(
        decision_key: str,
        site_id: UUID,
        session: SessionDependency,
        revision: int | None = Query(default=None, ge=1),
    ) -> DecisionRevisionResponse:
        repository = RevisionRepository(session, site_id=site_id)
        decision = repository.get_decision(decision_key)
        record = (
            repository.get_revision(decision_key, revision)
            if revision is not None
            else max(decision.revisions, key=lambda item: item.revision)
        )
        return DecisionRevisionResponse.from_record(record)

    @router.get(
        "/decisions/{decision_key}/revisions",
        response_model=list[DecisionRevisionResponse],
    )
    def decision_revisions(
        decision_key: str, site_id: UUID, session: SessionDependency
    ) -> list[DecisionRevisionResponse]:
        decision = RevisionRepository(session, site_id=site_id).get_decision(decision_key)
        return [
            DecisionRevisionResponse.from_record(item)
            for item in sorted(decision.revisions, key=lambda item: item.revision, reverse=True)
        ]

    @router.post(
        "/decisions/{decision_key}/revisions",
        response_model=DecisionRevisionResponse,
        status_code=201,
    )
    def create_revision(
        decision_key: str,
        site_id: UUID,
        body: DecisionRevisionRequest,
        actor: MakerActor,
        session: SessionDependency,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> DecisionRevisionResponse:
        repository = RevisionRepository(session, site_id=site_id)
        decision = repository.get_decision(decision_key)
        latest = max(item.revision for item in decision.revisions)
        expected = str(body.base_revision)
        if if_match is not None and if_match.strip('W/"') != expected:
            raise RuntimeError("If-Match and baseRevision identify different revisions")
        if latest != body.base_revision:
            raise RuntimeError(
                f"revision conflict: expected {body.base_revision}, latest is {latest}"
            )
        record = repository.add_revision(
            decision_key,
            body.content,
            actor,
            body.effective_from,
            body.effective_to,
        )
        session.commit()
        return DecisionRevisionResponse.from_record(
            repository.get_revision(decision_key, record.revision)
        )

    @router.post(
        "/decisions/{decision_key}/revisions/{revision}/{action}",
        response_model=DecisionRevisionResponse,
    )
    def transition_revision(
        decision_key: str,
        revision: int,
        action: Literal["submit", "approve", "reject", "retire"],
        site_id: UUID,
        body: LifecycleRequest,
        request: Request,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        required_role = (
            "maker" if action == "submit" else ("deployer" if action == "retire" else "checker")
        )
        actor = actor_for(required_role)(request)
        repository = RevisionRepository(session, site_id=site_id)
        record = repository.get_revision(decision_key, revision)
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        if action == "submit":
            lifecycle.submit(record, actor)
        elif action == "approve":
            lifecycle.approve(record, actor)
        elif action == "reject":
            lifecycle.reject(record, actor, reason=body.reason or "")
        else:
            lifecycle.retire(record, actor, reason=body.reason or "")
        session.commit()
        return DecisionRevisionResponse.from_record(repository.get_revision(decision_key, revision))

    @router.get("/decisions/{decision_key}/audit")
    def decision_audit(
        decision_key: str, site_id: UUID, session: SessionDependency
    ) -> list[dict[str, object]]:
        return [
            {
                "id": event.id,
                "actor": event.actor,
                "action": event.action,
                "fromStatus": event.from_status,
                "toStatus": event.to_status,
                "reason": event.reason,
                "contentHash": event.content_hash,
                "correlationId": str(event.correlation_id),
                "at": event.at.isoformat(),
            }
            for event in RevisionRepository(session, site_id=site_id).get_audit(decision_key)
        ]

    @router.post("/import-runs", status_code=202)
    def create_import_run(
        body: ImportRunRequest, actor: MakerActor, session: SessionDependency
    ) -> dict[str, object]:
        require_site(session, body.site_id)
        payload = body.model_dump(mode="json", by_alias=True)
        job = JobService(session).enqueue(
            site_id=body.site_id,
            job_type="IMPORT_EXTRACT",
            payload=payload,
            actor=actor,
        )
        run = ImportRun(
            site_id=body.site_id,
            job_id=job.id,
            adapter=body.adapter,
            source_name=body.filename,
            source_revision=body.revision,
            created_by=actor,
        )
        session.add(run)
        session.flush()
        job.payload = {**payload, "importRunId": str(run.id)}
        session.commit()
        return import_run_response(run, job)

    @router.post("/import-runs/preflight")
    def preflight_import(body: ImportRunRequest, session: SessionDependency) -> dict[str, object]:
        require_site(session, body.site_id)
        if body.adapter != "code-java":
            return {
                "ready": True,
                "adapter": body.adapter,
                "checks": ["safe filename", "bounded input", "durable worker"],
            }
        profile = session.scalar(
            select(SiteProfileRevision).where(
                SiteProfileRevision.site_id == body.site_id,
                SiteProfileRevision.revision == body.profile_revision,
            )
        )
        if profile is None:
            raise LookupError("site profile revision not found")
        document = SiteProfile.model_validate(profile.document)
        repository = next(
            (item for item in document.source.repositories if item.alias == body.repository_alias),
            None,
        )
        context = next(
            (
                item
                for item in document.source.program_contexts
                if item.repository == body.repository_alias
                and item.class_name == body.class_name
                and item.method == body.method
            ),
            None,
        )
        if repository is None or context is None:
            raise ValueError("repository or program context is not declared by the profile")
        runtime = RuntimeSettings.from_environment()
        root = runtime.repository_root.resolve()
        path = (root / repository.path).resolve()
        if root != path and root not in path.parents:
            raise ValueError("source repository escapes BRP_REPOSITORY_ROOT")
        if not path.is_dir():
            raise LookupError("source repository is unavailable")
        completed = subprocess.run(
            ["git", "rev-parse", f"{repository.revision}^{{commit}}"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        commit = completed.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("source revision does not resolve to an immutable commit")
        return {
            "ready": True,
            "adapter": body.adapter,
            "profileRevision": profile.revision,
            "repositoryAlias": repository.alias,
            "resolvedRevision": commit,
            "entryPoint": f"{context.class_name}#{context.method}",
            "checks": [
                "profile allowlist",
                "repository confinement",
                "immutable revision",
                "bounded program context",
            ],
        }

    @router.get("/import-runs")
    def import_runs(site_id: UUID, session: SessionDependency) -> list[dict[str, object]]:
        rows = session.execute(
            select(ImportRun, Job)
            .join(Job, Job.id == ImportRun.job_id)
            .where(ImportRun.site_id == site_id)
            .order_by(ImportRun.created_at.desc())
            .limit(100)
        ).all()
        return [import_run_response(run, job) for run, job in rows]

    @router.get("/import-runs/{run_id}")
    def import_run(run_id: UUID, site_id: UUID, session: SessionDependency) -> dict[str, object]:
        row = session.execute(
            select(ImportRun, Job)
            .join(Job, Job.id == ImportRun.job_id)
            .where(ImportRun.id == run_id, ImportRun.site_id == site_id)
        ).one_or_none()
        if row is None:
            raise LookupError("import run not found")
        run, job = row
        candidates = list(
            session.scalars(
                select(CandidateDecision)
                .where(CandidateDecision.import_run_id == run_id)
                .order_by(CandidateDecision.decision_key)
            )
        )
        return {
            **import_run_response(run, job),
            "candidates": [candidate_response(item) for item in candidates],
        }

    @router.post("/candidates/{candidate_id}/promote", status_code=201)
    def promote_candidate(
        candidate_id: UUID,
        body: CandidatePromotionRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        candidate = session.scalar(
            select(CandidateDecision).where(CandidateDecision.id == candidate_id).with_for_update()
        )
        if candidate is None:
            raise LookupError("candidate not found")
        repository = RevisionRepository(session, site_id=candidate.site_id)
        if candidate.promoted_revision_id is not None:
            existing = session.get(DecisionRevision, candidate.promoted_revision_id)
            assert existing is not None
            return DecisionRevisionResponse.from_record(
                repository.get_revision(candidate.decision_key, existing.revision)
            )
        content = DecisionContent.model_validate(candidate.content)
        existing_decision = session.scalar(
            select(Decision).where(
                Decision.site_id == candidate.site_id,
                Decision.decision_key == candidate.decision_key,
            )
        )
        if existing_decision is None:
            record = repository.create_decision(
                candidate.decision_key,
                content,
                actor,
                body.effective_from,
                body.effective_to,
                product_key=body.product_key,
                flow_key=body.flow_key,
            )
        else:
            latest = max(existing_decision.revisions, key=lambda item: item.revision)
            if body.base_revision is None or body.base_revision != latest.revision:
                raise RuntimeError("baseRevision does not match the latest governed revision")
            record = repository.add_revision(
                candidate.decision_key,
                content,
                actor,
                body.effective_from,
                body.effective_to,
            )
        candidate.promoted_revision_id = record.id
        candidate.status = "PROMOTED"
        session.commit()
        return DecisionRevisionResponse.from_record(
            repository.get_revision(candidate.decision_key, record.revision)
        )

    @router.get("/review-items")
    def review_items(site_id: UUID, session: SessionDependency) -> list[dict[str, object]]:
        records = session.scalars(
            select(ReviewQueueItem)
            .where(ReviewQueueItem.site_id == site_id)
            .order_by(ReviewQueueItem.created_at.desc())
            .limit(200)
        )
        return [review_response(item) for item in records]

    @router.post("/review-items/dispositions")
    def dispose_review_items(
        site_id: UUID,
        body: BatchReviewRequest,
        actor: ReviewerActor,
        session: SessionDependency,
    ) -> list[dict[str, object]]:
        service = ReviewQueueService(session, site_id=site_id)
        records = service.dispose_batch(
            [
                BatchReviewDisposition(
                    item_id=item.item_id,
                    status=ReviewStatus(item.status),
                    reason=item.reason,
                )
                for item in body.dispositions
            ],
            actor=actor,
        )
        session.commit()
        return [review_response(item) for item in records]

    @router.get("/golden-suites/{decision_key}")
    def golden_suites(
        decision_key: str, site_id: UUID, session: SessionDependency
    ) -> list[dict[str, object]]:
        records = session.scalars(
            select(GoldenSuiteRevision)
            .join(GoldenSuite)
            .join(Decision)
            .where(Decision.site_id == site_id, Decision.decision_key == decision_key)
            .order_by(GoldenSuiteRevision.revision.desc())
        )
        repository = GoldenRepository(session, site_id=site_id)
        return [golden_response(item, repository) for item in records]

    @router.get("/lookup-snapshots")
    def lookup_snapshots(
        site_id: UUID, session: SessionDependency, approved: bool = True
    ) -> list[dict[str, object]]:
        query = select(LookupSnapshot).where(LookupSnapshot.site_id == site_id)
        if approved:
            query = query.where(LookupSnapshot.approved.is_(True))
        records = session.scalars(query.order_by(LookupSnapshot.created_at.desc()).limit(100))
        return [lookup_snapshot_response(item) for item in records]

    @router.post("/lookup-snapshots", status_code=201)
    def create_lookup_snapshot(
        site_id: UUID,
        body: LookupSnapshotRequest,
        request: Request,
        session: SessionDependency,
    ) -> dict[str, object]:
        actor = actor_for("checker")(request)
        source = {**body.source, "attestedBy": actor}
        record = GoldenRepository(session, site_id=site_id).snapshot_lookup(
            body.name, body.rows, source, approved=True
        )
        session.commit()
        return lookup_snapshot_response(record)

    @router.post("/golden-suites/{decision_key}/revisions", status_code=201)
    def create_golden_suite(
        decision_key: str,
        site_id: UUID,
        body: GoldenSuiteCreateRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        repository = GoldenRepository(session, site_id=site_id)
        record = repository.create_revision(
            decision_key,
            [
                GoldenCaseData(item.case_key, item.input, item.expected, item.provenance)
                for item in body.cases
            ],
            actor,
            lookup_snapshot_hashes=body.lookup_snapshot_hashes,
        )
        session.commit()
        return golden_response(repository.get_revision(decision_key, record.revision), repository)

    @router.post("/golden-suites/{decision_key}/revisions/{revision}/{action}")
    def transition_golden_suite(
        decision_key: str,
        revision: int,
        action: Literal["submit", "approve"],
        site_id: UUID,
        request: Request,
        session: SessionDependency,
    ) -> dict[str, object]:
        role = "maker" if action == "submit" else "checker"
        actor = actor_for(role)(request)
        repository = GoldenRepository(session, site_id=site_id)
        record = repository.get_revision(decision_key, revision)
        repository.submit(record, actor) if action == "submit" else repository.approve(
            record, actor
        )
        session.commit()
        return golden_response(repository.get_revision(decision_key, revision), repository)

    @router.post("/golden-runs", status_code=202)
    def create_golden_run(
        decision_key: str,
        site_id: UUID,
        body: GoldenRunRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        RevisionRepository(session, site_id=site_id).get_revision(
            decision_key, body.decision_revision
        )
        GoldenRepository(session, site_id=site_id).get_revision(decision_key, body.suite_revision)
        job = JobService(session).enqueue(
            site_id=site_id,
            job_type="GOLDEN_RUN",
            payload={
                "decisionKey": decision_key,
                "decisionRevision": body.decision_revision,
                "suiteRevision": body.suite_revision,
            },
            actor=actor,
        )
        session.commit()
        return job_response(job)

    @router.get("/releases/mode-a/{decision_key}")
    def mode_a_history(
        decision_key: str,
        site_id: UUID,
        session: SessionDependency,
        channel: str = "production",
    ) -> list[dict[str, object]]:
        return [
            publication_response(item)
            for item in ModeAService(session, site_id=site_id).history(
                decision_key, channel=channel
            )
        ]

    @router.post("/releases/mode-a/{decision_key}/publish", status_code=202)
    def create_mode_a_publish(
        decision_key: str,
        site_id: UUID,
        body: ModeAPublishRequest,
        actor: DeployerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        job = JobService(session).enqueue(
            site_id=site_id,
            job_type="MODE_A_PUBLISH",
            payload={"decisionKey": decision_key, **body.model_dump(mode="json", by_alias=True)},
            actor=actor,
        )
        session.commit()
        return job_response(job)

    @router.post("/releases/mode-a/{decision_key}/rollback", status_code=202)
    def create_mode_a_rollback(
        decision_key: str,
        site_id: UUID,
        body: ModeARollbackRequest,
        actor: DeployerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        job = JobService(session).enqueue(
            site_id=site_id,
            job_type="MODE_A_ROLLBACK",
            payload={"decisionKey": decision_key, **body.model_dump(mode="json", by_alias=True)},
            actor=actor,
        )
        session.commit()
        return job_response(job)

    @router.get("/releases/mode-b")
    def mode_b_history(site_id: UUID, session: SessionDependency) -> list[dict[str, object]]:
        rows = session.execute(
            select(DeliveryRecord, DecisionRevision, Decision)
            .join(DecisionRevision, DecisionRevision.id == DeliveryRecord.decision_revision_id)
            .join(Decision, Decision.id == DecisionRevision.decision_id)
            .where(DeliveryRecord.site_id == site_id)
            .order_by(DeliveryRecord.created_at.desc())
            .limit(100)
        ).all()
        return [
            delivery_response(record, revision, decision) for record, revision, decision in rows
        ]

    @router.post("/releases/mode-b/{decision_key}/deliver", status_code=202)
    def create_mode_b_delivery(
        decision_key: str,
        site_id: UUID,
        body: ModeBDeliveryRequest,
        actor: DeployerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        RevisionRepository(session, site_id=site_id).get_revision(decision_key, body.revision)
        profile = session.scalar(
            select(SiteProfileRevision).where(
                SiteProfileRevision.site_id == site_id,
                SiteProfileRevision.revision == body.profile_revision,
            )
        )
        if profile is None:
            raise LookupError("site profile revision not found")
        job = JobService(session).enqueue(
            site_id=site_id,
            job_type="MODE_B_DELIVERY",
            payload={
                "decisionKey": decision_key,
                "revision": body.revision,
                "profileRevision": body.profile_revision,
            },
            actor=actor,
            max_attempts=1,
        )
        session.commit()
        return job_response(job)

    @router.get("/jobs")
    def jobs(site_id: UUID, session: SessionDependency) -> list[dict[str, object]]:
        return [job_response(item) for item in JobService(session).list(site_id=site_id)]

    @router.get("/jobs/{job_id}")
    def job(job_id: UUID, site_id: UUID, session: SessionDependency) -> dict[str, object]:
        return job_response(JobService(session).get(job_id, site_id=site_id))

    @router.post("/jobs/{job_id}/cancel")
    def cancel_job(
        job_id: UUID, site_id: UUID, actor: MakerActor, session: SessionDependency
    ) -> dict[str, object]:
        del actor
        record = JobService(session).request_cancel(job_id, site_id=site_id)
        session.commit()
        return job_response(record)

    @router.get("/jobs/{job_id}/events")
    async def job_events(job_id: UUID, site_id: UUID) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            last = ""
            while True:
                with factory() as event_session:
                    record = JobService(event_session).get(job_id, site_id=site_id)
                    current = json.dumps(job_response(record), ensure_ascii=False)
                    terminal = record.status in {"SUCCEEDED", "FAILED", "CANCELLED"}
                if current != last:
                    yield f"event: progress\ndata: {current}\n\n"
                    last = current
                if terminal:
                    return
                await asyncio.sleep(1)

        return StreamingResponse(events(), media_type="text/event-stream")

    @router.get("/artifacts/{artifact_id}")
    def download_artifact(artifact_id: UUID, site_id: UUID, session: SessionDependency) -> Response:
        record = session.scalar(
            select(Artifact).where(Artifact.id == artifact_id, Artifact.site_id == site_id)
        )
        if record is None:
            raise LookupError("artifact not found")
        try:
            content = artifact_store().get(safe_storage_key(record.storage_key))
        except Exception as exc:
            raise LookupError("artifact content not found") from exc
        if hashlib.sha256(content).hexdigest() != record.content_hash:
            raise RuntimeError("artifact integrity verification failed")
        safe_filename = record.filename.replace('"', "").replace("\r", "").replace("\n", "")
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Digest": f"sha-256={record.content_hash}",
                "X-Content-Hash": record.content_hash,
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
            },
        )

    return router


def require_site(session: Session, site_id: UUID) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise LookupError("site not found")
    return site


def workspace_response(item: Workspace) -> dict[str, object]:
    return {"id": str(item.id), "key": item.workspace_key, "name": item.name}


def site_response(item: Site) -> dict[str, object]:
    return {
        "id": str(item.id),
        "workspaceId": str(item.workspace_id),
        "key": item.site_key,
        "name": item.name,
        "status": item.status,
        "defaultLocale": item.default_locale,
        "timezone": item.timezone,
    }


def profile_response(item: SiteProfileRevision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "siteId": str(item.site_id),
        "revision": item.revision,
        "contentHash": item.content_hash,
        "document": item.document,
        "createdBy": item.created_by,
        "createdAt": item.created_at.isoformat(),
    }


def decision_summary(item: Decision, revision: DecisionRevision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "siteId": str(item.site_id),
        "decisionKey": item.decision_key,
        "name": item.name,
        "productKey": item.product_key,
        "flowKey": item.flow_key,
        "latestRevision": revision.revision,
        "latestStatus": revision.lifecycle_status,
        "owner": revision.created_by,
        "updatedAt": revision.created_at.isoformat(),
        "contentHash": revision.content_hash,
    }


def job_response(item: Job) -> dict[str, object]:
    return {
        "id": str(item.id),
        "siteId": str(item.site_id),
        "type": item.job_type,
        "status": item.status,
        "progress": item.progress,
        "attempts": item.attempts,
        "maxAttempts": item.max_attempts,
        "cancelRequested": item.cancel_requested,
        "errorCode": item.error_code,
        "errorDetail": item.error_detail,
        "result": item.result,
        "correlationId": str(item.correlation_id),
        "createdBy": item.created_by,
        "createdAt": item.created_at.isoformat(),
        "startedAt": item.started_at.isoformat() if item.started_at else None,
        "finishedAt": item.finished_at.isoformat() if item.finished_at else None,
    }


def import_run_response(run: ImportRun, job: Job) -> dict[str, object]:
    return {
        "id": str(run.id),
        "siteId": str(run.site_id),
        "jobId": str(job.id),
        "adapter": run.adapter,
        "sourceName": run.source_name,
        "sourceRevision": run.source_revision,
        "status": job.status,
        "progress": job.progress,
        "candidateCount": (job.result or {}).get("candidateCount"),
        "reviewCount": (job.result or {}).get("reviewCount"),
        "createdBy": run.created_by,
        "createdAt": run.created_at.isoformat(),
    }


def candidate_response(item: CandidateDecision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "decisionKey": item.decision_key,
        "name": item.content.get("decisionName", item.decision_key),
        "status": item.status,
        "content": item.content,
        "sourceSnapshot": item.source_snapshot,
        "diagnostics": item.diagnostics,
        "promotedRevisionId": str(item.promoted_revision_id) if item.promoted_revision_id else None,
    }


def review_response(item: ReviewQueueItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "siteId": str(item.site_id),
        "importRunId": str(item.import_run_id) if item.import_run_id else None,
        "adapter": item.adapter,
        "reasonCode": item.reason_code,
        "rawFragment": item.raw_fragment,
        "provenance": item.provenance,
        "status": item.status,
        "history": item.disposition_history,
        "createdAt": item.created_at.isoformat(),
    }


def golden_response(item: GoldenSuiteRevision, repository: GoldenRepository) -> dict[str, object]:
    return {
        "id": str(item.id),
        "revision": item.revision,
        "status": item.lifecycle_status,
        "contentHash": item.content_hash,
        "lookupSnapshotHashes": item.lookup_snapshot_hashes,
        "caseCount": len(repository.cases(item)),
        "cases": [
            {
                "id": str(case.id),
                "caseKey": case.case_key,
                "input": case.input,
                "expected": case.expected,
                "provenance": case.provenance,
            }
            for case in repository.cases(item)
        ],
        "createdBy": item.created_by,
        "submittedBy": item.submitted_by,
        "approvedBy": item.approved_by,
        "createdAt": item.created_at.isoformat(),
    }


def lookup_snapshot_response(item: LookupSnapshot) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "contentHash": item.content_hash,
        "rowCount": len(item.content),
        "source": item.source,
        "approved": item.approved,
        "createdAt": item.created_at.isoformat(),
    }


def publication_response(item: Any) -> dict[str, object]:
    return {
        "id": item.id,
        "action": item.action,
        "channel": item.channel,
        "actor": item.actor,
        "decisionRevision": item.decision_revision.revision,
        "suiteRevision": item.suite_revision.revision,
        "decisionHash": item.decision_hash,
        "suiteHash": item.suite_hash,
        "artifactHash": item.jdm_hash,
        "previousPublicationId": item.previous_publication_id,
        "sourcePublicationId": item.source_publication_id,
        "validation": item.validation_result,
        "createdAt": item.created_at.isoformat(),
    }


def delivery_response(
    item: DeliveryRecord, revision: DecisionRevision, decision: Decision
) -> dict[str, object]:
    return {
        "id": str(item.id),
        "jobId": str(item.job_id),
        "decisionKey": decision.decision_key,
        "decisionRevision": revision.revision,
        "provider": item.provider,
        "status": item.status,
        "branch": item.branch,
        "externalUrl": item.external_url,
        "evidence": item.evidence,
        "createdAt": item.created_at.isoformat(),
    }
