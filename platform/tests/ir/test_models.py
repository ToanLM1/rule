import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from brp.ir.models import DecisionContent

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "conformance"


def load(name: str = "enrollment_eligibility.json") -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture",
    ["enrollment_eligibility.json", "premium_adjustments.json", "required_documents.json"],
)
def test_fixture_decisions_parse(fixture: str) -> None:
    decision = DecisionContent.model_validate(load(fixture))
    assert decision.profile == "RULE_IR_V1"
    assert decision.model_dump(by_alias=True)["decisionName"]


@pytest.mark.parametrize("field,value", [("status", "APPROVED"), ("revision", 1)])
def test_repository_metadata_is_forbidden(field: str, value: object) -> None:
    document = load()
    document[field] = value
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DecisionContent.model_validate(document)


def test_first_requires_default_output() -> None:
    document = load()
    document.pop("defaultOutput")
    with pytest.raises(ValidationError, match="require defaultOutput"):
        DecisionContent.model_validate(document)


def test_collect_forbids_default_output() -> None:
    document = load("premium_adjustments.json")
    document["defaultOutput"] = {"premiumLoadingPct": 0}
    with pytest.raises(ValidationError, match="COLLECT forbids"):
        DecisionContent.model_validate(document)


def test_depth_four_is_rejected() -> None:
    document = load()
    condition = document["rules"][0]["when"]["all"][0]
    document["rules"][0]["when"] = {"all": [{"any": [{"all": [{"any": [condition]}]}]}]}
    with pytest.raises(ValidationError, match="exceeds condition depth 3"):
        DecisionContent.model_validate(document)


def test_extracted_rule_requires_reference_and_confidence() -> None:
    document = load()
    rule = document["rules"][0]
    rule["sourceReferences"] = []
    rule.pop("confidence")
    with pytest.raises(ValidationError, match="sourceReferences"):
        DecisionContent.model_validate(document)


def test_user_authored_rule_requires_user_action_and_omits_confidence() -> None:
    document = load()
    rule = document["rules"][0]
    rule["origin"] = "USER_AUTHORED"
    rule.pop("confidence")
    rule["sourceReferences"] = [
        {
            "type": "USER_ACTION",
            "actor": "maker-a",
            "at": datetime(2026, 7, 10, tzinfo=UTC).isoformat(),
            "reason": "가입 연령 변경",
        }
    ]
    parsed = DecisionContent.model_validate(document)
    assert parsed.rules[0].confidence is None


def test_user_authored_rule_rejects_non_action_only_provenance() -> None:
    document = load()
    rule = document["rules"][0]
    rule["origin"] = "USER_AUTHORED"
    rule.pop("confidence")
    with pytest.raises(ValidationError, match="USER_ACTION"):
        DecisionContent.model_validate(document)


def test_unknown_input_and_lookup_key_are_rejected() -> None:
    document = load()
    lookup = document["rules"][2]["when"]["all"][0]["left"]
    lookup["keys"] = {"wrong": {"kind": "INPUT", "name": "missing"}}
    with pytest.raises(ValidationError, match="keys do not match"):
        DecisionContent.model_validate(document)


def test_every_rule_assigns_every_output_once() -> None:
    document = load()
    document["rules"][0]["then"].pop()
    with pytest.raises(ValidationError, match="assign every output"):
        DecisionContent.model_validate(document)


def test_non_java_safe_logical_name_is_rejected() -> None:
    document = load()
    document["inputs"][0]["name"] = "customer.age"
    with pytest.raises(ValidationError, match="String should match pattern"):
        DecisionContent.model_validate(document)


def test_korean_is_not_normalized_or_lost() -> None:
    decision = DecisionContent.model_validate(load())
    assert decision.decision_name == "가입 자격 판정"


def minimal_operator_decision(case: dict[str, object]) -> dict[str, object]:
    right = {"kind": "LITERAL", "value": case.get("right")}
    condition: dict[str, object] = {
        "left": {"kind": "INPUT", "name": "value"},
        "operator": case["operator"],
    }
    if "right" in case:
        condition["right"] = right
    return {
        "decisionId": "operator_case",
        "decisionName": "연산자 검증",
        "profile": "RULE_IR_V1",
        "schemaVersion": 1,
        "programContexts": [
            {"programId": "TEST", "kind": "SERVICE", "entryPoint": "test.Operator"}
        ],
        "hitPolicy": "FIRST",
        "inputs": [{"name": "value", "type": case["leftType"], "required": True}],
        "outputs": [{"name": "matched", "type": "boolean"}],
        "defaultOutput": {"matched": False},
        "lookups": [],
        "rules": [
            {
                "ruleId": "R001",
                "when": {"all": [condition]},
                "then": [{"output": "matched", "value": True}],
                "origin": "EXTRACTED",
                "sourceReferences": [
                    {
                        "type": "JAVA_SOURCE",
                        "repository": "fixture",
                        "revision": "v1",
                        "file": "Operator.java",
                        "lineStart": 1,
                        "lineEnd": 1,
                    }
                ],
                "confidence": 1.0,
            }
        ],
    }


def test_copy_helper_does_not_mutate_fixture() -> None:
    original = load()
    changed = copy.deepcopy(original)
    changed["decisionName"] = "변경"
    assert original["decisionName"] == "가입 자격 판정"
