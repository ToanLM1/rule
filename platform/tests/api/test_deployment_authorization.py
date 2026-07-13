import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from brp.api.app import create_app
from brp.db import create_database_engine
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.ir.models import DecisionContent
from brp.repository.lifecycle import LifecycleService
from brp.repository.service import RevisionRepository
from brp.security import OidcConfig, SecuritySettings

PLATFORM = Path(__file__).resolve().parents[2]
FIXTURE = PLATFORM / "tests/fixtures/conformance/enrollment_eligibility.json"
ISSUER = "https://idp.example.test"
AUDIENCE = "brp-api"


def prepare_release() -> tuple[str, int, int]:
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    key = f"deployment_auth_{uuid4().hex}"
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["decisionId"] = key
    with Session(engine) as session:
        revision = RevisionRepository(session).create_decision(
            key,
            DecisionContent.model_validate(document),
            "maker",
            datetime(2026, 1, 1, tzinfo=UTC),
        )
        golden = GoldenRepository(session)
        snapshot = golden.snapshot_lookup(
            "지역",
            [{"region_code": "SEOUL", "eligible": True, "name": "서울"}],
            {"ref": "lookup://region_eligibility"},
            approved=True,
        )
        suite = golden.create_revision(
            key,
            [
                GoldenCaseData(
                    case_key="under-age",
                    input={
                        "age": 17,
                        "productCode": "CANCER_BASIC",
                        "regionCode": "SEOUL",
                    },
                    expected={"eligible": False, "reasonCode": "UNDER_AGE"},
                    provenance={"type": "SYNTHETIC"},
                )
            ],
            "maker",
            lookup_snapshot_hashes=[snapshot.content_hash],
        )
        golden.submit(suite, "maker")
        golden.approve(suite, "checker")
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        lifecycle.submit(revision, "maker")
        lifecycle.approve(revision, "checker")
        session.commit()
        result = key, revision.revision, suite.revision
    engine.dispose()
    return result


def bearer(private_key: object, *, subject: str, roles: list[str]) -> dict[str, str]:
    now = datetime.now(UTC)
    encoded = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": subject,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "roles": roles,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "deployment-test"},
    )
    return {"Authorization": f"Bearer {encoded}"}


def test_mode_a_deployment_requires_oidc_deployer_and_rejects_dev_headers() -> None:
    key, revision, suite = prepare_release()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = SecuritySettings(
        oidc=OidcConfig(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url="https://idp.example.test/jwks",
            leeway_seconds=0,
        )
    )
    api = TestClient(
        create_app(
            security=settings,
            key_resolver=lambda token: private.public_key(),
        )
    )
    path = f"/mode-a/{key}/publications?decision_revision={revision}&suite_revision={suite}"
    header_attempt = api.post(path, headers={"X-BRP-Actor": "deployer"})
    assert header_attempt.status_code == 401
    assert header_attempt.json()["detail"] == "development identity headers are disabled"

    denied = api.post(path, headers=bearer(private, subject="maker", roles=["maker"]))
    assert denied.status_code == 403
    assert "deployer" in denied.json()["detail"]

    published = api.post(
        path,
        headers=bearer(private, subject="release-user", roles=["deployer"]),
    )
    assert published.status_code == 201, published.text
    assert published.json()["actor"] == "release-user"
    assert published.json()["action"] == "PUBLISH"
