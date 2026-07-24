"""Lightweight evidence-first Java repository bootstrap agent."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from brp.canonical_package.models import (
    BusinessScenario,
    CanonicalDecisionPackage,
    DecisionTable,
    DecisionTableRow,
    PackageEvidence,
    VocabularyField,
    VocabularyRole,
)
from brp.evidence.models import (
    EscalationRecommendation,
    EvidenceBundle,
    EvidenceSpan,
    FieldEvidence,
    RepositoryIdentity,
    TestEvidence,
    ToolTranscriptEntry,
)
from brp.evidence.repo_tools import RepositoryEvidenceTools, RepositoryToolError
from brp.ir.models import (
    HitPolicy,
    JavaSourceReference,
    JsonScalar,
    ProgramContext,
    ProgramKind,
    ScalarType,
    StrictModel,
)
from brp.llm.client import LlmClient


class EvidenceLinkProposal(StrictModel):
    evidence_id: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    span_id: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    summary: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class InferredDecisionTableRow(DecisionTableRow):
    """Extraction rows always carry source evidence and a model confidence."""

    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class InferredDecisionTable(StrictModel):
    decision_id: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    name: str = Field(min_length=1)
    hit_policy: HitPolicy
    input_fields: list[str] = Field(min_length=1)
    output_fields: list[str] = Field(min_length=1)
    rows: list[InferredDecisionTableRow] = Field(min_length=1)
    default_outcome: dict[str, JsonScalar] | None = None


class JavaAgentInference(StrictModel):
    hypothesis: str = Field(min_length=1)
    package_id: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    package_name: str = Field(min_length=1)
    product: str | None = None
    vocabulary: list[VocabularyField] = Field(min_length=1)
    decisions: list[InferredDecisionTable] = Field(min_length=1)
    business_scenarios: list[BusinessScenario] = Field(default_factory=list)
    evidence_links: list[EvidenceLinkProposal] = Field(min_length=1)
    field_evidence: list[FieldEvidence] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_calls: list[str] = Field(default_factory=list)
    alternative_interpretations: list[str] = Field(default_factory=list)
    escalation: EscalationRecommendation


class JavaAgentResult(StrictModel):
    package: CanonicalDecisionPackage
    evidence_bundle: EvidenceBundle


class LightweightJavaAgent:
    def __init__(self, client: LlmClient, *, max_spans: int = 12) -> None:
        if not 1 <= max_spans <= 30:
            raise ValueError("max_spans must be between 1 and 30")
        self.client = client
        self.max_spans = max_spans

    def extract(
        self,
        checkout: Path,
        *,
        repository_url: str,
        repository_alias: str,
        class_name: str,
        method: str,
        subpath: str = ".",
    ) -> JavaAgentResult:
        tools = RepositoryEvidenceTools(checkout)
        commit = tools.commit()
        transcript: list[ToolTranscriptEntry] = []
        files = tools.inventory(suffixes=(".java",), limit=5000)
        prefix = "" if subpath in {"", "."} else subpath.strip("/") + "/"
        if prefix:
            files = [file for file in files if file.startswith(prefix)]
        transcript.append(
            ToolTranscriptEntry(
                sequence=1,
                tool="inventory",
                request={"suffixes": [".java"], "limit": 5000},
                result_summary=f"found {len(files)} tracked Java files",
                truncated=len(files) == 5000,
            )
        )
        if not files:
            raise RepositoryToolError("repository contains no tracked Java files")

        simple_class = class_name.rsplit(".", 1)[-1]
        java_glob = "*.java" if not prefix else f"{prefix}**/*.java"
        class_matches = tools.search(f"class {simple_class}", glob=java_glob, limit=20)
        method_matches = tools.search(f"{method}(", glob=java_glob, limit=50)
        matches = _unique_matches(class_matches + method_matches)
        production_matches = [
            item for item in matches if not _is_test_file(str(item["file"]))
        ]
        if production_matches:
            matches = production_matches
        matches.sort(key=lambda item: (_is_test_file(str(item["file"])), str(item["file"])))
        transcript.append(
            ToolTranscriptEntry(
                sequence=2,
                tool="search",
                request={"class": simple_class, "method": method, "glob": java_glob},
                result_summary=f"found {len(matches)} entry-point matches",
            )
        )
        if not matches:
            raise RepositoryToolError("entry-point hint was not found in tracked Java source")

        spans: list[EvidenceSpan] = []
        for match in matches[: self.max_spans]:
            line = int(str(match["line"]))
            document = tools.read(
                str(match["file"]), line_start=max(1, line - 80), line_end=line + 160
            )
            _append_unique_span(spans, document)
        transcript.append(
            ToolTranscriptEntry(
                sequence=3,
                tool="read",
                request={"entryMatches": len(matches), "maxSpans": self.max_spans},
                result_summary=f"captured {len(spans)} bounded source spans",
                truncated=len(matches) > self.max_spans,
            )
        )

        tests = [file for file in files if _is_test_file(file)]
        relevant_tests = [
            file for file in tests if simple_class.lower() in Path(file).name.lower()
        ][:5]
        if not relevant_tests and len(tests) <= 5:
            # In a small repository, entry points are often exercised indirectly through
            # a facade whose test filename does not repeat the implementation class.
            relevant_tests = tests
        for file in relevant_tests:
            document = tools.read(file, line_start=1, line_end=300)
            _append_unique_span(spans, document)
        test_evidence = [
            TestEvidence(
                file=file,
                status="DISCOVERED",
                summary=(
                    "Tracked test file related to the entry-point class; "
                    "not executed during extraction"
                ),
            )
            for file in relevant_tests
        ]
        transcript.append(
            ToolTranscriptEntry(
                sequence=4,
                tool="search",
                request={"testClass": simple_class, "limit": 5},
                result_summary=f"captured {len(relevant_tests)} related test files",
            )
        )

        prompt = _prompt(
            repository_alias=repository_alias,
            class_name=class_name,
            method=method,
            spans=spans,
            include_schema=(
                getattr(self.client.provider, "response_format", "json_object")
                != "json_schema"
            ),
        )
        inference = self.client.generate(prompt, JavaAgentInference)
        transcript.append(
            ToolTranscriptEntry(
                sequence=5,
                tool="semantic",
                request={
                    "provider": self.client.provider.name,
                    "model": self.client.provider.model,
                },
                result_summary="received schema-valid candidate package and evidence links",
            )
        )

        span_map = {span.span_id: span for span in spans}
        package_evidence: list[PackageEvidence] = []
        for link in inference.evidence_links:
            if link.span_id not in span_map:
                raise RepositoryToolError(
                    f"agent evidence link references unavailable span: {link.span_id}"
                )
            span = span_map[link.span_id]
            package_evidence.append(
                PackageEvidence(
                    evidence_id=link.evidence_id,
                    summary=link.summary,
                    assumptions=link.assumptions,
                    unresolved=link.unresolved,
                    source_reference=JavaSourceReference(
                        type="JAVA_SOURCE",
                        repository=repository_alias,
                        revision=commit,
                        file=span.file,
                        line_start=span.line_start,
                        line_end=span.line_end,
                        symbol=f"{class_name}#{method}",
                    ),
                )
            )
        proposed_ids = {item.evidence_id for item in package_evidence}
        row_ids = {
            evidence_id
            for decision in inference.decisions
            for row in decision.rows
            for evidence_id in row.evidence_ids
        }
        if row_ids - proposed_ids:
            raise RepositoryToolError(
                f"candidate rows reference unavailable evidence: {sorted(row_ids - proposed_ids)}"
            )

        unresolved_calls = list(inference.unresolved_calls)
        vocabulary: list[VocabularyField] = []
        vocabulary_keys: set[str] = set()
        for field in inference.vocabulary:
            if field.key in vocabulary_keys:
                unresolved_calls.append(
                    f"Discarded duplicate inferred vocabulary key: {field.key}"
                )
                continue
            vocabulary_keys.add(field.key)
            vocabulary.append(field)
        field_types = {field.key: field.type for field in vocabulary}

        decisions: list[DecisionTable] = []
        for inferred_decision in inference.decisions:
            document = inferred_decision.model_dump(mode="python")
            for row in document["rows"]:
                row["outcomes"] = _coerce_decimal_mapping(
                    row["outcomes"], field_types
                )
                for condition in row["conditions"]:
                    condition["value"] = _coerce_decimal_value(
                        condition["value"], field_types.get(condition["field"])
                    )
            default_outcome = document.get("default_outcome")
            if isinstance(default_outcome, dict):
                default_outcome = _coerce_decimal_mapping(
                    default_outcome, field_types
                )
                document["default_outcome"] = default_outcome
            if inferred_decision.hit_policy is HitPolicy.COLLECT and default_outcome is not None:
                unresolved_calls.append(
                    f"Discarded forbidden COLLECT default for {inferred_decision.decision_id}"
                )
                document["default_outcome"] = None
            elif (
                inferred_decision.hit_policy is not HitPolicy.COLLECT
                and isinstance(default_outcome, dict)
                and set(default_outcome) != set(inferred_decision.output_fields)
            ):
                retained_outputs = [
                    field
                    for field in inferred_decision.output_fields
                    if field in default_outcome
                ]
                if retained_outputs:
                    discarded = sorted(
                        set(inferred_decision.output_fields) - set(retained_outputs)
                    )
                    unresolved_calls.append(
                        "Projected "
                        f"{inferred_decision.decision_id} to outputs with a complete default; "
                        f"discarded unsupported outputs: {', '.join(discarded)}"
                    )
                    document["output_fields"] = retained_outputs
                    document["default_outcome"] = {
                        key: default_outcome[key] for key in retained_outputs
                    }
                    for row in document["rows"]:
                        row["outcomes"] = {
                            key: row["outcomes"][key]
                            for key in retained_outputs
                            if key in row["outcomes"]
                        }
            decisions.append(DecisionTable.model_validate(document))

        input_keys = {
            field.key for field in vocabulary if field.role is VocabularyRole.INPUT
        }
        output_keys = {
            field.key for field in vocabulary if field.role is VocabularyRole.OUTPUT
        }
        business_scenarios: list[BusinessScenario] = []
        for scenario in inference.business_scenarios:
            if set(scenario.inputs) <= input_keys and set(scenario.expected) <= output_keys:
                scenario_document = scenario.model_dump(mode="python")
                scenario_document["inputs"] = _coerce_decimal_mapping(
                    scenario_document["inputs"], field_types
                )
                scenario_document["expected"] = _coerce_decimal_mapping(
                    scenario_document["expected"], field_types
                )
                business_scenarios.append(
                    BusinessScenario.model_validate(scenario_document)
                )
            else:
                unresolved_calls.append(
                    f"Discarded scenario with undeclared fields: {scenario.scenario_id}"
                )

        package = CanonicalDecisionPackage(
            package_id=inference.package_id,
            package_name=inference.package_name,
            profile="CANONICAL_DECISION_PACKAGE_V1",
            schema_version=1,
            product=inference.product,
            program_contexts=[
                ProgramContext(
                    program_id=repository_alias.upper().replace("-", "_"),
                    kind=ProgramKind.SERVICE,
                    entry_point=f"{class_name}#{method}",
                )
            ],
            vocabulary=vocabulary,
            decisions=decisions,
            business_scenarios=business_scenarios,
            evidence=package_evidence,
        )
        bundle = EvidenceBundle(
            bundle_id=f"bundle_{commit[:12]}",
            repository=RepositoryIdentity(
                repository_url=repository_url,
                commit=commit,
                subpath=subpath,
                entry_point_hypothesis=f"{class_name}#{method}",
            ),
            hypothesis=inference.hypothesis,
            spans=spans,
            field_evidence=inference.field_evidence,
            assumptions=inference.assumptions,
            unresolved_calls=unresolved_calls,
            alternative_interpretations=inference.alternative_interpretations,
            test_evidence=test_evidence,
            transcript=transcript,
            escalation=inference.escalation,
        )
        return JavaAgentResult(package=package, evidence_bundle=bundle)


def _unique_matches(matches: list[dict[str, object]]) -> list[dict[str, object]]:
    found: set[tuple[str, int]] = set()
    result: list[dict[str, object]] = []
    for match in matches:
        key = (str(match["file"]), int(str(match["line"])))
        if key not in found:
            found.add(key)
            result.append(match)
    return result


def _is_test_file(path: str) -> bool:
    lowered = path.lower()
    return "/test/" in lowered or lowered.endswith(("test.java", "tests.java"))


def _span(document: dict[str, object], number: int) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=f"span_{number}",
        file=str(document["file"]),
        line_start=int(str(document["lineStart"])),
        line_end=int(str(document["lineEnd"])),
        content_hash=str(document["contentHash"]),
        snippet=str(document["snippet"]),
    )


def _append_unique_span(
    spans: list[EvidenceSpan], document: dict[str, object]
) -> None:
    identity = (
        str(document["file"]),
        int(str(document["lineStart"])),
        int(str(document["lineEnd"])),
        str(document["contentHash"]),
    )
    if any(
        (span.file, span.line_start, span.line_end, span.content_hash) == identity
        for span in spans
    ):
        return
    spans.append(_span(document, len(spans) + 1))


def _coerce_decimal_mapping(
    values: dict[str, object], field_types: dict[str, ScalarType]
) -> dict[str, object]:
    return {
        key: _coerce_decimal_value(value, field_types.get(key))
        for key, value in values.items()
    }


def _coerce_decimal_value(value: object, field_type: ScalarType | None) -> object:
    if field_type is not ScalarType.DECIMAL:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, list):
        return [
            float(item) if isinstance(item, int) and not isinstance(item, bool) else item
            for item in value
        ]
    return value


def _prompt(
    *,
    repository_alias: str,
    class_name: str,
    method: str,
    spans: list[EvidenceSpan],
    include_schema: bool = True,
) -> str:
    evidence = [span.model_dump(mode="json", by_alias=True) for span in spans]
    schema_instruction = ""
    if include_schema:
        schema = JavaAgentInference.model_json_schema(by_alias=True)
        schema_instruction = (
            f"OUTPUT_SCHEMA={json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        )
    return (
        "You are extracting business decision candidates from bounded Java evidence. "
        "Return JSON only and obey the supplied schema. Never invent source spans, calls, "
        "types, tests, or business meaning. Return only candidate vocabulary, decision tables, "
        "business scenarios, and evidence links; deterministic code builds the canonical package. "
        "Use only identifier characters A-Z, a-z, 0-9, underscore, or dollar sign for "
        "packageId, decisionId, rowId, fieldId, evidenceId, and spanId; identifiers must "
        "start with a letter, underscore, or dollar sign. Every vocabulary key, decisionId, "
        "rowId, evidenceId, and field-evidence path MUST be unique; do not emit the same "
        "business field twice. Decision inputFields/outputFields and conditions/outcomes "
        "must reference those exact unique vocabulary keys. For FIRST or UNIQUE, defaultOutcome "
        "is required and must contain exactly one value for every declared outputField. For "
        "COLLECT, omit defaultOutcome. Return no more than five decision rows in total; "
        "summarize additional branches under unresolvedCalls rather than exhausting the "
        "response budget. Always "
        "include evidenceLinks, fieldEvidence, and escalation, even when other optional arrays "
        "are empty. Business-scenario inputs may use only vocabulary keys with INPUT role and "
        "expected values may use only vocabulary keys with OUTPUT role; omit a scenario if that "
        "mapping is uncertain. Every returned decision row is "
        "source-derived: it MUST contain at least one evidenceId linked to one supplied "
        "spanId and MUST contain numeric confidence from 0 to 1. Include per-field evidence. Mark "
        "ambiguity in unresolvedCalls or alternativeInterpretations. Raw Java expressions "
        "must not enter candidate fields or rows.\n"
        f"Repository alias: {repository_alias}\nEntry point: {class_name}#{method}\n"
        f"{schema_instruction}"
        f"EVIDENCE={json.dumps(evidence, ensure_ascii=False, sort_keys=True)}"
    )
