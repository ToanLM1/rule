import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "conformance"
OPERATORS = {
    "EQ",
    "NE",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "IN",
    "NOT_IN",
    "BETWEEN",
    "EXISTS",
    "STARTS_WITH",
}
HIT_POLICIES = {"FIRST", "UNIQUE", "COLLECT"}


def load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_every_operator_has_positive_and_negative_cases() -> None:
    cases = load("operator_cases.json")["cases"]
    assert isinstance(cases, list)
    for operator in OPERATORS:
        matching = [case for case in cases if case["operator"] == operator]
        assert {case["valid"] for case in matching} == {True, False}


def test_every_hit_policy_has_cases() -> None:
    cases = load("decision_cases.json")["cases"]
    assert isinstance(cases, list)
    assert {case["hitPolicy"] for case in cases} == HIT_POLICIES
    assert {case["valid"] for case in cases} == {True, False}


def test_fixture_decisions_cover_reference_decomposition_and_korean() -> None:
    fixture_names = {
        "enrollment_eligibility.json",
        "premium_adjustments.json",
        "required_documents.json",
    }
    documents = [load(name) for name in fixture_names]
    assert {document["decisionId"] for document in documents} == {
        "enrollment_eligibility",
        "premium_adjustments",
        "required_documents",
    }
    assert all("ENROLLMENT-API" in json.dumps(document) for document in documents)
    korean_documents = [json.dumps(document, ensure_ascii=False) for document in documents]
    assert any("가입 자격 판정" in document for document in korean_documents)


def test_corpus_covers_nesting_lookup_and_provenance_boundaries() -> None:
    cases = load("decision_cases.json")["cases"]
    assert isinstance(cases, list)
    ids = {case["id"] for case in cases}
    assert {
        "nested_depth_three",
        "nested_depth_four",
        "lookup_hit",
        "lookup_miss",
        "extracted_without_reference",
        "user_action_reference",
    }.issubset(ids)
