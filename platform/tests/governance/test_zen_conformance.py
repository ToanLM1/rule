import json
from pathlib import Path

import pytest

from brp.governance.zen import DictLookupResolver, UniqueHitPolicyError, export_jdm, preview
from brp.ir.models import DecisionContent

FIXTURES = Path(__file__).parents[1] / "fixtures/conformance"


def decision(name: str) -> DecisionContent:
    return DecisionContent.model_validate_json(
        (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    )


def test_export_is_pure_deterministic_jdm() -> None:
    content = decision("premium_adjustments")
    first = export_jdm(content)
    second = export_jdm(content)
    assert json.dumps(first.document, sort_keys=True) == json.dumps(second.document, sort_keys=True)
    assert first.document["nodes"][1]["content"]["hitPolicy"] == "collect"


def test_first_preview_is_advisory_and_resolves_lookup_snapshot() -> None:
    content = decision("enrollment_eligibility")
    resolver = DictLookupResolver(
        {"lookup://region_eligibility": [{"region_code": "SEOUL", "eligible": True}]}
    )
    result = preview(
        content,
        {"age": 30, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
        resolver,
    )
    assert result == {
        "executor": "ZEN",
        "authority": "ADVISORY",
        "result": {"eligible": True, "reasonCode": "ELIGIBLE"},
    }


def test_collect_operators_and_korean_values() -> None:
    documents = preview(
        decision("required_documents"),
        {"age": 62, "productCode": "CANCER_BASIC", "occupationClass": 4},
    )
    assert documents["authority"] == "ADVISORY"
    assert documents["result"] == [
        {"requiredDoc": "DOC_HEALTH_CHECK"},
        {"requiredDoc": "DOC_HEALTH_CHECK"},
    ]


def test_unique_collision_is_not_silently_first() -> None:
    document = json.loads((FIXTURES / "premium_adjustments.json").read_text(encoding="utf-8"))
    document["hitPolicy"] = "UNIQUE"
    document["defaultOutput"] = {"premiumLoadingPct": 0}
    content = DecisionContent.model_validate(document)
    with pytest.raises(UniqueHitPolicyError):
        preview(content, {"age": 62, "productCode": "CANCER_BASIC", "smoker": True})
