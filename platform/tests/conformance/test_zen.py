from pathlib import Path

from brp.governance.zen import DictLookupResolver, preview
from brp.ir.models import DecisionContent

FIXTURES = Path(__file__).parent / "../fixtures/conformance"


def test_zen_matches_enrollment_boundary_cases() -> None:
    content = DecisionContent.model_validate_json(
        (FIXTURES / "enrollment_eligibility.json").read_text(encoding="utf-8")
    )
    cases = [
        (
            {"age": 17, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
            {"eligible": False, "reasonCode": "UNDER_AGE"},
        ),
        (
            {"age": 66, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
            {"eligible": False, "reasonCode": "OVER_AGE_LIMIT"},
        ),
    ]
    resolver = DictLookupResolver(
        {"lookup://region_eligibility": [{"region_code": "SEOUL", "eligible": True}]}
    )
    for inputs, expected in cases:
        assert preview(content, inputs, resolver)["result"] == expected
