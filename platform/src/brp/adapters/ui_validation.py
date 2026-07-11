"""Static HTML validation metadata to candidate Rule IR; scripts are never executed."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
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
    HitPolicy,
    InputDefinition,
    InputOperand,
    LiteralOperand,
    Operator,
    OutputDefinition,
    ProgramContext,
    ProgramKind,
    Rule,
    RuleOrigin,
    ScalarType,
    UiElementReference,
)


class HtmlValidationAdapter:
    name = "ui-html-validation"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def __init__(self, paths: list[Path], *, asset_revision: str) -> None:
        if not asset_revision.strip():
            raise ValueError("immutable UI asset revision is required")
        self.paths = [path.resolve() for path in paths]
        self.asset_revision = asset_revision

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [
            Source(
                source_id=f"ui:{path.name}",
                kind="html-validation",
                locator={
                    "path": str(path),
                    "assetId": path.name,
                    "assetRevision": self.asset_revision,
                },
            )
            for path in sorted(self.paths)
            if path.suffix.lower() in {".html", ".htm"}
        ]

    def extract(self, source: Source) -> ExtractionBatch:
        path = Path(str(source.locator["path"]))
        raw = path.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()
        parser = _ValidationParser()
        parser.feed(raw.decode("utf-8"))
        parser.close()
        inputs: dict[str, InputDefinition] = {}
        rules: list[Rule] = []
        unmappable = [
            self._review(source, content_hash, fragment, reason, line, element_id)
            for fragment, reason, line, element_id in parser.review
        ]
        for element in parser.inputs:
            field = element.attributes.get("name", "").strip()
            if not field or not _valid_identifier(field):
                unmappable.append(
                    self._review(
                        source,
                        content_hash,
                        element.raw,
                        "INVALID_UI_FIELD",
                        element.line,
                        element.element_id,
                    )
                )
                continue
            kind = _input_type(element.attributes)
            existing = inputs.get(field)
            if existing is not None and existing.type is not kind:
                unmappable.append(
                    self._review(
                        source,
                        content_hash,
                        element.raw,
                        "CONFLICTING_UI_FIELD_TYPE",
                        element.line,
                        element.element_id,
                    )
                )
                continue
            inputs[field] = InputDefinition(name=field, source_path=field, type=kind)
            unsupported = _unsupported_attributes(element.attributes)
            for attribute in unsupported:
                unmappable.append(
                    self._review(
                        source,
                        content_hash,
                        element.raw,
                        "UNSUPPORTED_UI_VALIDATION",
                        element.line,
                        f"{element.element_id}@{attribute}",
                    )
                )
            try:
                validations = _validations(element.attributes, field, kind)
            except ValueError:
                unmappable.append(
                    self._review(
                        source,
                        content_hash,
                        element.raw,
                        "INVALID_UI_VALIDATION_LITERAL",
                        element.line,
                        element.element_id,
                    )
                )
                continue
            for operator, value, error in validations:
                reference = UiElementReference(
                    type="UI_ELEMENT",
                    asset_id=str(source.locator["assetId"]),
                    revision=content_hash,
                    file=path.name,
                    element_id=element.element_id,
                    line=element.line,
                )
                rules.append(
                    Rule(
                        rule_id=f"R{len(rules) + 1:03d}",
                        when=ConditionGroup(
                            all=[
                                Condition(
                                    left=InputOperand(kind="INPUT", name=field),
                                    operator=operator,
                                    right=LiteralOperand(kind="LITERAL", value=value),
                                )
                            ]
                        ),
                        then=[
                            Action(output="valid", value=False),
                            Action(output="reasonCode", value=error),
                        ],
                        origin=RuleOrigin.EXTRACTED,
                        source_references=[reference],
                        confidence=1.0,
                    )
                )
        decisions: list[CandidateDecision] = []
        if rules:
            decision_id = _decision_key(parser.form_id or path.stem)
            content = DecisionContent(
                decision_id=decision_id,
                decision_name=parser.form_name or path.stem,
                profile="RULE_IR_V1",
                schema_version=1,
                program_contexts=[
                    ProgramContext(
                        program_id="UI-VALIDATION",
                        kind=ProgramKind.SCREEN,
                        entry_point=f"ui://{path.name}#{parser.form_id or 'form'}",
                    )
                ],
                hit_policy=HitPolicy.FIRST,
                inputs=[inputs[name] for name in sorted(inputs)],
                outputs=[
                    OutputDefinition(name="valid", type=ScalarType.BOOLEAN),
                    OutputDefinition(name="reasonCode", type=ScalarType.STRING),
                ],
                default_output={"valid": True, "reasonCode": ""},
                rules=rules,
            )
            decisions.append(CandidateDecision(decision_key=decision_id, content=content))
        if not decisions and not unmappable:
            unmappable.append(
                self._review(
                    source,
                    content_hash,
                    path.name,
                    "NO_UI_VALIDATIONS",
                    1,
                    parser.form_id or "document",
                )
            )
        return ExtractionBatch(
            adapter=self.name,
            decisions=decisions,
            unmappable=unmappable,
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="UI_VALIDATION_SCAN_COMPLETE",
                    message=f"mapped {len(rules)} validations; {len(unmappable)} review items",
                )
            ],
            source_snapshot=SourceSnapshot(
                source_id=source.source_id,
                revision=self.asset_revision,
                content_hash=content_hash,
                captured_at=datetime.now(UTC),
            ),
        )

    @staticmethod
    def _review(
        source: Source,
        revision: str,
        fragment: str,
        reason: str,
        line: int,
        element_id: str,
    ) -> UnmappableItem:
        return UnmappableItem(
            reason_code=reason,
            raw_fragment=fragment,
            provenance={
                "type": "UI_ELEMENT",
                "assetId": source.locator["assetId"],
                "revision": revision,
                "line": line,
                "elementId": element_id,
            },
        )


class _Element:
    def __init__(self, attributes: dict[str, str], raw: str, line: int, element_id: str) -> None:
        self.attributes = attributes
        self.raw = raw
        self.line = line
        self.element_id = element_id


class _ValidationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inputs: list[_Element] = []
        self.review: list[tuple[str, str, int, str]] = []
        self.form_id: str | None = None
        self.form_name: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        line, _ = self.getpos()
        if tag == "form" and self.form_id is None:
            self.form_id = attributes.get("id")
            self.form_name = attributes.get("aria-label") or attributes.get("name")
        if tag == "script":
            self.review.append(("<script>", "UNSUPPORTED_UI_SCRIPT", line, "script"))
            return
        if tag != "input":
            return
        element_id = attributes.get("id") or f"input-{len(self.inputs) + 1}"
        self.inputs.append(
            _Element(attributes, self.get_starttag_text() or "<input>", line, element_id)
        )


def _input_type(attributes: dict[str, str]) -> ScalarType:
    explicit = attributes.get("data-rule-type", "").lower()
    html_type = attributes.get("type", "text").lower()
    if explicit == "integer":
        return ScalarType.INTEGER
    if explicit == "decimal" or html_type in {"number", "range"}:
        return ScalarType.DECIMAL
    if explicit == "boolean" or html_type == "checkbox":
        return ScalarType.BOOLEAN
    if explicit == "date" or html_type == "date":
        return ScalarType.DATE
    return ScalarType.STRING


def _unsupported_attributes(attributes: dict[str, str]) -> list[str]:
    unsupported = {"required", "pattern", "minlength", "maxlength"} & attributes.keys()
    unsupported.update(
        name for name in attributes if name.startswith(("on", "v-", "ng-", ":", "@"))
    )
    return sorted(unsupported)


def _validations(
    attributes: dict[str, str], field: str, kind: ScalarType
) -> list[tuple[Operator, bool | int | float | str | list[bool | int | float | str], str]]:
    values: list[
        tuple[Operator, bool | int | float | str | list[bool | int | float | str], str]
    ] = []
    if "min" in attributes:
        values.append(
            (
                Operator.LT,
                _literal(attributes["min"], kind),
                attributes.get("data-error-min") or f"{field}_MIN",
            )
        )
    if "max" in attributes:
        values.append(
            (
                Operator.GT,
                _literal(attributes["max"], kind),
                attributes.get("data-error-max") or f"{field}_MAX",
            )
        )
    if "data-rule-eq" in attributes:
        values.append(
            (
                Operator.NE,
                _literal(attributes["data-rule-eq"], kind),
                attributes.get("data-error-eq") or f"{field}_EQ",
            )
        )
    if "data-rule-in" in attributes:
        items = [item.strip() for item in attributes["data-rule-in"].split(",")]
        if any(not item for item in items):
            raise ValueError("data-rule-in values cannot be empty")
        values.append(
            (
                Operator.NOT_IN,
                [_literal(item, kind) for item in items],
                attributes.get("data-error-in") or f"{field}_IN",
            )
        )
    return values


def _literal(value: str, kind: ScalarType) -> bool | int | float | str:
    if kind is ScalarType.BOOLEAN:
        if value.lower() not in {"true", "false"}:
            raise ValueError(f"invalid boolean UI literal: {value}")
        return value.lower() == "true"
    if kind is ScalarType.INTEGER:
        return int(value)
    if kind is ScalarType.DECIMAL:
        return float(value)
    return value


def _valid_identifier(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", value) is not None


def _decision_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return key if key and key[0].isalpha() else f"ui_{key or 'validation'}"
