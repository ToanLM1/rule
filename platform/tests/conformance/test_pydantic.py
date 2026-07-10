import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from brp.ir.models import DecisionContent
from tests.ir.test_models import minimal_operator_decision

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "conformance"


def operator_cases() -> list[dict[str, object]]:
    document = json.loads((FIXTURES / "operator_cases.json").read_text(encoding="utf-8"))
    return document["cases"]


@pytest.mark.parametrize("case", operator_cases(), ids=lambda case: str(case["id"]))
def test_operator_case(case: dict[str, object]) -> None:
    decision = minimal_operator_decision(case)
    if case["valid"]:
        DecisionContent.model_validate(decision)
    else:
        with pytest.raises(ValidationError):
            DecisionContent.model_validate(decision)
