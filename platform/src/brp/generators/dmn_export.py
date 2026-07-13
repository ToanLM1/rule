"""Deterministic DMN 1.3 decision-table export for the representable IR subset."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from brp.ir.canonical import canonical_bytes
from brp.ir.models import (
    Condition,
    ConditionGroup,
    DecisionContent,
    HitPolicy,
    InputOperand,
    JsonScalar,
    LiteralOperand,
    Operator,
    ScalarType,
)

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"
BRP_NS = "urn:brp:provenance:v1"
ET.register_namespace("", DMN_NS)
ET.register_namespace("brp", BRP_NS)


class DmnExportError(ValueError):
    pass


@dataclass(frozen=True)
class DmnArtifact:
    content: bytes
    content_hash: str
    decision_content_hash: str


def export_dmn(content: DecisionContent) -> DmnArtifact:
    if "$" in content.decision_id:
        raise DmnExportError("decisionId is not representable as a DMN XML id")
    root = ET.Element(
        _tag("definitions"),
        {
            "id": f"defs_{content.decision_id}",
            "name": content.decision_name,
            "namespace": f"urn:brp:decision:{content.decision_id}",
        },
    )
    decision = ET.SubElement(
        root,
        _tag("decision"),
        {"id": content.decision_id, "name": content.decision_name},
    )
    extension = ET.SubElement(decision, _tag("extensionElements"))
    decision_hash = hashlib.sha256(canonical_bytes(content)).hexdigest()
    ET.SubElement(extension, _brp("canonicalContentHash")).text = decision_hash
    table = ET.SubElement(
        decision,
        _tag("decisionTable"),
        {"id": f"table_{content.decision_id}", "hitPolicy": content.hit_policy.value},
    )
    for index, input_definition in enumerate(content.inputs, 1):
        input_element = ET.SubElement(
            table,
            _tag("input"),
            {"id": f"input_{index}", "label": input_definition.name},
        )
        expression = ET.SubElement(
            input_element,
            _tag("inputExpression"),
            {
                "id": f"input_expression_{index}",
                "typeRef": _type_ref(input_definition.type),
            },
        )
        ET.SubElement(expression, _tag("text")).text = (
            input_definition.source_path or input_definition.name
        )
    for index, output_definition in enumerate(content.outputs, 1):
        ET.SubElement(
            table,
            _tag("output"),
            {
                "id": f"output_{index}",
                "name": output_definition.name,
                "typeRef": _type_ref(output_definition.type),
            },
        )
    for index, rule in enumerate(content.rules, 1):
        cells = _rule_cells(content, rule.when)
        element = ET.SubElement(table, _tag("rule"), {"id": _xml_id(rule.rule_id, f"rule_{index}")})
        rule_extension = ET.SubElement(element, _tag("extensionElements"))
        references = [
            reference.model_dump(mode="json", by_alias=True, exclude_none=True)
            for reference in rule.source_references
        ]
        ET.SubElement(rule_extension, _brp("sourceReferences")).text = json.dumps(
            references, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        for input_index, cell in enumerate(cells, 1):
            entry = ET.SubElement(element, _tag("inputEntry"), {"id": f"r{index}_in{input_index}"})
            ET.SubElement(entry, _tag("text")).text = cell
        actions = {action.output: action.value for action in rule.then}
        for output_index, output in enumerate(content.outputs, 1):
            entry = ET.SubElement(
                element, _tag("outputEntry"), {"id": f"r{index}_out{output_index}"}
            )
            ET.SubElement(entry, _tag("text")).text = _literal(actions[output.name], output.type)
    if content.hit_policy in {HitPolicy.FIRST, HitPolicy.UNIQUE}:
        assert content.default_output is not None
        index = len(content.rules) + 1
        element = ET.SubElement(table, _tag("rule"), {"id": "__default__"})
        for input_index, _input in enumerate(content.inputs, 1):
            entry = ET.SubElement(element, _tag("inputEntry"), {"id": f"r{index}_in{input_index}"})
            ET.SubElement(entry, _tag("text")).text = "-"
        for output_index, output in enumerate(content.outputs, 1):
            entry = ET.SubElement(
                element, _tag("outputEntry"), {"id": f"r{index}_out{output_index}"}
            )
            ET.SubElement(entry, _tag("text")).text = _literal(
                content.default_output[output.name], output.type
            )
    ET.indent(root, space="  ")
    document = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return DmnArtifact(
        content=document,
        content_hash=hashlib.sha256(document).hexdigest(),
        decision_content_hash=decision_hash,
    )


def dmn_semantic_bytes(content: DecisionContent) -> bytes:
    """Canonical behavior projection used for import/export round-trip checks."""
    document: dict[str, Any] = {
        "decisionId": content.decision_id,
        "decisionName": content.decision_name,
        "profile": content.profile,
        "schemaVersion": content.schema_version,
        "hitPolicy": content.hit_policy.value,
        "inputs": [
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in content.inputs
        ],
        "outputs": [
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in content.outputs
        ],
        "rules": [
            {
                "ruleId": rule.rule_id,
                "when": rule.when.model_dump(mode="json", by_alias=True, exclude_none=True),
                "then": [
                    action.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for action in rule.then
                ],
            }
            for rule in content.rules
        ],
    }
    if content.default_output is not None:
        document["defaultOutput"] = content.default_output
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _rule_cells(content: DecisionContent, group: ConditionGroup) -> list[str]:
    if group.all is None or any(isinstance(item, ConditionGroup) for item in group.all):
        raise DmnExportError("DMN export supports one flat all-condition group per rule")
    by_input: dict[str, Condition] = {}
    for item in group.all:
        assert isinstance(item, Condition)
        if not isinstance(item.left, InputOperand) or not isinstance(item.right, LiteralOperand):
            raise DmnExportError("DMN export supports input-to-literal conditions only")
        if item.left.name in by_input:
            raise DmnExportError("DMN export supports at most one condition per input cell")
        by_input[item.left.name] = item
    input_types = {item.name: item.type for item in content.inputs}
    return [
        "-"
        if item.name not in by_input
        else _unary_test(by_input[item.name], input_types[item.name])
        for item in content.inputs
    ]


def _unary_test(condition: Condition, kind: ScalarType) -> str:
    if condition.operator in {Operator.EXISTS, Operator.STARTS_WITH}:
        raise DmnExportError(f"operator {condition.operator} is not in the DMN export subset")
    assert isinstance(condition.right, LiteralOperand)
    value = condition.right.value
    if condition.operator is Operator.BETWEEN:
        assert isinstance(value, list)
        return f"[{_literal(value[0], kind)}..{_literal(value[1], kind)}]"
    if condition.operator in {Operator.IN, Operator.NOT_IN}:
        assert isinstance(value, list)
        listed = ",".join(_literal(item, kind) for item in value)
        return f"not({listed})" if condition.operator is Operator.NOT_IN else listed
    assert not isinstance(value, list)
    literal = _literal(value, kind)
    if condition.operator is Operator.EQ:
        return literal
    if condition.operator is Operator.NE:
        return f"not({literal})"
    prefix = {
        Operator.LT: "<",
        Operator.LTE: "<=",
        Operator.GT: ">",
        Operator.GTE: ">=",
    }.get(condition.operator)
    if prefix is None:
        raise DmnExportError(f"operator {condition.operator} is not representable")
    return f"{prefix} {literal}"


def _literal(value: JsonScalar, kind: ScalarType) -> str:
    if kind is ScalarType.STRING:
        return json.dumps(value, ensure_ascii=False)
    if kind is ScalarType.BOOLEAN:
        return "true" if value is True else "false"
    if kind is ScalarType.DATE:
        return f"date({json.dumps(value)})"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _type_ref(kind: ScalarType) -> str:
    return {
        ScalarType.BOOLEAN: "boolean",
        ScalarType.INTEGER: "integer",
        ScalarType.DECIMAL: "number",
        ScalarType.STRING: "string",
        ScalarType.DATE: "date",
    }[kind]


def _xml_id(value: str, fallback: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return identifier if identifier and identifier[0].isalpha() else fallback


def _tag(name: str) -> str:
    return f"{{{DMN_NS}}}{name}"


def _brp(name: str) -> str:
    return f"{{{BRP_NS}}}{name}"
