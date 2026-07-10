import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from brp.api.app import create_app
from brp.governance.diff import semantic_diff
from brp.ir.models import DecisionContent
from brp.repository.models import DecisionRevision

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "conformance" / "enrollment_eligibility.json"
)


class Evidence:
    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        del session, revision


def document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def model(value: dict[str, object]) -> DecisionContent:
    return DecisionContent.model_validate(value)


def test_equal_content_has_empty_diff() -> None:
    content = model(document())
    assert semantic_diff(content, content) == {
        "addedRules": [],
        "removedRules": [],
        "changedRules": [],
        "metadataChanges": [],
    }


def test_rule_value_and_korean_provenance_changes_have_stable_paths() -> None:
    before = document()
    after = copy.deepcopy(before)
    after["rules"][0]["when"]["all"][0]["right"]["value"] = 19
    after["rules"][0]["sourceReferences"][0]["symbol"] = "가입연령"
    result = semantic_diff(model(before), model(after))
    paths = {change["path"] for change in result["changedRules"][0]["fieldChanges"]}
    assert "/rules/R001/when/all" in paths
    assert "/rules/R001/sourceReferences" in paths


def test_added_removed_and_reordered_rules_are_explicit() -> None:
    before = document()
    after = copy.deepcopy(before)
    removed = after["rules"].pop(0)
    added = copy.deepcopy(removed)
    added["ruleId"] = "R099"
    after["rules"].append(added)
    result = semantic_diff(model(before), model(after))
    assert result["addedRules"] == ["R099"]
    assert result["removedRules"] == ["R001"]
    assert any(change["path"] == "/rules/order" for change in result["metadataChanges"])


def test_named_input_change_is_semantic_not_whole_document() -> None:
    before = document()
    after = copy.deepcopy(before)
    after["inputs"][0]["sourcePath"] = "applicant.age"
    result = semantic_diff(model(before), model(after))
    assert result["metadataChanges"] == [
        {
            "path": "/inputs/age/sourcePath",
            "before": "customer.age",
            "after": "applicant.age",
        }
    ]


def test_diff_route_compares_repository_revisions() -> None:
    api = TestClient(create_app(Evidence()))
    key = f"diff_{uuid4().hex}"
    before = document()
    created = api.post(
        "/decisions",
        json={
            "decisionKey": key,
            "content": before,
            "effectiveFrom": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
        },
        headers={"X-BRP-Actor": "maker-a"},
    )
    assert created.status_code == 201
    after = copy.deepcopy(before)
    after["rules"][0]["when"]["all"][0]["right"]["value"] = 19
    revised = api.post(
        f"/decisions/{key}/revisions",
        json={
            "content": after,
            "effectiveFrom": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
        },
        headers={"X-BRP-Actor": "maker-a"},
    )
    assert revised.status_code == 201
    response = api.get(f"/decisions/{key}/diff", params={"from": 1, "to": 2})
    assert response.status_code == 200
    assert response.json()["changedRules"][0]["ruleId"] == "R001"
