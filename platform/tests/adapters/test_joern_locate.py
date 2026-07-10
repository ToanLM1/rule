from pathlib import Path

from brp.adapters.joern import JoernLocator

ROOT = Path(__file__).resolve().parents[3]


def test_locate_pins_commit_and_reachable_private_helper() -> None:
    methods = JoernLocator(ROOT / "fixtures/legacy-enrollment", "legacy-enrollment").locate(
        "legacy.EnrollmentValidator", "evaluate"
    )
    assert [method.method for method in methods] == ["evaluate", "isRegionCovered"]
    assert all(len(method.revision) == 40 for method in methods)
    assert len({method.revision for method in methods}) == 1
    assert methods[0].entry_point is True
    assert methods[1].entry_point is False


def test_unreachable_unrelated_class_is_excluded() -> None:
    methods = JoernLocator(ROOT / "fixtures/legacy-enrollment", "legacy-enrollment").locate(
        "legacy.EnrollmentValidator", "evaluate"
    )
    assert all("UnrelatedUtil" not in method.file for method in methods)
    assert all(method.line_end >= method.line_start for method in methods)
