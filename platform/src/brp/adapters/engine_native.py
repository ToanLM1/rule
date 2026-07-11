"""Restricted DRL import and fail-closed classification of unsupported engine assets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
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
from brp.adapters.dmn import BpmnDocumentError
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DecisionContent,
    EngineAssetReference,
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


class EngineNativeAdapter:
    name = "engine-native"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def __init__(self, paths: list[Path], *, asset_revision: str) -> None:
        if not asset_revision.strip():
            raise ValueError("immutable engine asset revision is required")
        self.paths = [path.resolve() for path in paths]
        self.asset_revision = asset_revision

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [
            Source(
                source_id=f"engine:{path.name}",
                kind="engine-native-asset",
                locator={
                    "path": str(path),
                    "assetId": path.name,
                    "assetRevision": self.asset_revision,
                },
            )
            for path in sorted(self.paths)
            if path.suffix.lower() in {".drl", ".odm", ".xml", ".bpmn"}
        ]

    def extract(self, source: Source) -> ExtractionBatch:
        path = Path(str(source.locator["path"]))
        raw = path.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()
        snapshot = SourceSnapshot(
            source_id=source.source_id,
            revision=self.asset_revision,
            content_hash=content_hash,
            captured_at=datetime.now(UTC),
        )
        upper = raw[:4096].upper()
        if path.suffix.lower() == ".bpmn" or b"/BPMN/" in upper:
            raise BpmnDocumentError(
                "BPMN workflow assets cannot be imported as engine decision rules"
            )
        if path.suffix.lower() != ".drl":
            return ExtractionBatch(
                adapter=self.name,
                unmappable=[
                    UnmappableItem(
                        reason_code="ODM_FORMAT_REQUIRES_CUSTOMER_MAPPING",
                        raw_fragment=raw.decode("utf-8", errors="replace")[:2000],
                        provenance={
                            "type": "ENGINE_ASSET",
                            "engineFormat": "ODM",
                            "assetId": path.name,
                            "revision": self.asset_revision,
                            "contentHash": content_hash,
                        },
                    )
                ],
                diagnostics=[
                    AdapterDiagnostic(
                        level="WARNING",
                        code="ODM_REVIEW_REQUIRED",
                        message="ODM artifact version/mapping requires customer samples",
                    )
                ],
                source_snapshot=snapshot,
            )
        text = raw.decode("utf-8")
        decision, review = self._drl(path, text, content_hash)
        return ExtractionBatch(
            adapter=self.name,
            decisions=[] if decision is None else [decision],
            unmappable=review,
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="DRL_IMPORT_COMPLETE",
                    message=(
                        f"imported {0 if decision is None else 1} decision; "
                        f"{len(review)} review items"
                    ),
                )
            ],
            source_snapshot=snapshot,
        )

    def _drl(
        self, path: Path, text: str, content_hash: str
    ) -> tuple[CandidateDecision | None, list[UnmappableItem]]:
        blocks = list(
            re.finditer(
                r"(?ms)^\s*rule\s+(?:\"([^\"]+)\"|([A-Za-z_][\w$]*))(.*?)^\s*end\s*$",
                text,
            )
        )
        if not blocks:
            return None, [self._review(path, content_hash, "NO_DRL_RULES", text[:2000], 1, "drl")]
        parsed: list[_DrlRule] = []
        review: list[UnmappableItem] = []
        for block in blocks:
            name = block.group(1) or block.group(2)
            rule_offset = block.start() + block.group(0).lower().index("rule")
            line_start = text[:rule_offset].count("\n") + 1
            line_end = text[: block.end()].count("\n") + 1
            try:
                parsed.append(_parse_rule(name, block.group(3), line_start, line_end))
            except DrlSubsetError as exc:
                review.append(
                    self._review(
                        path,
                        content_hash,
                        exc.reason,
                        block.group(0),
                        line_start,
                        name,
                    )
                )
        defaults = [item for item in parsed if not item.conditions]
        conditional = [item for item in parsed if item.conditions]
        if len(defaults) != 1:
            review.append(
                self._review(
                    path,
                    content_hash,
                    "DRL_DEFAULT_REQUIRED",
                    "restricted DRL import requires exactly one unconditional default rule",
                    1,
                    "default",
                )
            )
            return None, review
        if not conditional:
            return None, review
        default = defaults[0]
        output_types = _types(default.actions)
        input_types: dict[str, ScalarType] = {}
        for item in conditional:
            if _types(item.actions) != output_types:
                review.append(
                    self._review(
                        path,
                        content_hash,
                        "INCONSISTENT_DRL_OUTPUTS",
                        item.name,
                        item.line_start,
                        item.name,
                    )
                )
                return None, review
            for field, _operator, value in item.conditions:
                kind = _value_type(value)
                if field in input_types and input_types[field] is not kind:
                    review.append(
                        self._review(
                            path,
                            content_hash,
                            "INCONSISTENT_DRL_INPUT_TYPE",
                            field,
                            item.line_start,
                            item.name,
                        )
                    )
                    return None, review
                input_types[field] = kind
        rules: list[Rule] = []
        for index, item in enumerate(conditional, 1):
            reference = EngineAssetReference(
                type="ENGINE_ASSET",
                engine_format="DRL",
                asset_id=path.name,
                revision=self.asset_revision,
                content_hash=content_hash,
                rule_id=item.name,
                line_start=item.line_start,
                line_end=item.line_end,
            )
            rules.append(
                Rule(
                    rule_id=f"R{index:03d}",
                    when=ConditionGroup(
                        all=[
                            Condition(
                                left=InputOperand(kind="INPUT", name=field),
                                operator=operator,
                                right=LiteralOperand(kind="LITERAL", value=value),
                            )
                            for field, operator, value in item.conditions
                        ]
                    ),
                    then=[Action(output=name, value=value) for name, value in item.actions],
                    origin=RuleOrigin.EXTRACTED,
                    source_references=[reference],
                    confidence=1.0,
                )
            )
        decision_key = _decision_key(path.stem)
        content = DecisionContent(
            decision_id=decision_key,
            decision_name=path.stem,
            profile="RULE_IR_V1",
            schema_version=1,
            program_contexts=[
                ProgramContext(
                    program_id="ENGINE-DRL",
                    kind=ProgramKind.SERVICE,
                    entry_point=f"drl://{path.name}",
                )
            ],
            hit_policy=HitPolicy.FIRST,
            inputs=[
                InputDefinition(name=name, source_path=name, type=input_types[name])
                for name in sorted(input_types)
            ],
            outputs=[
                OutputDefinition(name=name, type=output_types[name])
                for name in sorted(output_types)
            ],
            default_output={name: value for name, value in default.actions},
            rules=rules,
        )
        return CandidateDecision(decision_key=decision_key, content=content), review

    def _review(
        self,
        path: Path,
        content_hash: str,
        reason: str,
        raw: str,
        line: int,
        rule_id: str,
    ) -> UnmappableItem:
        return UnmappableItem(
            reason_code=reason,
            raw_fragment=raw,
            provenance={
                "type": "ENGINE_ASSET",
                "engineFormat": "DRL",
                "assetId": path.name,
                "revision": self.asset_revision,
                "contentHash": content_hash,
                "ruleId": rule_id,
                "lineStart": line,
            },
        )


@dataclass(frozen=True)
class _DrlRule:
    name: str
    conditions: tuple[tuple[str, Operator, JsonScalar], ...]
    actions: tuple[tuple[str, JsonScalar], ...]
    line_start: int
    line_end: int


class DrlSubsetError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _parse_rule(name: str, body: str, line_start: int, line_end: int) -> _DrlRule:
    sections = re.fullmatch(r"(?s)(.*?)\bwhen\b(.*?)\bthen\b(.*)", body, re.IGNORECASE)
    if sections is None:
        raise DrlSubsetError("INVALID_DRL_RULE")
    attributes, when, then = sections.groups()
    attributes = re.sub(r"(?m)^\s*salience\s+-?\d+\s*$", "", attributes)
    if attributes.strip():
        raise DrlSubsetError("UNSUPPORTED_DRL_ATTRIBUTE")
    fact = re.fullmatch(
        r"\s*(?:\$[A-Za-z_]\w*\s*:\s*)?[A-Za-z_][\w.]*\s*\((.*?)\)\s*",
        when,
        re.DOTALL,
    )
    if fact is None:
        raise DrlSubsetError("UNSUPPORTED_DRL_CONDITION")
    condition_text = fact.group(1).strip()
    conditions: list[tuple[str, Operator, JsonScalar]] = []
    if condition_text:
        for expression in re.split(r"\s*(?:,|&&)\s*", condition_text):
            match = re.fullmatch(r"([A-Za-z_$][\w$]*)\s*(==|!=|<=|>=|<|>)\s*(.+)", expression)
            if match is None:
                raise DrlSubsetError("UNSUPPORTED_DRL_CONDITION")
            conditions.append((match.group(1), _operator(match.group(2)), _literal(match.group(3))))
    action_matches = list(
        re.finditer(
            r"\s*result\.set([A-Z][A-Za-z0-9_$]*)\s*\((.*?)\)\s*;",
            then,
            re.DOTALL,
        )
    )
    residual = then
    for match in action_matches:
        residual = residual.replace(match.group(0), "")
    residual = re.sub(r"(?m)//[^\n]*", "", residual)
    if not action_matches or residual.strip():
        raise DrlSubsetError("UNSUPPORTED_DRL_CONSEQUENCE")
    actions = tuple(
        (_lower_camel(match.group(1)), _literal(match.group(2))) for match in action_matches
    )
    if len({name for name, _value in actions}) != len(actions):
        raise DrlSubsetError("DUPLICATE_DRL_OUTPUT")
    return _DrlRule(name, tuple(conditions), actions, line_start, line_end)


def _literal(value: str) -> JsonScalar:
    text = value.strip()
    if text.startswith('"') and text.endswith('"'):
        decoded = json.loads(text)
        if isinstance(decoded, str):
            return decoded
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    raise DrlSubsetError("UNSUPPORTED_DRL_LITERAL")


def _operator(value: str) -> Operator:
    return {
        "==": Operator.EQ,
        "!=": Operator.NE,
        "<": Operator.LT,
        "<=": Operator.LTE,
        ">": Operator.GT,
        ">=": Operator.GTE,
    }[value]


def _value_type(value: JsonScalar) -> ScalarType:
    if type(value) is bool:
        return ScalarType.BOOLEAN
    if type(value) is int:
        return ScalarType.INTEGER
    if type(value) is float:
        return ScalarType.DECIMAL
    return ScalarType.STRING


def _types(actions: tuple[tuple[str, JsonScalar], ...]) -> dict[str, ScalarType]:
    return {name: _value_type(value) for name, value in actions}


def _lower_camel(value: str) -> str:
    return value[0].lower() + value[1:]


def _decision_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return key if key and key[0].isalpha() else f"engine_{key or 'decision'}"
