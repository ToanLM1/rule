import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from brp.canonical_package import compile_package
from brp.evidence import LightweightJavaAgent, RepositoryToolError
from brp.llm.client import LlmClient, MockProvider
from tests.canonical_package.test_compiler import package_document
from tests.evidence.test_repo_tools import repository


def inference_document(*, span_id: str = "span_1") -> dict[str, object]:
    package = package_document()
    return {
        "hypothesis": "Age controls eligibility in Policy.eligible",
        "packageId": package["packageId"],
        "packageName": package["packageName"],
        "product": package["product"],
        "vocabulary": package["vocabulary"],
        "decisions": package["decisions"],
        "businessScenarios": package["businessScenarios"],
        "evidenceLinks": [
            {
                "evidenceId": "source_age",
                "spanId": span_id,
                "summary": "The return expression compares age with the minimum",
            }
        ],
        "fieldEvidence": [
            {
                "fieldPath": "decisions[0].rows[0].conditions[0]",
                "spanIds": [span_id],
                "confidence": 0.9,
                "explanation": "The age comparison supports the condition",
            }
        ],
        "assumptions": ["The method result represents eligibility"],
        "unresolvedCalls": [],
        "alternativeInterpretations": [],
        "escalation": {"tier": "HUMAN", "reason": "Business labels require confirmation"},
    }


def run_agent(root: Path, document: dict[str, object]):
    agent = LightweightJavaAgent(LlmClient(MockProvider([json.dumps(document)])))
    return agent.extract(
        root,
        repository_url="https://github.com/example/dummy-rules",
        repository_alias="dummy-rules",
        class_name="sample.Policy",
        method="eligible",
    )


def test_agent_builds_package_and_auditable_bundle_without_joern(tmp_path: Path) -> None:
    result = run_agent(repository(tmp_path), inference_document())
    assert result.evidence_bundle.repository.commit
    assert [entry.tool for entry in result.evidence_bundle.transcript] == [
        "inventory",
        "search",
        "read",
        "search",
        "semantic",
    ]
    assert result.evidence_bundle.spans[0].file.endswith("Policy.java")
    assert result.package.evidence[0].source_reference.type == "JAVA_SOURCE"
    compiled = compile_package(
        result.package,
        actor="reviewer",
        authored_at=result.package.authored_at or datetime(2026, 7, 23, tzinfo=UTC),
        reason="Confirmed from evidence",
    )
    assert compiled.valid is True


def test_agent_rejects_model_links_to_unavailable_spans(tmp_path: Path) -> None:
    with pytest.raises(RepositoryToolError, match="unavailable span"):
        run_agent(repository(tmp_path), inference_document(span_id="span_999"))


def test_agent_discards_invalid_optional_inference_and_records_uncertainty(
    tmp_path: Path,
) -> None:
    document = inference_document()
    vocabulary = document["vocabulary"]
    decisions = document["decisions"]
    scenarios = document["businessScenarios"]
    assert isinstance(vocabulary, list)
    assert isinstance(decisions, list)
    assert isinstance(scenarios, list)
    vocabulary.append(dict(vocabulary[0]))
    decisions[0]["defaultOutcome"] = {"eligible": True}
    scenarios[0]["inputs"] = {"unknown_input": 20}

    result = run_agent(repository(tmp_path), document)

    assert [item.key for item in result.package.vocabulary].count("age") == 1
    assert result.package.decisions[0].output_fields == ["eligible"]
    assert result.package.decisions[0].default_outcome == {"eligible": True}
    assert result.package.business_scenarios == []
    unresolved = result.evidence_bundle.unresolved_calls
    assert any("duplicate inferred vocabulary" in item for item in unresolved)
    assert any("discarded unsupported outputs" in item for item in unresolved)
    assert any("scenario with undeclared fields" in item for item in unresolved)
    assert compile_package(
        result.package,
        actor="reviewer",
        authored_at=datetime(2026, 7, 23, tzinfo=UTC),
        reason="Review conservative projection",
    ).valid


def test_agent_fails_explicitly_when_entry_point_is_missing(tmp_path: Path) -> None:
    root = repository(tmp_path)
    agent = LightweightJavaAgent(LlmClient(MockProvider([json.dumps(inference_document())])))
    with pytest.raises(RepositoryToolError, match="entry-point hint"):
        agent.extract(
            root,
            repository_url="https://github.com/example/dummy-rules",
            repository_alias="dummy-rules",
            class_name="sample.Unknown",
            method="missing",
        )
