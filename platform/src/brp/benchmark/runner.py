"""Deterministic benchmark scoring with fail-closed data/provider policy."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from brp.benchmark.models import (
    BenchmarkManifest,
    DataClassification,
    MiningPrediction,
    ProviderPolicy,
)


class BenchmarkPolicyError(PermissionError):
    pass


def run_benchmark(
    manifest: BenchmarkManifest,
    predictions: list[MiningPrediction],
    *,
    provider: str,
    model: str,
    provider_policy: ProviderPolicy | None,
) -> dict[str, Any]:
    _authorize(manifest, provider, model, provider_policy)
    expected_ids = {item.slice_id for item in manifest.slices}
    predicted_ids = [item.slice_id for item in predictions]
    if len(predicted_ids) != len(set(predicted_ids)):
        raise ValueError("one prediction per slice is required")
    if set(predicted_ids) != expected_ids:
        missing = sorted(expected_ids - set(predicted_ids))
        extra = sorted(set(predicted_ids) - expected_ids)
        raise ValueError(f"prediction slice mismatch: missing={missing}, extra={extra}")

    prediction_by_slice = {item.slice_id: item for item in predictions}
    truth_pairs: set[tuple[str, str]] = set()
    predicted_pairs: set[tuple[str, str]] = set()
    for item in manifest.slices:
        truth_pairs.update((item.slice_id, construct.construct_id) for construct in item.constructs)
        predicted_pairs.update(
            (item.slice_id, construct_id)
            for construct_id in prediction_by_slice[item.slice_id].construct_ids
        )
    true_positive = truth_pairs & predicted_pairs
    false_positive = predicted_pairs - truth_pairs
    false_negative = truth_pairs - predicted_pairs
    precision, recall, f1 = _scores(len(true_positive), len(false_positive), len(false_negative))
    constructs = sorted({pair[1] for pair in truth_pairs | predicted_pairs})
    per_construct: list[dict[str, Any]] = []
    for construct_id in constructs:
        truth = {pair for pair in truth_pairs if pair[1] == construct_id}
        predicted = {pair for pair in predicted_pairs if pair[1] == construct_id}
        tp = len(truth & predicted)
        fp = len(predicted - truth)
        fn = len(truth - predicted)
        item_precision, item_recall, item_f1 = _scores(tp, fp, fn)
        per_construct.append(
            {
                "constructId": construct_id,
                "truePositive": tp,
                "falsePositive": fp,
                "falseNegative": fn,
                "precision": item_precision,
                "recall": item_recall,
                "f1": item_f1,
                "missedSlices": sorted(pair[0] for pair in truth - predicted),
                "spuriousSlices": sorted(pair[0] for pair in predicted - truth),
            }
        )

    latencies = sorted(item.latency_ms for item in predictions)
    policy = provider_policy
    assert policy is not None
    return {
        "schemaVersion": 1,
        "benchmarkId": manifest.benchmark_id,
        "benchmarkRevision": manifest.revision,
        "classification": manifest.classification.value,
        "evidenceLabel": manifest.classification.value,
        "manifestHash": _hash(manifest.model_dump(mode="json", by_alias=True)),
        "providerPolicyHash": _hash(policy.model_dump(mode="json", by_alias=True)),
        "provider": provider,
        "model": model,
        "sliceCount": len(manifest.slices),
        "micro": {
            "truePositive": len(true_positive),
            "falsePositive": len(false_positive),
            "falseNegative": len(false_negative),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "perConstruct": per_construct,
        "usage": {
            "inputTokens": sum(item.input_tokens for item in predictions),
            "outputTokens": sum(item.output_tokens for item in predictions),
            "costUsd": round(sum(item.cost_usd for item in predictions), 8),
            "latencyMsTotal": round(sum(latencies), 3),
            "latencyMsMean": round(sum(latencies) / len(latencies), 3),
            "latencyMsP95": round(latencies[math.ceil(len(latencies) * 0.95) - 1], 3),
        },
    }


def _authorize(
    manifest: BenchmarkManifest,
    provider: str,
    model: str,
    policy: ProviderPolicy | None,
) -> None:
    if policy is None:
        raise BenchmarkPolicyError("an explicit provider policy is required")
    if not policy.allows(provider, model, manifest.classification):
        raise BenchmarkPolicyError("provider/model is not allowed for this data classification")
    if manifest.classification is DataClassification.REAL_CUSTOMER:
        approval = manifest.approval
        if approval is None:
            raise BenchmarkPolicyError("REAL_CUSTOMER benchmark requires approval metadata")
        if approval.scope_hash != benchmark_scope_hash(manifest):
            raise BenchmarkPolicyError("customer approval scope hash does not match benchmark")
        if provider not in approval.allowed_providers:
            raise BenchmarkPolicyError("customer approval does not allow this provider")


def benchmark_scope_hash(manifest: BenchmarkManifest) -> str:
    scope = {
        "benchmarkId": manifest.benchmark_id,
        "revision": manifest.revision,
        "classification": manifest.classification.value,
        "slices": [item.model_dump(mode="json", by_alias=True) for item in manifest.slices],
    }
    return _hash(scope)


def _scores(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def _hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()
