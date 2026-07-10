"""Strict Pydantic models for canonical Rule IR v1 decision content."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

IDENTIFIER_PATTERN = r"^[A-Za-z_$][A-Za-z0-9_$]*$"

type JsonScalar = StrictBool | StrictInt | StrictFloat | StrictStr
type JsonValue = JsonScalar | list[JsonScalar]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ScalarType(StrEnum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    DATE = "date"


class Operator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    BETWEEN = "BETWEEN"
    EXISTS = "EXISTS"
    STARTS_WITH = "STARTS_WITH"


class HitPolicy(StrEnum):
    FIRST = "FIRST"
    UNIQUE = "UNIQUE"
    COLLECT = "COLLECT"


class ProgramKind(StrEnum):
    SCREEN = "SCREEN"
    BATCH = "BATCH"
    INTERFACE = "INTERFACE"
    API = "API"
    SERVICE = "SERVICE"


class RuleOrigin(StrEnum):
    EXTRACTED = "EXTRACTED"
    USER_AUTHORED = "USER_AUTHORED"


class FieldDefinition(StrictModel):
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    type: ScalarType


class InputDefinition(FieldDefinition):
    source_path: str | None = None
    required: bool = True


class OutputDefinition(FieldDefinition):
    pass


class ProgramContext(StrictModel):
    program_id: str = Field(min_length=1)
    kind: ProgramKind
    entry_point: str = Field(min_length=1)


class LookupDefinition(StrictModel):
    name: str = Field(pattern=IDENTIFIER_PATTERN)
    ref: str = Field(pattern=r"^lookup://.+")
    keys: list[FieldDefinition] = Field(min_length=1)
    outputs: list[FieldDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_fields(self) -> LookupDefinition:
        _require_unique(self.keys, "lookup key")
        _require_unique(self.outputs, "lookup output")
        return self


class InputOperand(StrictModel):
    kind: Literal["INPUT"]
    name: str = Field(pattern=IDENTIFIER_PATTERN)


class LiteralOperand(StrictModel):
    kind: Literal["LITERAL"]
    value: JsonValue

    @model_validator(mode="after")
    def homogeneous_list(self) -> LiteralOperand:
        if isinstance(self.value, list) and self.value:
            first_type = type(self.value[0])
            if any(type(value) is not first_type for value in self.value):
                raise ValueError("literal lists must be homogeneous")
        return self


type LookupKeyOperand = InputOperand | LiteralOperand


class LookupFieldOperand(StrictModel):
    kind: Literal["LOOKUP_FIELD"]
    lookup: str = Field(pattern=IDENTIFIER_PATTERN)
    keys: dict[str, LookupKeyOperand]
    field: str = Field(pattern=IDENTIFIER_PATTERN)


type Operand = Annotated[
    InputOperand | LiteralOperand | LookupFieldOperand,
    Field(discriminator="kind"),
]


class Condition(StrictModel):
    left: Operand
    operator: Operator
    right: Operand | None = None


class ConditionGroup(StrictModel):
    all: list[Condition | ConditionGroup] | None = None
    any: list[Condition | ConditionGroup] | None = None

    @model_validator(mode="after")
    def exactly_one_branch(self) -> ConditionGroup:
        branches = [branch for branch in (self.all, self.any) if branch is not None]
        if len(branches) != 1 or not branches[0]:
            raise ValueError("condition group requires exactly one non-empty all/any branch")
        return self


class Action(StrictModel):
    output: str = Field(pattern=IDENTIFIER_PATTERN)
    value: JsonScalar


class JavaSourceReference(StrictModel):
    type: Literal["JAVA_SOURCE"]
    repository: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    symbol: str | None = None

    @model_validator(mode="after")
    def valid_line_range(self) -> JavaSourceReference:
        if self.line_end < self.line_start:
            raise ValueError("lineEnd must be greater than or equal to lineStart")
        return self


class DbRowReference(StrictModel):
    type: Literal["DB_ROW"]
    connection_alias: str = Field(min_length=1)
    schema_name: str = Field(alias="schema", min_length=1)
    table: str = Field(min_length=1)
    primary_key: dict[str, JsonScalar] = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ManualDocumentReference(StrictModel):
    type: Literal["MANUAL_DOC"]
    document_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    sheet: str | None = None
    section: str | None = None
    cell_range: str | None = None

    @model_validator(mode="after")
    def has_location(self) -> ManualDocumentReference:
        if not any((self.page, self.slide, self.sheet, self.section, self.cell_range)):
            raise ValueError(
                "manual reference requires a page, slide, sheet, section, or cellRange"
            )
        return self


class DmnAssetReference(StrictModel):
    type: Literal["DMN_ASSET"]
    asset_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    element_id: str = Field(min_length=1)


class UserActionReference(StrictModel):
    type: Literal["USER_ACTION"]
    actor: str = Field(min_length=1)
    at: datetime
    reason: str = Field(min_length=1)


type SourceReference = Annotated[
    JavaSourceReference
    | DbRowReference
    | ManualDocumentReference
    | DmnAssetReference
    | UserActionReference,
    Field(discriminator="type"),
]


class Rule(StrictModel):
    rule_id: str = Field(pattern=IDENTIFIER_PATTERN)
    when: ConditionGroup
    then: list[Action] = Field(min_length=1)
    origin: RuleOrigin
    source_references: list[SourceReference]
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def valid_provenance(self) -> Rule:
        if self.origin is RuleOrigin.EXTRACTED:
            if not self.source_references:
                raise ValueError("extracted rules require sourceReferences")
            if self.confidence is None:
                raise ValueError("extracted rules require confidence")
        else:
            if not any(reference.type == "USER_ACTION" for reference in self.source_references):
                raise ValueError("user-authored rules require a USER_ACTION reference")
            if self.confidence is not None:
                raise ValueError("user-authored rules must omit extraction confidence")
        return self


class DecisionContent(StrictModel):
    decision_id: str = Field(pattern=IDENTIFIER_PATTERN)
    decision_name: str = Field(min_length=1)
    profile: Literal["RULE_IR_V1"]
    schema_version: Literal[1]
    product: str | None = None
    program_contexts: list[ProgramContext] = Field(min_length=1)
    hit_policy: HitPolicy
    inputs: list[InputDefinition] = Field(min_length=1)
    outputs: list[OutputDefinition] = Field(min_length=1)
    default_output: dict[str, JsonScalar] | None = None
    lookups: list[LookupDefinition] = Field(default_factory=list)
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_semantics(self) -> DecisionContent:
        _require_unique(self.inputs, "input")
        _require_unique(self.outputs, "output")
        _require_unique(self.lookups, "lookup")
        _require_unique(self.rules, "rule", attribute="rule_id")
        self._validate_default_output()
        self._validate_rules()
        return self

    def _validate_default_output(self) -> None:
        output_types = {output.name: output.type for output in self.outputs}
        if self.hit_policy is HitPolicy.COLLECT:
            if self.default_output is not None:
                raise ValueError("COLLECT forbids defaultOutput")
            return
        if self.default_output is None:
            raise ValueError("FIRST and UNIQUE require defaultOutput")
        if set(self.default_output) != set(output_types):
            raise ValueError("defaultOutput must assign every declared output exactly once")
        for name, value in self.default_output.items():
            _require_scalar_type(value, output_types[name], f"defaultOutput.{name}")

    def _validate_rules(self) -> None:
        input_types = {field.name: field.type for field in self.inputs}
        output_types = {field.name: field.type for field in self.outputs}
        lookup_map = {lookup.name: lookup for lookup in self.lookups}
        for rule in self.rules:
            if _group_depth(rule.when) > 3:
                raise ValueError(f"rule {rule.rule_id} exceeds condition depth 3")
            if {action.output for action in rule.then} != set(output_types):
                raise ValueError(f"rule {rule.rule_id} must assign every output exactly once")
            if len(rule.then) != len(output_types):
                raise ValueError(f"rule {rule.rule_id} contains duplicate output assignments")
            for action in rule.then:
                _require_scalar_type(
                    action.value,
                    output_types[action.output],
                    f"rule {rule.rule_id}.{action.output}",
                )
            for condition in _conditions(rule.when):
                _validate_condition(condition, input_types, lookup_map)


def _require_unique(
    values: Sequence[StrictModel], label: str, *, attribute: str = "name"
) -> None:
    names = [getattr(value, attribute) for value in values]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate {label} names are forbidden")


def _group_depth(group: ConditionGroup) -> int:
    children = group.all if group.all is not None else group.any
    assert children is not None
    nested = [_group_depth(child) for child in children if isinstance(child, ConditionGroup)]
    return 1 + (max(nested) if nested else 0)


def _conditions(group: ConditionGroup) -> list[Condition]:
    children = group.all if group.all is not None else group.any
    assert children is not None
    found: list[Condition] = []
    for child in children:
        if isinstance(child, Condition):
            found.append(child)
        else:
            found.extend(_conditions(child))
    return found


def _resolve_operand_type(
    operand: Operand,
    input_types: dict[str, ScalarType],
    lookups: dict[str, LookupDefinition],
) -> ScalarType | None:
    if isinstance(operand, InputOperand):
        if operand.name not in input_types:
            raise ValueError(f"unknown input operand: {operand.name}")
        return input_types[operand.name]
    if isinstance(operand, LiteralOperand):
        return None
    if operand.lookup not in lookups:
        raise ValueError(f"unknown lookup operand: {operand.lookup}")
    lookup = lookups[operand.lookup]
    key_types = {field.name: field.type for field in lookup.keys}
    if set(operand.keys) != set(key_types):
        raise ValueError(f"lookup {lookup.name} keys do not match its declaration")
    for name, value in operand.keys.items():
        resolved = _resolve_operand_type(value, input_types, lookups)
        if resolved is None:
            assert isinstance(value, LiteralOperand)
            _require_value_type(value.value, key_types[name], f"lookup key {name}")
        elif resolved is not key_types[name]:
            raise ValueError(f"lookup key {name} type mismatch")
    outputs = {field.name: field.type for field in lookup.outputs}
    if operand.field not in outputs:
        raise ValueError(f"unknown lookup output: {operand.field}")
    return outputs[operand.field]


def _validate_condition(
    condition: Condition,
    input_types: dict[str, ScalarType],
    lookups: dict[str, LookupDefinition],
) -> None:
    left_type = _resolve_operand_type(condition.left, input_types, lookups)
    if left_type is None:
        raise ValueError("condition left operand must be an input or lookup field")
    if condition.operator is Operator.EXISTS:
        if condition.right is not None:
            raise ValueError("EXISTS forbids a right operand")
        return
    if condition.right is None:
        raise ValueError(f"{condition.operator} requires a right operand")

    if condition.operator is Operator.STARTS_WITH and left_type is not ScalarType.STRING:
        raise ValueError("STARTS_WITH requires string operands")
    ordered_operators = {Operator.GT, Operator.GTE, Operator.LT, Operator.LTE}
    ordered_types = {ScalarType.INTEGER, ScalarType.DECIMAL, ScalarType.DATE}
    if condition.operator in ordered_operators and left_type not in ordered_types:
        raise ValueError(f"{condition.operator} requires integer, decimal, or date operands")

    right_type = _resolve_operand_type(condition.right, input_types, lookups)
    if right_type is None:
        assert isinstance(condition.right, LiteralOperand)
        _validate_literal_operator(condition.operator, condition.right.value, left_type)
    elif right_type is not left_type:
        raise ValueError("condition operand types do not match")


def _validate_literal_operator(operator: Operator, value: JsonValue, expected: ScalarType) -> None:
    if operator in {Operator.IN, Operator.NOT_IN}:
        if not isinstance(value, list) or not value:
            raise ValueError(f"{operator} requires a non-empty list")
        for item in value:
            _require_scalar_type(item, expected, operator)
        return
    if operator is Operator.BETWEEN:
        if expected not in {ScalarType.INTEGER, ScalarType.DECIMAL, ScalarType.DATE}:
            raise ValueError("BETWEEN requires integer, decimal, or date operands")
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("BETWEEN requires exactly two values")
        _require_scalar_type(value[0], expected, operator)
        _require_scalar_type(value[1], expected, operator)
        if expected is ScalarType.DATE:
            assert isinstance(value[0], str) and isinstance(value[1], str)
            reversed_bounds = date.fromisoformat(value[0]) > date.fromisoformat(value[1])
        elif expected is ScalarType.DECIMAL:
            reversed_bounds = Decimal(str(value[0])) > Decimal(str(value[1]))
        else:
            assert type(value[0]) is int and type(value[1]) is int
            reversed_bounds = value[0] > value[1]
        if reversed_bounds:
            raise ValueError("BETWEEN bounds must be ordered")
        return
    if isinstance(value, list):
        raise ValueError(f"{operator} requires a scalar right operand")
    _require_scalar_type(value, expected, operator)


def _require_value_type(value: JsonValue, expected: ScalarType, location: str) -> None:
    if isinstance(value, list):
        raise ValueError(f"{location} requires a scalar value")
    _require_scalar_type(value, expected, location)


def _require_scalar_type(value: JsonScalar, expected: ScalarType, location: object) -> None:
    if expected is ScalarType.BOOLEAN and type(value) is bool:
        return
    if expected is ScalarType.INTEGER and type(value) is int:
        return
    if expected is ScalarType.DECIMAL and type(value) in {int, float} and type(value) is not bool:
        return
    if expected is ScalarType.STRING and type(value) is str:
        return
    if expected is ScalarType.DATE and type(value) is str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{location} requires an ISO date") from exc
        return
    raise ValueError(f"{location} does not match declared type {expected}")


ConditionGroup.model_rebuild()
