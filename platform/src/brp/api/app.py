"""FastAPI routes for governed decision revisions."""

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from brp.api.schemas import (
    AuditEventResponse,
    BatchReviewRequest,
    DecisionCreateRequest,
    DecisionRevisionResponse,
    DecisionSummaryResponse,
    GoldenSuiteCreateRequest,
    OrchestrationExtractRequest,
    OrchestrationGenerateRequest,
    OrchestrationPreflightRequest,
    PreviewRequest,
    ReasonRequest,
    RevisionCreateRequest,
)
from brp.db import create_database_engine
from brp.governance.diff import semantic_diff
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.governance.runner import run_zen_advisory
from brp.governance.zen import DictLookupResolver, preview
from brp.ir.models import DecisionContent
from brp.mode_a import ModeAService
from brp.orchestration import (
    OrchestrationError,
    extract_inline,
    generate_preview,
    preflight,
)
from brp.orchestration import (
    catalog as orchestration_catalog,
)
from brp.repository.errors import (
    ApprovalEvidenceError,
    ApprovedRevisionNotFoundError,
    DecisionNotFoundError,
    EffectiveIntervalOverlapError,
    IllegalLifecycleTransitionError,
    RepositoryError,
    RevisionNotFoundError,
    SelfApprovalError,
    SubmissionActorError,
)
from brp.repository.lifecycle import (
    LifecycleService,
    ReleaseEvidencePolicy,
)
from brp.repository.models import (
    DecisionRevision,
    GoldenSuite,
    GoldenSuiteRevision,
    ModeAPublication,
)
from brp.repository.review_queue import (
    BatchReviewDisposition,
    ReviewQueueService,
    ReviewStatus,
)
from brp.repository.service import RevisionRepository
from brp.security import (
    AuthenticationError,
    AuthorizationError,
    Principal,
    RequestAuthenticator,
    SecuritySettings,
)


def create_app(
    evidence_policy: ReleaseEvidencePolicy | None = None,
    *,
    security: SecuritySettings | None = None,
    key_resolver: Any = None,
) -> FastAPI:
    engine = create_database_engine()
    factory = sessionmaker(engine, expire_on_commit=False)
    policy = evidence_policy or GoldenSuiteEvidencePolicy()
    request_authenticator = RequestAuthenticator(
        security or SecuritySettings(), key_resolver=key_resolver
    )
    app = FastAPI(title="Business Rules Platform", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    SessionDependency = Annotated[Session, Depends(get_session)]

    def authenticate_request(request: Request) -> Principal:
        return request_authenticator.authenticate(
            authorization=request.headers.get("Authorization"),
            development_actor=request.headers.get("X-BRP-Actor"),
            development_roles=request.headers.get("X-BRP-Roles"),
        )

    def require_role(role: str) -> Any:
        def dependency(
            principal: Annotated[Principal, Depends(authenticate_request)],
        ) -> str:
            return request_authenticator.require_role(principal, role)

        return dependency

    MakerActor = Annotated[str, Depends(require_role("maker"))]
    CheckerActor = Annotated[str, Depends(require_role("checker"))]
    ReviewerActor = Annotated[str, Depends(require_role("reviewer"))]
    DeployerActor = Annotated[str, Depends(require_role("deployer"))]

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        del request
        return problem(401, "Authentication failed", str(exc))

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
        del request
        return problem(403, "Role denied", str(exc))

    @app.exception_handler(OrchestrationError)
    async def orchestration_error_handler(
        request: Request, exc: OrchestrationError
    ) -> JSONResponse:
        del request
        return problem(422, "Orchestration input rejected", str(exc))

    @app.exception_handler(RepositoryError)
    async def repository_error_handler(request: Request, exc: RepositoryError) -> JSONResponse:
        del request
        status, title = repository_problem(exc)
        return problem(status, title, str(exc))

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        del request
        return problem(409, "Repository conflict", "A uniqueness or integrity rule failed")

    @app.post("/decisions", status_code=201, response_model=DecisionRevisionResponse)
    def create_decision(
        body: DecisionCreateRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository = RevisionRepository(session)
        record = repository.create_decision(
            body.decision_key,
            body.content,
            actor,
            body.effective_from,
            body.effective_to,
        )
        session.commit()
        return response_for(repository.get_revision(body.decision_key, record.revision))

    @app.get("/decisions", response_model=list[DecisionSummaryResponse])
    def list_decisions(session: SessionDependency) -> list[DecisionSummaryResponse]:
        repository = RevisionRepository(session)
        return [DecisionSummaryResponse.from_record(item) for item in repository.list_decisions()]

    @app.get("/decisions/{decision_key}", response_model=DecisionRevisionResponse)
    def get_decision(
        decision_key: str,
        session: SessionDependency,
        revision: int | None = Query(default=None, ge=1),
        as_of: datetime | None = None,
        approved: bool = False,
    ) -> DecisionRevisionResponse:
        repository = RevisionRepository(session)
        if approved or as_of is not None:
            record = repository.resolve_approved(decision_key, revision=revision, as_of=as_of)
        elif revision is not None:
            record = repository.get_revision(decision_key, revision)
        else:
            decision = repository.get_decision(decision_key)
            latest = max(decision.revisions, key=lambda item: item.revision)
            record = repository.get_revision(decision_key, latest.revision)
        return response_for(record)

    @app.post(
        "/decisions/{decision_key}/revisions",
        status_code=201,
        response_model=DecisionRevisionResponse,
    )
    def add_revision(
        decision_key: str,
        body: RevisionCreateRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository = RevisionRepository(session)
        record = repository.add_revision(
            decision_key,
            body.content,
            actor,
            body.effective_from,
            body.effective_to,
        )
        session.commit()
        return response_for(repository.get_revision(decision_key, record.revision))

    def lifecycle_record(
        decision_key: str, revision: int, session: Session
    ) -> tuple[RevisionRepository, DecisionRevision]:
        repository = RevisionRepository(session)
        return repository, repository.get_revision(decision_key, revision)

    @app.post(
        "/decisions/{decision_key}/revisions/{revision}/submit",
        response_model=DecisionRevisionResponse,
    )
    def submit_revision(
        decision_key: str,
        revision: int,
        actor: MakerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository, record = lifecycle_record(decision_key, revision, session)
        LifecycleService(session, policy).submit(record, actor)
        session.commit()
        return response_for(repository.get_revision(decision_key, revision))

    @app.post(
        "/decisions/{decision_key}/revisions/{revision}/approve",
        response_model=DecisionRevisionResponse,
    )
    def approve_revision(
        decision_key: str,
        revision: int,
        actor: CheckerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository, record = lifecycle_record(decision_key, revision, session)
        LifecycleService(session, policy).approve(record, actor)
        session.commit()
        return response_for(repository.get_revision(decision_key, revision))

    @app.post(
        "/decisions/{decision_key}/revisions/{revision}/reject",
        response_model=DecisionRevisionResponse,
    )
    def reject_revision(
        decision_key: str,
        revision: int,
        body: ReasonRequest,
        actor: CheckerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository, record = lifecycle_record(decision_key, revision, session)
        LifecycleService(session, policy).reject(record, actor, reason=body.reason)
        session.commit()
        return response_for(repository.get_revision(decision_key, revision))

    @app.post(
        "/decisions/{decision_key}/revisions/{revision}/retire",
        response_model=DecisionRevisionResponse,
    )
    def retire_revision(
        decision_key: str,
        revision: int,
        body: ReasonRequest,
        actor: CheckerActor,
        session: SessionDependency,
    ) -> DecisionRevisionResponse:
        repository, record = lifecycle_record(decision_key, revision, session)
        LifecycleService(session, policy).retire(record, actor, reason=body.reason)
        session.commit()
        return response_for(repository.get_revision(decision_key, revision))

    @app.get(
        "/decisions/{decision_key}/audit",
        response_model=list[AuditEventResponse],
    )
    def get_audit(decision_key: str, session: SessionDependency) -> list[AuditEventResponse]:
        repository = RevisionRepository(session)
        repository.get_decision(decision_key)
        return [
            AuditEventResponse.from_record(event) for event in repository.get_audit(decision_key)
        ]

    @app.get("/decisions/{decision_key}/diff")
    def get_diff(
        decision_key: str,
        session: SessionDependency,
        from_revision: int = Query(alias="from", ge=1),
        to_revision: int = Query(alias="to", ge=1),
    ) -> dict[str, object]:
        repository = RevisionRepository(session)
        before = repository.get_revision(decision_key, from_revision)
        after = repository.get_revision(decision_key, to_revision)
        result = semantic_diff(
            DecisionContent.model_validate(before.content_blob.content),
            DecisionContent.model_validate(after.content_blob.content),
        )
        return {"fromRevision": from_revision, "toRevision": to_revision, **result}

    @app.post("/preview/{decision_key}")
    def preview_decision(
        decision_key: str,
        body: PreviewRequest,
        session: SessionDependency,
        revision: int = Query(ge=1),
    ) -> dict[str, object]:
        record = RevisionRepository(session).get_revision(decision_key, revision)
        content = DecisionContent.model_validate(record.content_blob.content)
        return preview(content, body.input, DictLookupResolver(body.lookup_snapshots))

    @app.post("/golden-suites/{decision_key}", status_code=201)
    def create_golden_suite(
        decision_key: str,
        body: GoldenSuiteCreateRequest,
        actor: MakerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        repository = GoldenRepository(session)
        record = repository.create_revision(
            decision_key,
            [
                GoldenCaseData(
                    case_key=case.case_key,
                    input=case.input,
                    expected=case.expected,
                    provenance=case.provenance,
                )
                for case in body.cases
            ],
            actor,
            lookup_snapshot_hashes=body.lookup_snapshot_hashes,
        )
        session.commit()
        return golden_response(record)

    @app.post("/golden-suites/{decision_key}/{revision}/submit")
    def submit_golden_suite(
        decision_key: str,
        revision: int,
        actor: MakerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        repository = GoldenRepository(session)
        record = repository.get_revision(decision_key, revision)
        repository.submit(record, actor)
        session.commit()
        return golden_response(record)

    @app.post("/golden-suites/{decision_key}/{revision}/approve")
    def approve_golden_suite(
        decision_key: str,
        revision: int,
        actor: CheckerActor,
        session: SessionDependency,
    ) -> dict[str, object]:
        repository = GoldenRepository(session)
        record = repository.get_revision(decision_key, revision)
        repository.approve(record, actor)
        session.commit()
        return golden_response(record)

    @app.post("/golden/{decision_key}/run")
    def run_golden_suite(
        decision_key: str,
        session: SessionDependency,
        executor: str = "zen-advisory",
        decision_revision: int = Query(ge=1),
        suite_revision: int = Query(ge=1),
    ) -> dict[str, object]:
        if executor != "zen-advisory":
            return {
                "executor": "GENERATED_JAVA",
                "authority": "AUTHORITATIVE",
                "status": "NOT_RUN",
                "error": "a generated release artifact is required",
            }
        decision = RevisionRepository(session).get_revision(decision_key, decision_revision)
        suite = GoldenRepository(session).get_revision(decision_key, suite_revision)
        if suite.lifecycle_status != "APPROVED":
            raise ApprovalEvidenceError("golden runner requires an approved suite revision")
        return run_zen_advisory(session, decision, suite)

    @app.get("/golden-suites/{decision_key}")
    def list_golden_suites(
        decision_key: str, session: SessionDependency
    ) -> list[dict[str, object]]:
        decision = RevisionRepository(session).get_decision(decision_key)
        records = list(
            session.scalars(
                select(GoldenSuiteRevision)
                .join(GoldenSuite)
                .where(GoldenSuite.decision_id == decision.id)
                .order_by(GoldenSuiteRevision.revision.desc())
            )
        )
        return [golden_response(record) for record in records]

    @app.get("/review-queue")
    def list_review_queue(session: SessionDependency) -> list[dict[str, object]]:
        return [
            {
                "id": str(item.id),
                "adapter": item.adapter,
                "reasonCode": item.reason_code,
                "rawFragment": item.raw_fragment,
                "provenance": item.provenance,
                "status": item.status,
            }
            for item in ReviewQueueService(session).list_open()
        ]

    @app.get("/orchestration/catalog")
    def get_orchestration_catalog() -> dict[str, object]:
        return orchestration_catalog()

    @app.post("/orchestration/preflight")
    def run_orchestration_preflight(
        body: OrchestrationPreflightRequest,
    ) -> dict[str, object]:
        return preflight(body.profiles, body.inventory).model_dump(mode="json", by_alias=True)

    @app.post("/orchestration/extract")
    def run_orchestration_extract(
        body: OrchestrationExtractRequest,
        actor: MakerActor,
    ) -> dict[str, object]:
        del actor
        try:
            batch = extract_inline(
                adapter=body.adapter,
                content=body.content,
                filename=body.filename,
                revision=body.revision,
                connection_alias=body.connection_alias,
                schema_name=body.schema_name,
                object_name=body.object_name,
            )
        except OrchestrationError:
            raise
        except (UnicodeError, ValueError) as exc:
            raise OrchestrationError(str(exc)) from exc
        return {
            "evidenceLabel": "LOCAL_PREVIEW_NON_AUTHORITATIVE",
            "persistent": False,
            "batch": batch.model_dump(mode="json", by_alias=True),
        }

    @app.post("/orchestration/generate")
    def run_orchestration_generate(
        body: OrchestrationGenerateRequest,
        actor: MakerActor,
    ) -> dict[str, object]:
        del actor
        try:
            return generate_preview(
                generator=body.generator,
                content=body.content,
                csharp_namespace=body.csharp_namespace,
            )
        except OrchestrationError:
            raise
        except ValueError as exc:
            raise OrchestrationError(str(exc)) from exc

    @app.post("/review-queue/batch")
    def batch_review(
        body: BatchReviewRequest,
        actor: ReviewerActor,
        session: SessionDependency,
    ) -> list[dict[str, object]]:
        records = ReviewQueueService(session).dispose_batch(
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
        return [
            {
                "id": str(item.id),
                "status": item.status,
                "dispositionHistory": item.disposition_history,
            }
            for item in records
        ]

    @app.post("/mode-a/{decision_key}/publications", status_code=201)
    def publish_mode_a(
        decision_key: str,
        actor: DeployerActor,
        session: SessionDependency,
        decision_revision: int = Query(ge=1),
        suite_revision: int = Query(ge=1),
        channel: str = "production",
    ) -> dict[str, object]:
        record = ModeAService(session).publish(
            decision_key,
            decision_revision,
            suite_revision,
            actor,
            channel=channel,
        )
        session.commit()
        return mode_a_response(record)

    @app.post("/mode-a/{decision_key}/rollbacks/{publication_id}", status_code=201)
    def rollback_mode_a(
        decision_key: str,
        publication_id: int,
        actor: DeployerActor,
        session: SessionDependency,
        channel: str = "production",
    ) -> dict[str, object]:
        record = ModeAService(session).rollback(
            decision_key, publication_id, actor, channel=channel
        )
        session.commit()
        return mode_a_response(record)

    @app.post("/mode-a/{decision_key}/execute")
    def execute_mode_a(
        decision_key: str,
        body: PreviewRequest,
        session: SessionDependency,
        channel: str = "production",
    ) -> dict[str, object]:
        return ModeAService(session).execute(decision_key, body.input, channel=channel)

    @app.get("/mode-a/{decision_key}/publications")
    def mode_a_history(
        decision_key: str,
        session: SessionDependency,
        channel: str = "production",
    ) -> list[dict[str, object]]:
        return [
            mode_a_response(record)
            for record in ModeAService(session).history(decision_key, channel=channel)
        ]

    return app


def response_for(record: DecisionRevision) -> DecisionRevisionResponse:
    return DecisionRevisionResponse.from_record(record)


def golden_response(record: GoldenSuiteRevision) -> dict[str, object]:
    return {
        "revision": record.revision,
        "status": record.lifecycle_status,
        "contentHash": record.content_hash,
        "lookupSnapshotHashes": record.lookup_snapshot_hashes,
    }


def mode_a_response(record: ModeAPublication) -> dict[str, object]:
    return {
        "publicationId": record.id,
        "action": record.action,
        "channel": record.channel,
        "decisionRevision": record.decision_revision.revision,
        "suiteRevision": record.suite_revision.revision,
        "decisionHash": record.decision_hash,
        "suiteHash": record.suite_hash,
        "jdmHash": record.jdm_hash,
        "lookupSnapshotHashes": record.lookup_snapshot_hashes,
        "previousPublicationId": record.previous_publication_id,
        "sourcePublicationId": record.source_publication_id,
        "actor": record.actor,
        "createdAt": record.created_at.isoformat(),
    }


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"urn:brp:problem:{title.lower().replace(' ', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


def repository_problem(exc: RepositoryError) -> tuple[int, str]:
    if isinstance(
        exc,
        (DecisionNotFoundError, RevisionNotFoundError, ApprovedRevisionNotFoundError),
    ):
        return 404, "Not found"
    if isinstance(exc, (SelfApprovalError, SubmissionActorError)):
        return 403, "Maker-checker violation"
    if isinstance(
        exc,
        (
            IllegalLifecycleTransitionError,
            ApprovalEvidenceError,
            EffectiveIntervalOverlapError,
        ),
    ):
        return 409, "Governance conflict"
    return 400, "Repository request failed"


app = create_app(security=SecuritySettings.from_environment())
