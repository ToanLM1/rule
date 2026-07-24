"""Pure deterministic Canonical Decision Package to Rule IR compiler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from brp.canonical_package.models import (
    CanonicalDecisionPackage,
    DecisionTable,
    PackageEvidence,
    VocabularyField,
    VocabularyRole,
)
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DecisionContent,
    InputDefinition,
    InputOperand,
    JsonValue,
    LiteralOperand,
    LookupDefinition,
    Operator,
    OutputDefinition,
    Rule,
    RuleOrigin,
    StrictModel,
    UserActionReference,
)


class PackageDiagnostic(StrictModel):
    severity: Literal["ERROR"] = "ERROR"
    path: str
    code: str
    message: str


class PackageCompilation(StrictModel):
    decisions: list[DecisionContent]
    diagnostics: list[PackageDiagnostic]

    @property
    def valid(self) -> bool:
        return not self.diagnostics


def compile_package(
    package: CanonicalDecisionPackage,
    *,
    actor: str,
    authored_at: datetime,
    reason: str,
) -> PackageCompilation:
    diagnostics: list[PackageDiagnostic] = []
    fields = _unique_by_key(package.vocabulary, "vocabulary", diagnostics)
    evidence = _unique_by_key(package.evidence, "evidence", diagnostics, key="evidence_id")
    decisions = _unique_by_key(package.decisions, "decisions", diagnostics, key="decision_id")
    _validate_composition(package, decisions, diagnostics)
    _validate_scenarios(package, fields, evidence, diagnostics)
    if diagnostics:
        return PackageCompilation(decisions=[], diagnostics=diagnostics)

    compiled: list[DecisionContent] = []
    for index, decision in enumerate(package.decisions):
        candidate = _compile_decision(
            package,
            decision,
            fields,
            evidence,
            actor=actor,
            authored_at=authored_at,
            reason=reason,
            diagnostics=diagnostics,
            decision_index=index,
        )
        if candidate is not None:
            compiled.append(candidate)
    if diagnostics:
        return PackageCompilation(decisions=[], diagnostics=diagnostics)
    return PackageCompilation(decisions=compiled, diagnostics=[])


def _compile_decision(
    package: CanonicalDecisionPackage,
    decision: DecisionTable,
    fields: dict[str, VocabularyField],
    evidence: dict[str, PackageEvidence],
    *,
    actor: str,
    authored_at: datetime,
    reason: str,
    diagnostics: list[PackageDiagnostic],
    decision_index: int,
) -> DecisionContent | None:
    path = f"decisions[{decision_index}]"
    inputs = _resolve_fields(decision.input_fields, fields, VocabularyRole.INPUT, path, diagnostics)
    outputs = _resolve_fields(
        decision.output_fields, fields, VocabularyRole.OUTPUT, path, diagnostics
    )
    if len(set(decision.input_fields)) != len(decision.input_fields):
        _error(diagnostics, f"{path}.inputFields", "DUPLICATE_FIELD", "duplicate input field")
    if len(set(decision.output_fields)) != len(decision.output_fields):
        _error(diagnostics, f"{path}.outputFields", "DUPLICATE_FIELD", "duplicate output field")

    rules: list[Rule] = []
    seen_rows: set[str] = set()
    for row_index, row in enumerate(decision.rows):
        row_path = f"{path}.rows[{row_index}]"
        if row.row_id in seen_rows:
            _error(diagnostics, f"{row_path}.rowId", "DUPLICATE_ROW", row.row_id)
        seen_rows.add(row.row_id)
        for condition_index, condition in enumerate(row.conditions):
            field = fields.get(condition.field)
            if field is None or field.role is not VocabularyRole.INPUT:
                _error(
                    diagnostics,
                    f"{row_path}.conditions[{condition_index}].field",
                    "UNKNOWN_INPUT",
                    condition.field,
                )
        if set(row.outcomes) != set(decision.output_fields):
            _error(
                diagnostics,
                f"{row_path}.outcomes",
                "OUTCOME_FIELDS_MISMATCH",
                "row must assign every declared output exactly once",
            )
        missing_evidence = [item for item in row.evidence_ids if item not in evidence]
        if missing_evidence:
            _error(
                diagnostics,
                f"{row_path}.evidenceIds",
                "UNKNOWN_EVIDENCE",
                ", ".join(missing_evidence),
            )
        if diagnostics:
            continue
        source_references = [
            evidence[evidence_id].source_reference for evidence_id in row.evidence_ids
        ]
        origin = RuleOrigin.EXTRACTED if source_references else RuleOrigin.USER_AUTHORED
        if not source_references:
            source_references = [
                UserActionReference(type="USER_ACTION", actor=actor, at=authored_at, reason=reason)
            ]
        rules.append(
            Rule(
                rule_id=row.row_id,
                when=ConditionGroup(
                    all=[
                        Condition(
                            left=InputOperand(kind="INPUT", name=condition.field),
                            operator=condition.operator,
                            right=(
                                None
                                if condition.operator is Operator.EXISTS
                                else LiteralOperand(
                                    kind="LITERAL", value=_required_value(condition.value)
                                )
                            ),
                        )
                        for condition in row.conditions
                    ]
                ),
                then=[Action(output=name, value=value) for name, value in row.outcomes.items()],
                origin=origin,
                source_references=source_references,
                confidence=row.confidence,
            )
        )

    if decision.hit_policy.value != "COLLECT":
        if decision.default_outcome is None or set(decision.default_outcome) != set(
            decision.output_fields
        ):
            _error(
                diagnostics,
                f"{path}.defaultOutcome",
                "DEFAULT_OUTCOME_REQUIRED",
                "FIRST and UNIQUE require every declared output",
            )
    elif decision.default_outcome is not None:
        _error(
            diagnostics,
            f"{path}.defaultOutcome",
            "DEFAULT_OUTCOME_FORBIDDEN",
            "COLLECT forbids a default outcome",
        )
    if diagnostics:
        return None
    try:
        return DecisionContent(
            decision_id=decision.decision_id,
            decision_name=decision.name,
            profile="RULE_IR_V1",
            schema_version=1,
            product=package.product,
            program_contexts=package.program_contexts,
            hit_policy=decision.hit_policy,
            inputs=[
                InputDefinition(
                    name=field.key,
                    type=field.type,
                    required=field.required,
                    source_path=field.source_path,
                )
                for field in inputs
            ],
            outputs=[OutputDefinition(name=field.key, type=field.type) for field in outputs],
            default_output=decision.default_outcome,
            lookups=[
                LookupDefinition(name=item.name, ref=item.ref, keys=item.keys, outputs=item.outputs)
                for item in package.lookups
            ],
            rules=rules,
        )
    except ValidationError as exc:
        for error in exc.errors(include_url=False):
            location = ".".join(str(item) for item in error["loc"])
            _error(
                diagnostics,
                f"{path}.{location}" if location else path,
                "IR_VALIDATION",
                str(error["msg"]),
            )
        return None


def _resolve_fields(
    names: list[str],
    fields: dict[str, VocabularyField],
    role: VocabularyRole,
    path: str,
    diagnostics: list[PackageDiagnostic],
) -> list[VocabularyField]:
    resolved: list[VocabularyField] = []
    for index, name in enumerate(names):
        field = fields.get(name)
        if field is None or field.role is not role:
            field_path = "inputFields" if role is VocabularyRole.INPUT else "outputFields"
            _error(
                diagnostics,
                f"{path}.{field_path}[{index}]",
                f"UNKNOWN_{role.value}",
                name,
            )
        else:
            resolved.append(field)
    return resolved


def _validate_composition(
    package: CanonicalDecisionPackage,
    decisions: Mapping[str, object],
    diagnostics: list[PackageDiagnostic],
) -> None:
    for index, step in enumerate(package.composition):
        unknown = [decision for decision in step.decisions if decision not in decisions]
        if unknown:
            _error(
                diagnostics,
                f"composition[{index}].decisions",
                "UNKNOWN_DECISION",
                ", ".join(unknown),
            )


def _validate_scenarios(
    package: CanonicalDecisionPackage,
    fields: dict[str, VocabularyField],
    evidence: dict[str, PackageEvidence],
    diagnostics: list[PackageDiagnostic],
) -> None:
    seen: set[str] = set()
    input_names = {name for name, field in fields.items() if field.role is VocabularyRole.INPUT}
    output_names = {name for name, field in fields.items() if field.role is VocabularyRole.OUTPUT}
    for index, scenario in enumerate(package.business_scenarios):
        path = f"businessScenarios[{index}]"
        if scenario.scenario_id in seen:
            _error(diagnostics, f"{path}.scenarioId", "DUPLICATE_SCENARIO", scenario.scenario_id)
        seen.add(scenario.scenario_id)
        unknown_inputs = set(scenario.inputs) - input_names
        unknown_outputs = set(scenario.expected) - output_names
        unknown_evidence = set(scenario.evidence_ids) - set(evidence)
        if unknown_inputs:
            _error(diagnostics, f"{path}.inputs", "UNKNOWN_INPUT", ", ".join(unknown_inputs))
        if unknown_outputs:
            _error(
                diagnostics, f"{path}.expected", "UNKNOWN_OUTPUT", ", ".join(unknown_outputs)
            )
        if unknown_evidence:
            _error(
                diagnostics,
                f"{path}.evidenceIds",
                "UNKNOWN_EVIDENCE",
                ", ".join(unknown_evidence),
            )


def _unique_by_key[T](
    values: Sequence[T],
    path: str,
    diagnostics: list[PackageDiagnostic],
    *,
    key: str = "key",
) -> dict[str, T]:
    result: dict[str, T] = {}
    for index, value in enumerate(values):
        name = str(getattr(value, key))
        if name in result:
            _error(diagnostics, f"{path}[{index}].{key}", "DUPLICATE_ID", name)
        result[name] = value
    return result


def _required_value(value: JsonValue | None) -> JsonValue:
    assert value is not None
    return value


def _error(
    diagnostics: list[PackageDiagnostic], path: str, code: str, message: str
) -> None:
    diagnostics.append(PackageDiagnostic(path=path, code=code, message=message))
