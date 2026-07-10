"""Cross-executor divergence reporting without changing Mode-B authority."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from brp.governance.zen import LookupResolver, preview
from brp.ir.models import DecisionContent

GeneratedExecutor = Callable[[dict[str, Any]], object]


def compare_executors(
    content: DecisionContent,
    cases: list[dict[str, Any]],
    generated: GeneratedExecutor,
    resolver: LookupResolver | None = None,
) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    for case in cases:
        inputs = case["input"]
        advisory = preview(content, inputs, resolver)["result"]
        authoritative = generated(inputs)
        comparisons.append(
            {
                "caseKey": case["caseKey"],
                "consistent": advisory == authoritative,
                "zenAdvisory": advisory,
                "generatedJava": authoritative,
            }
        )
    divergences = [item for item in comparisons if not item["consistent"]]
    return {
        "previewExecutor": "ZEN",
        "previewAuthority": "ADVISORY",
        "authoritativeExecutor": "GENERATED_JAVA",
        "authoritativeAuthority": "AUTHORITATIVE",
        "defectCategory": "GENERATOR_OR_EXPORT_DEFECT" if divergences else None,
        "divergences": divergences,
        "cases": comparisons,
    }
