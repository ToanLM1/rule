"""Restricted DMN 1.3+ decision-table import into candidate Rule IR."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from brp.adapters.contracts import (
    SOURCE_ADAPTER_CAPABILITY,
    AdapterDiagnostic,
    CandidateDecision,
    ExtractionBatch,
    Source,
    SourceSnapshot,
    UnmappableItem,
)
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DecisionContent,
    DmnAssetReference,
    HitPolicy,
    InputDefinition,
    InputOperand,
    JsonScalar,
    LiteralOperand,
    Operator,
    OutputDefinition,
    ProgramContext,
    ProgramKind,
    Rule,
    RuleOrigin,
    ScalarType,
)


class DmnImportError(ValueError):
    pass


class BpmnDocumentError(DmnImportError):
    pass


class UnsupportedFeelError(DmnImportError):
    pass


class DmnDecisionTableAdapter:
    name = "engine-dmn"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def __init__(self, paths: list[Path], *, revision: str) -> None:
        if not revision.strip():
            raise ValueError("immutable DMN asset revision is required")
        self.paths = [path.resolve() for path in paths]
        self.revision = revision

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [
            Source(
                source_id=f"dmn:{path.name}",
                kind="dmn-asset",
                locator={"path": str(path), "assetId": path.name, "revision": self.revision},
            )
            for path in sorted(self.paths)
            if path.suffix.lower() in {".dmn", ".xml", ".bpmn"}
        ]

    def extract(self, source: Source) -> ExtractionBatch:
        path = Path(str(source.locator["path"]))
        raw = path.read_bytes()
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise DmnImportError("DTD and entity declarations are forbidden")
        content_hash = hashlib.sha256(raw).hexdigest()
        root = ET.fromstring(raw)
        namespace = _namespace(root.tag)
        if "BPMN" in namespace.upper() or path.suffix.lower() == ".bpmn":
            raise BpmnDocumentError(
                "BPMN is workflow orchestration and cannot be imported as rules"
            )
        if "DMN" not in namespace.upper():
            raise DmnImportError(f"not a DMN document namespace: {namespace}")

        decisions: list[CandidateDecision] = []
        unmappable: list[UnmappableItem] = []
        for decision in _children(root, "decision"):
            table = _child(decision, "decisionTable")
            if table is None:
                unmappable.append(
                    self._unmappable(
                        source,
                        decision,
                        "UNSUPPORTED_DMN_EXPRESSION",
                        ET.tostring(decision, encoding="unicode"),
                    )
                )
                continue
            candidate, review = self._table(source, decision, table)
            unmappable.extend(review)
            if candidate is not None:
                decisions.append(candidate)
        if not decisions and not unmappable:
            unmappable.append(
                UnmappableItem(
                    reason_code="NO_DMN_DECISIONS",
                    raw_fragment=path.name,
                    provenance={
                        "assetId": source.locator["assetId"],
                        "revision": self.revision,
                    },
                )
            )
        return ExtractionBatch(
            adapter=self.name,
            decisions=decisions,
            unmappable=unmappable,
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="DMN_IMPORT_COMPLETE",
                    message=(
                        f"imported {len(decisions)} decision tables; "
                        f"{len(unmappable)} review items"
                    ),
                )
            ],
            source_snapshot=SourceSnapshot(
                source_id=source.source_id,
                revision=self.revision,
                content_hash=content_hash,
                captured_at=datetime.now(UTC),
            ),
        )

    def _table(
        self, source: Source, decision: ET.Element, table: ET.Element
    ) -> tuple[CandidateDecision | None, list[UnmappableItem]]:
        decision_id = decision.get("id") or "decision"
        key = _decision_key(decision.get("name") or decision_id)
        inputs = [
            _input_definition(item, index)
            for index, item in enumerate(_children(table, "input"), 1)
        ]
        outputs = [
            _output_definition(item, index)
            for index, item in enumerate(_children(table, "output"), 1)
        ]
        if not inputs or not outputs:
            return None, [
                self._unmappable(
                    source, table, "INVALID_DMN_TABLE", "decision table requires inputs and outputs"
                )
            ]
        try:
            hit_policy = HitPolicy(table.get("hitPolicy", "UNIQUE").upper())
        except ValueError:
            return None, [
                self._unmappable(
                    source,
                    table,
                    "UNSUPPORTED_DMN_HIT_POLICY",
                    table.get("hitPolicy", ""),
                )
            ]
        rules: list[Rule] = []
        default_output: dict[str, JsonScalar] | None = None
        review: list[UnmappableItem] = []
        for index, element in enumerate(_children(table, "rule"), 1):
            input_entries = [
                _text(_child(item, "text")) for item in _children(element, "inputEntry")
            ]
            output_entries = [
                _text(_child(item, "text")) for item in _children(element, "outputEntry")
            ]
            raw_fragment = json.dumps(
                {"inputs": input_entries, "outputs": output_entries}, ensure_ascii=False
            )
            if len(input_entries) != len(inputs) or len(output_entries) != len(outputs):
                review.append(self._unmappable(source, element, "INVALID_DMN_RULE", raw_fragment))
                continue
            try:
                actions = [
                    Action(output=output.name, value=_literal(value, output.type))
                    for output, value in zip(outputs, output_entries, strict=True)
                ]
                conditions: list[Condition | ConditionGroup] = [
                    condition
                    for field, value in zip(inputs, input_entries, strict=True)
                    if (condition := _condition(field, value)) is not None
                ]
            except (UnsupportedFeelError, ValueError) as exc:
                review.append(
                    self._unmappable(
                        source,
                        element,
                        "UNSUPPORTED_FEEL",
                        f"{raw_fragment}; error={exc}",
                    )
                )
                continue
            if not conditions and hit_policy in {HitPolicy.FIRST, HitPolicy.UNIQUE}:
                default_output = {action.output: action.value for action in actions}
                continue
            if not conditions:
                conditions = [
                    Condition(
                        left=InputOperand(kind="INPUT", name=inputs[0].name),
                        operator=Operator.EXISTS,
                    )
                ]
            reference = DmnAssetReference(
                type="DMN_ASSET",
                asset_id=str(source.locator["assetId"]),
                revision=self.revision,
                decision_id=decision_id,
                element_id=element.get("id") or f"rule-{index}",
            )
            rules.append(
                Rule(
                    rule_id=_identifier(element.get("id") or f"R{index:03d}"),
                    when=ConditionGroup(all=conditions),
                    then=actions,
                    origin=RuleOrigin.EXTRACTED,
                    source_references=[reference],
                    confidence=1.0,
                )
            )
        if hit_policy in {HitPolicy.FIRST, HitPolicy.UNIQUE} and default_output is None:
            review.append(
                self._unmappable(
                    source,
                    table,
                    "DMN_DEFAULT_REQUIRED",
                    "Rule IR requires an explicit wildcard default for FIRST/UNIQUE",
                )
            )
            return None, review
        if not rules:
            return None, review
        content = DecisionContent(
            decision_id=_identifier(decision_id),
            decision_name=decision.get("name") or decision_id,
            profile="RULE_IR_V1",
            schema_version=1,
            program_contexts=[
                ProgramContext(
                    program_id="DMN-IMPORT",
                    kind=ProgramKind.SERVICE,
                    entry_point=f"dmn://{source.locator['assetId']}#{decision_id}",
                )
            ],
            hit_policy=hit_policy,
            inputs=inputs,
            outputs=outputs,
            default_output=default_output,
            rules=rules,
        )
        return CandidateDecision(decision_key=key, content=content), review

    def _unmappable(
        self,
        source: Source,
        element: ET.Element,
        reason: str,
        raw: str,
    ) -> UnmappableItem:
        return UnmappableItem(
            reason_code=reason,
            raw_fragment=raw,
            provenance={
                "type": "DMN_ASSET",
                "assetId": source.locator["assetId"],
                "revision": self.revision,
                "elementId": element.get("id") or _local(element.tag),
            },
        )


def _input_definition(element: ET.Element, index: int) -> InputDefinition:
    expression = _child(element, "inputExpression")
    source_path = _text(_child(expression, "text")) if expression is not None else ""
    name = element.get("label") or source_path.rsplit(".", 1)[-1] or f"input{index}"
    type_name = (expression.get("typeRef") if expression is not None else None) or "string"
    return InputDefinition(
        name=_identifier(name),
        source_path=source_path or None,
        type=_scalar_type(type_name),
    )


def _output_definition(element: ET.Element, index: int) -> OutputDefinition:
    name = element.get("name") or element.get("label") or f"output{index}"
    return OutputDefinition(
        name=_identifier(name), type=_scalar_type(element.get("typeRef") or "string")
    )


def _condition(field: InputDefinition, feel: str) -> Condition | None:
    value = feel.strip()
    if value in {"", "-"}:
        return None
    left = InputOperand(kind="INPUT", name=field.name)
    between = re.fullmatch(r"\[\s*(.+?)\s*\.\.\s*(.+?)\s*\]", value)
    if between:
        bounds = [
            _literal(between.group(1), field.type),
            _literal(between.group(2), field.type),
        ]
        return Condition(
            left=left,
            operator=Operator.BETWEEN,
            right=LiteralOperand(kind="LITERAL", value=bounds),
        )
    comparison = re.fullmatch(r"(<=|>=|<|>)\s*(.+)", value)
    if comparison:
        operators = {
            "<": Operator.LT,
            "<=": Operator.LTE,
            ">": Operator.GT,
            ">=": Operator.GTE,
        }
        return Condition(
            left=left,
            operator=operators[comparison.group(1)],
            right=LiteralOperand(kind="LITERAL", value=_literal(comparison.group(2), field.type)),
        )
    negated = re.fullmatch(r"not\((.+)\)", value, re.IGNORECASE)
    list_text = negated.group(1) if negated else value
    parts = _split_list(list_text)
    if len(parts) > 1:
        return Condition(
            left=left,
            operator=Operator.NOT_IN if negated else Operator.IN,
            right=LiteralOperand(
                kind="LITERAL", value=[_literal(part, field.type) for part in parts]
            ),
        )
    if negated:
        return Condition(
            left=left,
            operator=Operator.NE,
            right=LiteralOperand(kind="LITERAL", value=_literal(parts[0], field.type)),
        )
    if re.search(r"\b(if|then|else|function|for|some|every)\b|[+*/]", value, re.I):
        raise UnsupportedFeelError(value)
    return Condition(
        left=left,
        operator=Operator.EQ,
        right=LiteralOperand(kind="LITERAL", value=_literal(value, field.type)),
    )


def _literal(value: str, kind: ScalarType) -> bool | int | float | str:
    text = value.strip()
    if kind is ScalarType.STRING:
        if not (len(text) >= 2 and text[0] == text[-1] == '"'):
            raise UnsupportedFeelError(f"string literal must be quoted: {text}")
        decoded = json.loads(text)
        if not isinstance(decoded, str):
            raise UnsupportedFeelError(text)
        return decoded
    if kind is ScalarType.BOOLEAN:
        if text.lower() not in {"true", "false"}:
            raise UnsupportedFeelError(text)
        return text.lower() == "true"
    if kind is ScalarType.INTEGER:
        return int(text)
    if kind is ScalarType.DECIMAL:
        return float(text)
    if kind is ScalarType.DATE:
        match = re.fullmatch(r'date\("(\d{4}-\d{2}-\d{2})"\)|"(\d{4}-\d{2}-\d{2})"', text)
        if match is None:
            raise UnsupportedFeelError(text)
        return match.group(1) or match.group(2)
    raise UnsupportedFeelError(text)


def _split_list(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quoted = False
    for index, character in enumerate(value):
        if character == '"':
            quoted = not quoted
        elif character == "," and not quoted:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    if quoted or any(not part for part in parts):
        raise UnsupportedFeelError(value)
    return parts


def _scalar_type(value: str) -> ScalarType:
    normalized = value.split(":")[-1].lower()
    mapping = {
        "boolean": ScalarType.BOOLEAN,
        "integer": ScalarType.INTEGER,
        "long": ScalarType.INTEGER,
        "number": ScalarType.DECIMAL,
        "double": ScalarType.DECIMAL,
        "decimal": ScalarType.DECIMAL,
        "string": ScalarType.STRING,
        "date": ScalarType.DATE,
    }
    if normalized not in mapping:
        raise DmnImportError(f"unsupported DMN typeRef: {value}")
    return mapping[normalized]


def _decision_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return key if key and key[0].isalpha() else f"dmn_{key or 'decision'}"


def _identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_$]", "_", value.strip())
    return identifier if identifier and re.match(r"[A-Za-z_$]", identifier) else f"D_{identifier}"


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next((child for child in element if _local(child.tag) == name), None)


def _text(element: ET.Element | None) -> str:
    return "" if element is None or element.text is None else element.text.strip()
