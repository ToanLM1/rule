from pathlib import Path

from brp.governance.consistency import compare_executors
from brp.ir.models import DecisionContent

FIXTURE = Path(__file__).parents[1] / "fixtures/conformance/premium_adjustments.json"


def content() -> DecisionContent:
    return DecisionContent.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


CASES = [
    {
        "caseKey": "smoker",
        "input": {"age": 30, "productCode": "CANCER_BASIC", "smoker": True},
    },
    {
        "caseKey": "senior-smoker",
        "input": {"age": 62, "productCode": "CANCER_BASIC", "smoker": True},
    },
]


def faithful(inputs):
    results = []
    if inputs["smoker"] and inputs["productCode"].startswith("CANCER"):
        results.append({"premiumLoadingPct": 20})
    if 60 <= inputs["age"] <= 65 and inputs["productCode"] == "CANCER_BASIC":
        results.append({"premiumLoadingPct": 30})
    return results


def test_consistent_executors_preserve_generated_java_authority() -> None:
    report = compare_executors(content(), CASES, faithful)
    assert report["divergences"] == []
    assert report["previewAuthority"] == "ADVISORY"
    assert report["authoritativeAuthority"] == "AUTHORITATIVE"


def test_planted_divergence_is_generator_or_export_defect() -> None:
    def divergent(inputs):
        return [{"premiumLoadingPct": 999}]

    report = compare_executors(content(), CASES, divergent)
    assert len(report["divergences"]) == 2
    assert report["defectCategory"] == "GENERATOR_OR_EXPORT_DEFECT"
    assert report["authoritativeAuthority"] == "AUTHORITATIVE"
