import json
from pathlib import Path

import pytest

from brp.benchmark import (
    BenchmarkManifest,
    BenchmarkPolicyError,
    MiningPrediction,
    ProviderPolicy,
    run_benchmark,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/benchmark"


def manifest() -> BenchmarkManifest:
    return BenchmarkManifest.model_validate_json(
        (FIXTURES / "synthetic-v1.json").read_text(encoding="utf-8")
    )


def policy() -> ProviderPolicy:
    return ProviderPolicy.model_validate_json(
        (FIXTURES / "provider-policy-v1.json").read_text(encoding="utf-8")
    )


def predictions() -> list[MiningPrediction]:
    return [
        MiningPrediction(
            slice_id="slice-enrollment",
            construct_ids=["C1_BOUNDARY", "C2_LOOKUP", "C9_SPURIOUS"],
            input_tokens=100,
            output_tokens=30,
            latency_ms=12.5,
            cost_usd=0.001,
        ),
        MiningPrediction(
            slice_id="slice-premium",
            construct_ids=["C3_AGGREGATE"],
            input_tokens=80,
            output_tokens=20,
            latency_ms=20,
            cost_usd=0.0008,
        ),
    ]


def test_synthetic_metrics_are_reproducible_labeled_and_diagnostic() -> None:
    first = run_benchmark(
        manifest(),
        predictions(),
        provider="mock",
        model="recorded-v1",
        provider_policy=policy(),
    )
    second = run_benchmark(
        manifest(),
        list(reversed(predictions())),
        provider="mock",
        model="recorded-v1",
        provider_policy=policy(),
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["evidenceLabel"] == "SYNTHETIC_NON_CUSTOMER"
    assert first["micro"] == {
        "truePositive": 3,
        "falsePositive": 1,
        "falseNegative": 0,
        "precision": 0.75,
        "recall": 1.0,
        "f1": 0.857143,
    }
    assert first["usage"] == {
        "inputTokens": 180,
        "outputTokens": 50,
        "costUsd": 0.0018,
        "latencyMsTotal": 32.5,
        "latencyMsMean": 16.25,
        "latencyMsP95": 20,
    }
    spurious = next(item for item in first["perConstruct"] if item["constructId"] == "C9_SPURIOUS")
    assert spurious["spuriousSlices"] == ["slice-enrollment"]


def test_real_customer_run_fails_closed_without_approval_and_policy() -> None:
    document = manifest().model_dump(mode="json", by_alias=True)
    document["classification"] = "REAL_CUSTOMER"
    real = BenchmarkManifest.model_validate(document)
    real_policy = ProviderPolicy.model_validate(
        {
            "schemaVersion": 1,
            "policyId": "customer-policy",
            "revision": "1",
            "rules": [
                {
                    "provider": "approved-provider",
                    "models": ["approved-model"],
                    "classifications": ["REAL_CUSTOMER"],
                }
            ],
        }
    )
    with pytest.raises(BenchmarkPolicyError, match="approval metadata"):
        run_benchmark(
            real,
            predictions(),
            provider="approved-provider",
            model="approved-model",
            provider_policy=real_policy,
        )
    with pytest.raises(BenchmarkPolicyError, match="provider policy"):
        run_benchmark(
            real,
            predictions(),
            provider="approved-provider",
            model="approved-model",
            provider_policy=None,
        )


def test_policy_denial_and_slice_mismatch_fail_before_claiming_metrics() -> None:
    with pytest.raises(BenchmarkPolicyError, match="not allowed"):
        run_benchmark(
            manifest(),
            predictions(),
            provider="foreign-provider",
            model="unknown",
            provider_policy=policy(),
        )
    with pytest.raises(ValueError, match="slice mismatch"):
        run_benchmark(
            manifest(),
            predictions()[:1],
            provider="mock",
            model="recorded-v1",
            provider_policy=policy(),
        )
