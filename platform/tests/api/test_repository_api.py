import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from brp.api.app import create_app
from brp.repository.models import DecisionRevision

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


class Evidence:
    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        del session, revision


def client() -> TestClient:
    return TestClient(create_app(Evidence()))


def content() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def create_body(key: str) -> dict[str, object]:
    return {
        "decisionKey": key,
        "content": content(),
        "effectiveFrom": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
    }


def unique_key() -> str:
    return f"api_{uuid4().hex}"


def test_write_requires_actor_but_reads_do_not() -> None:
    api = client()
    key = unique_key()
    missing = api.post("/decisions", json=create_body(key))
    assert missing.status_code == 400
    assert missing.headers["content-type"].startswith("application/problem+json")

    created = api.post("/decisions", json=create_body(key), headers={"X-BRP-Actor": "maker-a"})
    assert created.status_code == 201
    assert api.get(f"/decisions/{key}").status_code == 200


def test_content_and_lifecycle_envelope_are_separate_and_korean_survives() -> None:
    api = client()
    key = unique_key()
    response = api.post("/decisions", json=create_body(key), headers={"X-BRP-Actor": "maker-a"})
    payload = response.json()
    assert payload["envelope"]["lifecycleStatus"] == "DRAFT"
    assert payload["envelope"]["revision"] == 1
    assert payload["content"]["decisionName"] == "가입 자격 판정"
    assert "status" not in payload["content"]
    assert "revision" not in payload["content"]


def test_new_revision_is_server_numbered() -> None:
    api = client()
    key = unique_key()
    api.post("/decisions", json=create_body(key), headers={"X-BRP-Actor": "maker-a"})
    response = api.post(
        f"/decisions/{key}/revisions",
        json={
            "content": content(),
            "effectiveFrom": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        },
        headers={"X-BRP-Actor": "maker-a"},
    )
    assert response.status_code == 201
    assert response.json()["envelope"]["revision"] == 2


def test_maker_checker_and_effective_resolution() -> None:
    api = client()
    key = unique_key()
    created = api.post("/decisions", json=create_body(key), headers={"X-BRP-Actor": "maker-a"})
    assert created.status_code == 201
    path = f"/decisions/{key}/revisions/1"
    submitted = api.post(f"{path}/submit", headers={"X-BRP-Actor": "maker-a"})
    assert submitted.status_code == 200
    self_approval = api.post(f"{path}/approve", headers={"X-BRP-Actor": "maker-a"})
    assert self_approval.status_code == 403
    approved = api.post(f"{path}/approve", headers={"X-BRP-Actor": "checker-b"})
    assert approved.status_code == 200
    assert approved.json()["envelope"]["lifecycleStatus"] == "APPROVED"

    at = datetime(2026, 8, 15, tzinfo=UTC).isoformat()
    resolved = api.get(f"/decisions/{key}", params={"as_of": at})
    assert resolved.status_code == 200
    assert resolved.json()["envelope"]["revision"] == 1


def test_audit_is_readable_without_actor() -> None:
    api = client()
    key = unique_key()
    api.post("/decisions", json=create_body(key), headers={"X-BRP-Actor": "maker-a"})
    api.post(
        f"/decisions/{key}/revisions/1/submit",
        headers={"X-BRP-Actor": "maker-a"},
    )
    response = api.get(f"/decisions/{key}/audit")
    assert response.status_code == 200
    assert [event["action"] for event in response.json()] == ["CREATE_REVISION", "SUBMIT"]
