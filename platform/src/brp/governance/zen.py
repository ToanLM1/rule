"""Pure Rule IR to JDM export and explicitly advisory Zen preview."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import zen

from brp.ir.models import (
    Condition,
    ConditionGroup,
    DecisionContent,
    HitPolicy,
    InputOperand,
    LiteralOperand,
    LookupFieldOperand,
    Operator,
)


class LookupResolver(Protocol):
    def resolve(self, ref: str, keys: dict[str, object]) -> dict[str, object]: ...


class MissingLookupValueError(LookupError):
    pass


class UniqueHitPolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class LookupBinding:
    context_field: str
    ref: str
    keys: dict[str, InputOperand | LiteralOperand]
    output_field: str


@dataclass(frozen=True)
class JdmExport:
    document: dict[str, Any]
    lookup_bindings: tuple[LookupBinding, ...]


class DictLookupResolver:
    """Resolve values from immutable, already-snapshotted lookup rows."""

    def __init__(self, snapshots: dict[str, list[dict[str, object]]]) -> None:
        self.snapshots = snapshots

    def resolve(self, ref: str, keys: dict[str, object]) -> dict[str, object]:
        matches = [
            row
            for row in self.snapshots.get(ref, [])
            if all(row.get(name) == value for name, value in keys.items())
        ]
        if len(matches) != 1:
            raise MissingLookupValueError(f"lookup {ref} expected one row, found {len(matches)}")
        return matches[0]


def export_jdm(content: DecisionContent) -> JdmExport:
    """Transform content only; no repository envelope or mutable state is read."""
    bindings: list[LookupBinding] = []
    lookup_refs = {lookup.name: lookup.ref for lookup in content.lookups}
    condition_column = {"id": "condition", "name": "Condition", "field": ""}
    output_columns = [
        {
            "id": f"out_{index}",
            "name": output.name,
            "field": output.name,
        }
        for index, output in enumerate(content.outputs)
    ]
    rows: list[dict[str, str]] = []
    for rule in content.rules:
        row = {
            "_id": rule.rule_id,
            "condition": _group_expression(rule.when, rule.rule_id, lookup_refs, bindings),
        }
        actions = {action.output: action.value for action in rule.then}
        for output_index, output in enumerate(content.outputs):
            row[f"out_{output_index}"] = _literal(actions[output.name])
        rows.append(row)
    if content.hit_policy is HitPolicy.FIRST:
        assert content.default_output is not None
        default_row = {"_id": "__default__", "condition": "true"}
        for index, output in enumerate(content.outputs):
            default_row[f"out_{index}"] = _literal(content.default_output[output.name])
        rows.append(default_row)

    jdm_policy = "collect" if content.hit_policy is not HitPolicy.FIRST else "first"
    document = {
        "nodes": [
            {
                "id": "input",
                "type": "inputNode",
                "name": "Request",
                "position": {"x": 0, "y": 0},
                "content": {"schema": ""},
            },
            {
                "id": "decision",
                "type": "decisionTableNode",
                "name": content.decision_name,
                "position": {"x": 300, "y": 0},
                "content": {
                    "hitPolicy": jdm_policy,
                    "inputs": [condition_column],
                    "outputs": output_columns,
                    "rules": rows,
                    "passThrough": False,
                    "inputField": None,
                    "outputPath": None,
                    "executionMode": "single",
                },
            },
            {
                "id": "output",
                "type": "outputNode",
                "name": "Response",
                "position": {"x": 600, "y": 0},
                "content": {"schema": ""},
            },
        ],
        "edges": [
            {"id": "e1", "sourceId": "input", "targetId": "decision", "type": "edge"},
            {"id": "e2", "sourceId": "decision", "targetId": "output", "type": "edge"},
        ],
    }
    return JdmExport(document=document, lookup_bindings=tuple(bindings))


def preview(
    content: DecisionContent,
    inputs: dict[str, object],
    lookup_resolver: LookupResolver | None = None,
) -> dict[str, object]:
    exported = export_jdm(content)
    context = dict(inputs)
    for binding in exported.lookup_bindings:
        if lookup_resolver is None:
            raise MissingLookupValueError(f"lookup resolver required for {binding.ref}")
        keys = {
            name: context[value.name] if isinstance(value, InputOperand) else value.value
            for name, value in binding.keys.items()
        }
        resolved = lookup_resolver.resolve(binding.ref, keys)
        if binding.output_field not in resolved:
            raise MissingLookupValueError(
                f"lookup {binding.ref} has no field {binding.output_field}"
            )
        context[binding.context_field] = resolved[binding.output_field]
    engine = zen.ZenEngine()
    decision = engine.create_decision(
        json.dumps(exported.document, ensure_ascii=False, separators=(",", ":"))
    )
    response = decision.evaluate(context)
    result: object = response["result"]
    if content.hit_policy is HitPolicy.UNIQUE:
        assert isinstance(result, list)
        if len(result) > 1:
            raise UniqueHitPolicyError(f"UNIQUE matched {len(result)} rules")
        result = result[0] if result else content.default_output
    return {"executor": "ZEN", "authority": "ADVISORY", "result": result}


def _group_expression(
    group: ConditionGroup,
    rule_id: str,
    lookup_refs: dict[str, str],
    bindings: list[LookupBinding],
) -> str:
    children = group.all if group.all is not None else group.any
    assert children is not None
    operator = " and " if group.all is not None else " or "
    expressions = [
        _condition_expression(child, rule_id, lookup_refs, bindings)
        if isinstance(child, Condition)
        else _group_expression(child, rule_id, lookup_refs, bindings)
        for child in children
    ]
    return "(" + operator.join(expressions) + ")"


def _condition_expression(
    condition: Condition,
    rule_id: str,
    lookup_refs: dict[str, str],
    bindings: list[LookupBinding],
) -> str:
    left = _operand_expression(condition.left, rule_id, lookup_refs, bindings)
    if condition.operator is Operator.EXISTS:
        return f"({left} != null)"
    assert condition.right is not None
    right = _operand_expression(condition.right, rule_id, lookup_refs, bindings)
    binary = {
        Operator.EQ: "==",
        Operator.NE: "!=",
        Operator.GT: ">",
        Operator.GTE: ">=",
        Operator.LT: "<",
        Operator.LTE: "<=",
    }
    if condition.operator in binary:
        return f"({left} {binary[condition.operator]} {right})"
    assert isinstance(condition.right, LiteralOperand)
    if condition.operator in {Operator.IN, Operator.NOT_IN}:
        expression = f"contains({right}, {left})"
        return f"(!{expression})" if condition.operator is Operator.NOT_IN else expression
    if condition.operator is Operator.BETWEEN:
        assert isinstance(condition.right.value, list)
        low, high = condition.right.value
        return f"({left} >= {_literal(low)} and {left} <= {_literal(high)})"
    if condition.operator is Operator.STARTS_WITH:
        return f"startsWith({left}, {right})"
    raise ValueError(f"unsupported operator: {condition.operator}")


def _operand_expression(
    operand: InputOperand | LiteralOperand | LookupFieldOperand,
    rule_id: str,
    lookup_refs: dict[str, str],
    bindings: list[LookupBinding],
) -> str:
    if isinstance(operand, InputOperand):
        return operand.name
    if isinstance(operand, LiteralOperand):
        return _literal(operand.value)
    field = f"__lookup_{len(bindings)}"
    bindings.append(
        LookupBinding(
            context_field=field,
            ref=lookup_refs[operand.lookup],
            keys=operand.keys,
            output_field=operand.field,
        )
    )
    return field


def _literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
