from brp.jobs import _candidate_storage_key


def test_candidate_storage_key_normalizes_model_identifiers() -> None:
    assert _candidate_storage_key("discountCalculation") == "discount_calculation"
    assert _candidate_storage_key("Discount-Eligibility") == "discount_eligibility"
    assert _candidate_storage_key("_42") == "decision_42"
