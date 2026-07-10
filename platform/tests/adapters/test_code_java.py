from pathlib import Path

import yaml

from brp.adapters.code_java import CONSTRUCT_RULES, JavaRuleMiner, collapse_rules
from brp.adapters.joern import JoernLocator, JoernSlicer

ROOT = Path(__file__).resolve().parents[3]


def mined():
    methods = JoernLocator(ROOT / "fixtures/legacy-enrollment", "legacy-enrollment").locate(
        "legacy.EnrollmentValidator", "evaluate"
    )
    manifest = JoernSlicer().slice(methods)
    return manifest, JavaRuleMiner(ROOT / "platform/tests/fixtures/conformance").mine(
        manifest, unsupported_fragments=["result.applyUnknown(request)"]
    )


def test_recorded_mining_matches_expected_construct_decomposition() -> None:
    manifest, batch = mined()
    expected = yaml.safe_load(
        (ROOT / "fixtures/legacy-enrollment/expected-decisions.yaml").read_text(encoding="utf-8")
    )
    assert {item["id"] for item in expected["constructs"]} == set(CONSTRUCT_RULES)
    assert {decision.decision_key for decision in batch.decisions} == {
        "enrollment_eligibility",
        "premium_adjustments",
        "required_documents",
    }
    references = [
        reference
        for decision in batch.decisions
        for rule in decision.content.rules
        for reference in rule.source_references
    ]
    assert all(reference.revision == manifest.revision for reference in references)
    assert all(reference.file.endswith("EnrollmentValidator.java") for reference in references)
    assert any(
        condition.operator == "STARTS_WITH"
        for decision in batch.decisions
        for rule in decision.content.rules
        for condition in (rule.when.all or [])
        if hasattr(condition, "operator")
    )
    assert any(
        getattr(condition.left, "kind", None) == "LOOKUP_FIELD"
        for decision in batch.decisions
        for rule in decision.content.rules
        for condition in (rule.when.all or [])
        if hasattr(condition, "left")
    )


def test_unsupported_call_reaches_review_queue_contract() -> None:
    _, batch = mined()
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_RAW_CALL"
    assert batch.unmappable[0].raw_fragment == "result.applyUnknown(request)"


def test_duplicate_rules_collapse_without_collapsing_provenance() -> None:
    _, batch = mined()
    rule = batch.decisions[0].content.rules[0]
    duplicate = rule.model_copy(deep=True)
    duplicate.source_references = batch.decisions[1].content.rules[0].source_references
    collapsed = collapse_rules([rule, duplicate])
    assert len(collapsed) == 1
    assert len(collapsed[0].source_references) == 2
