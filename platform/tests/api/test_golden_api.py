import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from brp.api.app import create_app
from brp.repository.models import DecisionRevision
from brp.security import SecuritySettings

FIXTURE = Path(__file__).parents[1] / "fixtures/conformance/premium_adjustments.json"


class Evidence:
    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        del session, revision


def test_golden_api_names_advisory_executor_and_evidence() -> None:
    api = TestClient(create_app(Evidence(), security=SecuritySettings.local_development()))
    key = f"golden_api_{uuid4().hex}"
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    content["decisionId"] = key
    created = api.post(
        "/decisions",
        json={
            "decisionKey": key,
            "content": content,
            "effectiveFrom": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
        },
        headers={"X-BRP-Actor": "maker"},
    )
    assert created.status_code == 201
    suite = api.post(
        f"/golden-suites/{key}",
        json={
            "cases": [
                {
                    "caseKey": "smoker",
                    "input": {"age": 30, "productCode": "CANCER_BASIC", "smoker": True},
                    "expected": [{"premiumLoadingPct": 20}],
                    "provenance": {"type": "LEGACY_TEST", "id": "smoker"},
                }
            ]
        },
        headers={"X-BRP-Actor": "maker"},
    )
    assert suite.status_code == 201
    assert (
        api.post(f"/golden-suites/{key}/1/submit", headers={"X-BRP-Actor": "maker"}).status_code
        == 200
    )
    approved = api.post(f"/golden-suites/{key}/1/approve", headers={"X-BRP-Actor": "checker"})
    assert approved.status_code == 200
    run = api.post(
        f"/golden/{key}/run",
        params={
            "executor": "zen-advisory",
            "decision_revision": 1,
            "suite_revision": 1,
        },
    )
    assert run.status_code == 200
    assert run.json() == {
        "executor": "ZEN",
        "authority": "ADVISORY",
        "decisionRevision": 1,
        "suiteRevision": 1,
        "suiteHash": approved.json()["contentHash"],
        "lookupSnapshots": [],
        "passed": 1,
        "failed": 0,
        "cases": [
            {
                "caseKey": "smoker",
                "passed": True,
                "expected": [{"premiumLoadingPct": 20}],
                "actual": [{"premiumLoadingPct": 20}],
            }
        ],
    }


def test_mode_b_authority_is_reserved_for_generated_java() -> None:
    api = TestClient(create_app(Evidence(), security=SecuritySettings.local_development()))
    response = api.post(
        "/golden/anything/run",
        params={"executor": "generated-java", "decision_revision": 1, "suite_revision": 1},
    )
    assert response.status_code == 200
    assert response.json()["executor"] == "GENERATED_JAVA"
    assert response.json()["authority"] == "AUTHORITATIVE"
