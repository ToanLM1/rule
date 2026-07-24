from datetime import UTC, datetime

from fastapi.testclient import TestClient

from brp.api.app import create_app
from brp.security import SecuritySettings
from tests.canonical_package.test_compiler import package_document


def test_compile_endpoint_returns_ir_without_opening_a_database_session() -> None:
    api = TestClient(create_app(security=SecuritySettings.local_development()))
    response = api.post(
        "/api/v1/canonical-packages/compile",
        headers={"X-BRP-Actor": "business-author"},
        json={
            "package": package_document(),
            "authoredAt": datetime(2026, 7, 23, tzinfo=UTC).isoformat(),
            "reason": "Policy update",
        },
    )
    assert response.status_code == 200
    assert response.json()["diagnostics"] == []
    assert response.json()["decisions"][0]["decisionName"] == "가입 자격"


def test_compile_endpoint_returns_actionable_diagnostics() -> None:
    document = package_document()
    document["decisions"][0]["rows"][0]["conditions"][0]["field"] = "missing"  # type: ignore[index]
    api = TestClient(create_app(security=SecuritySettings.local_development()))
    response = api.post(
        "/api/v1/canonical-packages/compile",
        headers={"X-BRP-Actor": "business-author"},
        json={
            "package": document,
            "authoredAt": datetime(2026, 7, 23, tzinfo=UTC).isoformat(),
            "reason": "Policy update",
        },
    )
    assert response.status_code == 200
    assert response.json()["decisions"] == []
    assert response.json()["diagnostics"][0] == {
        "severity": "ERROR",
        "path": "decisions[0].rows[0].conditions[0].field",
        "code": "UNKNOWN_INPUT",
        "message": "missing",
    }
