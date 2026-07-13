from pathlib import Path

from brp.adapters.joern import JoernLocator, JoernSlicer

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    "C1_UNDER_AGE",
    "C2_OVER_AGE_LIMIT",
    "C3_SMOKER_LOADING",
    "C4_REGION_LOOKUP",
    "C5_OCCUPATION_DOCUMENT",
    "C6_SENIOR_ADJUSTMENTS",
}


def manifest():
    methods = JoernLocator(ROOT / "fixtures/legacy-enrollment", "legacy-enrollment").locate(
        "legacy.EnrollmentValidator", "evaluate"
    )
    return JoernSlicer().slice(methods)


def test_all_six_constructs_are_covered_exactly_once_and_bounded() -> None:
    slices = manifest().slices
    assert {item.construct_id for item in slices} == EXPECTED
    assert len(slices) == len(EXPECTED)
    assert all(len(item.source.splitlines()) <= 120 for item in slices)
    assert [item.source_references[0].line_start for item in slices] == sorted(
        item.source_references[0].line_start for item in slices
    )


def test_jdbc_slice_includes_reachable_helper_and_immutable_references() -> None:
    item = next(item for item in manifest().slices if item.construct_id == "C4_REGION_LOOKUP")
    assert "SELECT eligible FROM region_eligibility" in item.source
    assert len(item.source_references) == 2
    assert all(reference.revision == manifest().revision for reference in item.source_references)
    assert item.source_references[0].line_start == 30
    assert item.source_references[1].line_start == 52
