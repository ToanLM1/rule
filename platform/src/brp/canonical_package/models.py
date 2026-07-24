"""Strict business-facing models above executable Rule IR."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from brp.ir.models import (
    IDENTIFIER_PATTERN,
    FieldDefinition,
    HitPolicy,
    JsonScalar,
    JsonValue,
    Operator,
    ProgramContext,
    ScalarType,
    SourceReference,
    StrictModel,
)


class VocabularyRole(StrEnum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class VocabularyField(StrictModel):
    key: str = Field(pattern=IDENTIFIER_PATTERN)
    label: str = Field(min_length=1)
    type: ScalarType
    role: VocabularyRole
    required: bool = True
    source_path: str | None = None
    description: str | None = None


class PackageCondition(StrictModel):
    field: str = Field(pattern=IDENTIFIER_PATTERN)
    operator: Operator
    value: JsonValue | None = None

    @model_validator(mode="after")
    def unary_exists_only(self) -> PackageCondition:
        if self.operator is Operator.EXISTS and self.value is not None:
            raise ValueError("EXISTS forbids a value")
        if self.operator is not Operator.EXISTS and self.value is None:
            raise ValueError(f"{self.operator} requires a value")
        return self


class DecisionTableRow(StrictModel):
    row_id: str = Field(pattern=IDENTIFIER_PATTERN)
    conditions: list[PackageCondition] = Field(min_length=1)
    outcomes: dict[str, JsonScalar] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None

    @model_validator(mode="after")
    def evidence_confidence_pair(self) -> DecisionTableRow:
        if self.evidence_ids and self.confidence is None:
            raise ValueError("source-derived rows require confidence")
        if not self.evidence_ids and self.confidence is not None:
            raise ValueError("user-authored rows must omit extraction confidence")
        return self


class DecisionTable(StrictModel):
    decision_id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    hit_policy: HitPolicy
    input_fields: list[str] = Field(min_length=1)
    output_fields: list[str] = Field(min_length=1)
    rows: list[DecisionTableRow] = Field(min_length=1)
    default_outcome: dict[str, JsonScalar] | None = None


class PackageLookup(StrictModel):
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    label: str = Field(min_length=1)
    ref: str = Field(pattern=r"^lookup://.+")
    keys: list[FieldDefinition] = Field(min_length=1)
    outputs: list[FieldDefinition] = Field(min_length=1)


class CompositionOperation(StrEnum):
    SUM = "SUM"
    DISTINCT = "DISTINCT"
    FIRST_NON_NULL = "FIRST_NON_NULL"


class CompositionStep(StrictModel):
    output: str = Field(pattern=IDENTIFIER_PATTERN)
    operation: CompositionOperation
    decisions: list[str] = Field(min_length=1)


class BusinessScenario(StrictModel):
    scenario_id: str = Field(pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1)
    inputs: dict[str, JsonScalar] = Field(min_length=1)
    expected: dict[str, JsonValue] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class PackageEvidence(StrictModel):
    evidence_id: str = Field(pattern=IDENTIFIER_PATTERN)
    source_reference: SourceReference
    summary: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class JavaTargetBinding(StrictModel):
    repository_alias: str = Field(min_length=1)
    base_branch: str = Field(min_length=1)
    java_package: str = Field(min_length=1)
    generated_path: str = Field(min_length=1)
    test_path: str = Field(min_length=1)
    facade: str = Field(min_length=1)
    build_commands: list[list[str]] = Field(min_length=1)


class CanonicalDecisionPackage(StrictModel):
    package_id: str = Field(pattern=IDENTIFIER_PATTERN)
    package_name: str = Field(min_length=1)
    profile: Literal["CANONICAL_DECISION_PACKAGE_V1"]
    schema_version: Literal[1]
    product: str | None = None
    program_contexts: list[ProgramContext] = Field(min_length=1)
    vocabulary: list[VocabularyField] = Field(min_length=1)
    decisions: list[DecisionTable] = Field(min_length=1)
    lookups: list[PackageLookup] = Field(default_factory=list)
    composition: list[CompositionStep] = Field(default_factory=list)
    business_scenarios: list[BusinessScenario] = Field(default_factory=list)
    evidence: list[PackageEvidence] = Field(default_factory=list)
    target_binding: JavaTargetBinding | None = None
    authored_at: datetime | None = None
