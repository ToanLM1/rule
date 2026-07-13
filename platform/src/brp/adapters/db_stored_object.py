"""Fail-closed mining of a restricted scalar PL/pgSQL function subset."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Protocol

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
    DbStoredObjectReference,
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
)


class StoredObjectReader(Protocol):
    def stored_procedure_source(self, schema: str, procedure: str) -> str: ...


class PostgresStoredObjectAdapter:
    name = "db-postgres-stored-object"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def __init__(
        self,
        reader: StoredObjectReader,
        *,
        connection_alias: str,
        objects: list[tuple[str, str]],
    ) -> None:
        if not connection_alias.strip() or not objects:
            raise ValueError("connection alias and stored objects are required")
        self.reader = reader
        self.connection_alias = connection_alias
        self.objects = sorted(set(objects))

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [
            Source(
                source_id=f"db-object:{schema}.{name}",
                kind="postgres-stored-object",
                locator={"schema": schema, "objectName": name},
            )
            for schema, name in self.objects
        ]

    def extract(self, source: Source) -> ExtractionBatch:
        schema = str(source.locator["schema"])
        name = str(source.locator["objectName"])
        text = self.reader.stored_procedure_source(schema, name)
        raw = text.encode("utf-8")
        revision = hashlib.sha256(raw).hexdigest()
        snapshot = SourceSnapshot(
            source_id=source.source_id,
            revision=revision,
            content_hash=revision,
            captured_at=datetime.now(UTC),
        )
        try:
            content = self._parse(schema, name, text, revision)
        except RestrictedProcedureError as exc:
            return ExtractionBatch(
                adapter=self.name,
                unmappable=[
                    UnmappableItem(
                        reason_code=exc.reason,
                        raw_fragment=exc.fragment,
                        provenance={
                            "type": "DB_STORED_OBJECT",
                            "connectionAlias": self.connection_alias,
                            "schema": schema,
                            "objectName": name,
                            "revision": revision,
                            "lineStart": exc.line,
                        },
                    )
                ],
                diagnostics=[
                    AdapterDiagnostic(
                        level="WARNING",
                        code="STORED_OBJECT_REVIEW_REQUIRED",
                        message=f"{schema}.{name} is outside the restricted PL/pgSQL profile",
                    )
                ],
                source_snapshot=snapshot,
            )
        return ExtractionBatch(
            adapter=self.name,
            decisions=[CandidateDecision(decision_key=_identifier(name).lower(), content=content)],
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="STORED_OBJECT_MAPPED",
                    message=f"mapped restricted function {schema}.{name}",
                )
            ],
            source_snapshot=snapshot,
        )

    def _parse(self, schema: str, expected_name: str, text: str, revision: str) -> DecisionContent:
        signature = re.search(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(?:[\w\"]+\.)?[\"]?([A-Za-z_][\w$]*)[\"]?\s*"
            r"\((.*?)\)\s*RETURNS\s+([\w\s]+?)\s+AS\s+\$\$(.*?)\$\$\s+LANGUAGE\s+plpgsql",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if signature is None or signature.group(1).lower() != expected_name.lower():
            raise RestrictedProcedureError("INVALID_STORED_OBJECT", text[:1000], 1)
        inputs = _parameters(signature.group(2))
        output_type = _scalar_type(signature.group(3).strip())
        body = signature.group(4)
        body_start_line = text[: signature.start(4)].count("\n") + 1
        cleaned = re.sub(r"--[^\n]*", "", body)
        branches = list(
            re.finditer(
                r"\b(IF|ELSIF)\s+(.+?)\s+THEN\s+RETURN\s+(.+?)\s*;",
                cleaned,
                re.IGNORECASE | re.DOTALL,
            )
        )
        default_match = re.search(
            r"\bELSE\s+RETURN\s+(.+?)\s*;\s*END\s+IF\s*;",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if not branches or default_match is None:
            raise RestrictedProcedureError(
                "UNSUPPORTED_PROCEDURE_CONTROL_FLOW", body.strip()[:1000], body_start_line
            )
        recognized = "\n".join(match.group(0) for match in branches) + default_match.group(0)
        residual = cleaned
        for match in [*branches, default_match]:
            residual = residual.replace(match.group(0), "")
        residual = re.sub(r"\b(BEGIN|END)\b\s*;?", "", residual, flags=re.IGNORECASE)
        if residual.strip():
            line = body_start_line + cleaned[: cleaned.find(residual.strip())].count("\n")
            raise RestrictedProcedureError(
                "UNSUPPORTED_PROCEDURE_STATEMENT", residual.strip()[:1000], line
            )
        del recognized
        input_by_name = {item.name.lower(): item for item in inputs}
        rules: list[Rule] = []
        for index, branch in enumerate(branches, 1):
            field, operator, literal_text = _comparison(branch.group(2))
            definition = input_by_name.get(field.lower())
            if definition is None:
                raise RestrictedProcedureError(
                    "UNKNOWN_PROCEDURE_INPUT",
                    branch.group(2).strip(),
                    body_start_line + cleaned[: branch.start(2)].count("\n"),
                )
            value = _literal(literal_text, definition.type)
            output = _literal(branch.group(3), output_type)
            line_start = body_start_line + cleaned[: branch.start()].count("\n")
            line_end = body_start_line + cleaned[: branch.end()].count("\n")
            reference = DbStoredObjectReference(
                type="DB_STORED_OBJECT",
                connection_alias=self.connection_alias,
                schema=schema,
                object_name=expected_name,
                object_kind="FUNCTION",
                revision=revision,
                line_start=line_start,
                line_end=line_end,
            )
            rules.append(
                Rule(
                    rule_id=f"R{index:03d}",
                    when=ConditionGroup(
                        all=[
                            Condition(
                                left=InputOperand(kind="INPUT", name=definition.name),
                                operator=operator,
                                right=LiteralOperand(kind="LITERAL", value=value),
                            )
                        ]
                    ),
                    then=[Action(output="result", value=output)],
                    origin=RuleOrigin.EXTRACTED,
                    source_references=[reference],
                    confidence=1.0,
                )
            )
        default_output = _literal(default_match.group(1), output_type)
        decision_id = _identifier(expected_name).lower()
        return DecisionContent(
            decision_id=decision_id,
            decision_name=expected_name,
            profile="RULE_IR_V1",
            schema_version=1,
            program_contexts=[
                ProgramContext(
                    program_id="DB-STORED-OBJECT",
                    kind=ProgramKind.SERVICE,
                    entry_point=f"postgres://{schema}/{expected_name}",
                )
            ],
            hit_policy=HitPolicy.FIRST,
            inputs=inputs,
            outputs=[OutputDefinition(name="result", type=output_type)],
            default_output={"result": default_output},
            rules=rules,
        )


class RestrictedProcedureError(ValueError):
    def __init__(self, reason: str, fragment: str, line: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.fragment = fragment or reason
        self.line = max(line, 1)


def _parameters(text: str) -> list[InputDefinition]:
    if not text.strip():
        raise RestrictedProcedureError("PROCEDURE_INPUT_REQUIRED", text or "()", 1)
    parameters: list[InputDefinition] = []
    for item in text.split(","):
        match = re.fullmatch(
            r"\s*([A-Za-z_][\w$]*)\s+([A-Za-z]+(?:\s+precision)?)\s*",
            item,
            re.IGNORECASE,
        )
        if match is None:
            raise RestrictedProcedureError("UNSUPPORTED_PROCEDURE_SIGNATURE", item, 1)
        name = _identifier(match.group(1)).lower()
        parameters.append(
            InputDefinition(name=name, source_path=name, type=_scalar_type(match.group(2)))
        )
    return parameters


def _comparison(text: str) -> tuple[str, Operator, str]:
    match = re.fullmatch(r"\s*([A-Za-z_][\w$]*)\s*(<=|>=|<>|!=|=|<|>)\s*(.+?)\s*", text)
    if match is None or re.search(r"\b(AND|OR|SELECT|CALL)\b", text, re.IGNORECASE):
        raise RestrictedProcedureError("UNSUPPORTED_PROCEDURE_CONDITION", text, 1)
    operator = {
        "=": Operator.EQ,
        "!=": Operator.NE,
        "<>": Operator.NE,
        "<": Operator.LT,
        "<=": Operator.LTE,
        ">": Operator.GT,
        ">=": Operator.GTE,
    }[match.group(2)]
    return match.group(1), operator, match.group(3)


def _scalar_type(value: str) -> ScalarType:
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    if normalized in {"smallint", "integer", "int", "bigint"}:
        return ScalarType.INTEGER
    if normalized in {"numeric", "decimal", "real", "double precision"}:
        return ScalarType.DECIMAL
    if normalized in {"text", "varchar", "character varying"}:
        return ScalarType.STRING
    if normalized in {"boolean", "bool"}:
        return ScalarType.BOOLEAN
    if normalized == "date":
        return ScalarType.DATE
    raise RestrictedProcedureError("UNSUPPORTED_PROCEDURE_TYPE", value, 1)


def _literal(value: str, kind: ScalarType) -> bool | int | float | str:
    text = value.strip()
    try:
        if kind is ScalarType.STRING:
            if len(text) < 2 or text[0] != "'" or text[-1] != "'":
                raise ValueError
            return text[1:-1].replace("''", "'")
        if kind is ScalarType.BOOLEAN:
            if text.lower() not in {"true", "false"}:
                raise ValueError
            return text.lower() == "true"
        if kind is ScalarType.INTEGER:
            return int(text)
        if kind is ScalarType.DECIMAL:
            return float(text)
        if kind is ScalarType.DATE:
            match = re.fullmatch(r"DATE\s+'(\d{4}-\d{2}-\d{2})'", text, re.IGNORECASE)
            if match is None:
                raise ValueError
            return match.group(1)
    except ValueError as exc:
        raise RestrictedProcedureError("UNSUPPORTED_PROCEDURE_LITERAL", text, 1) from exc
    raise RestrictedProcedureError("UNSUPPORTED_PROCEDURE_LITERAL", text, 1)


def _identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_$]", "_", value.strip())
    if not identifier or not re.match(r"[A-Za-z_$]", identifier):
        return f"D_{identifier or 'decision'}"
    return identifier
