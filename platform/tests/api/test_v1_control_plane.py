import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from brp.api.app import create_app
from brp.db import create_database_engine
from brp.ir.models import DecisionContent
from brp.repository.models import Site, Workspace
from brp.repository.service import RevisionRepository
from brp.security import SecuritySettings

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


def test_v1_pagination_is_site_scoped_and_concurrency_is_enforced() -> None:
    engine = create_database_engine()
    suffix = uuid4().hex
    workspace = Workspace(workspace_key=f"ws-{suffix}", name="Isolation workspace")
    first = Site(workspace=workspace, site_key="first", name="First site")
    second = Site(workspace=workspace, site_key="second", name="Second site")
    content = DecisionContent.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    key = f"isolated-{suffix}"
    with Session(engine) as session:
        session.add_all([workspace, first, second])
        session.flush()
        RevisionRepository(session, site_id=first.id).create_decision(
            key,
            content.model_copy(update={"decision_name": "First site decision"}),
            "maker-a",
            datetime(2026, 8, 1, tzinfo=UTC),
        )
        RevisionRepository(session, site_id=second.id).create_decision(
            key,
            content.model_copy(update={"decision_name": "Second site decision"}),
            "maker-a",
            datetime(2026, 8, 1, tzinfo=UTC),
        )
        session.commit()
        first_id, second_id = first.id, second.id
    engine.dispose()

    api = TestClient(create_app(security=SecuritySettings.local_development()))
    first_page = api.get("/api/v1/decisions", params={"site_id": first_id, "page_size": 1})
    second_page = api.get("/api/v1/decisions", params={"site_id": second_id, "page_size": 1})
    assert first_page.status_code == 200
    assert first_page.json()["total"] == 1
    assert first_page.json()["items"][0]["name"] == "First site decision"
    assert second_page.json()["items"][0]["name"] == "Second site decision"

    conflict = api.post(
        f"/api/v1/decisions/{key}/revisions",
        params={"site_id": first_id},
        headers={"X-BRP-Actor": "maker-a", "If-Match": '"99"'},
        json={
            "content": content.model_dump(mode="json", by_alias=True),
            "baseRevision": 1,
            "effectiveFrom": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        },
    )
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert conflict.json()["extensions"]["code"] == "WORKFLOW_CONFLICT"
    assert conflict.json()["extensions"]["correlationId"]
