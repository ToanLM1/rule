"""Deterministic C# target plug-in for Rule IR v1."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field

from brp.config.models import Language, TargetConfig
from brp.generators.contracts import (
    GeneratedArtifact,
    ReleaseInput,
    release_manifest,
)
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DecisionContent,
    FieldDefinition,
    HitPolicy,
    InputOperand,
    LiteralOperand,
    LookupDefinition,
    Operand,
    Operator,
    ScalarType,
    StrictModel,
)


class CSharpGenerationError(ValueError):
    pass


class CompileEvidence(StrictModel):
    status: Literal["COMPILED", "COMPILE_NOT_RUN", "COMPILE_FAILED"]
    sdk_version: str | None = None
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    detail: str


class CSharpGenerator:
    name = "csharp-source"
    version = "1.0.0"

    def supports(self, profile: str, target: TargetConfig) -> bool:
        return (
            profile == "RULE_IR_V1"
            and target.language is Language.CSHARP
            and target.csharp_namespace is not None
        )

    def generate(self, release_input: ReleaseInput) -> list[GeneratedArtifact]:
        if not self.supports(release_input.content.profile, release_input.target):
            raise CSharpGenerationError("csharp-source requires a C# RULE_IR_V1 target")
        if release_input.generator != self.name or release_input.generator_version != self.version:
            raise CSharpGenerationError("release generator identity does not match csharp-source")
        namespace = release_input.target.csharp_namespace
        assert namespace is not None
        class_name = _class_name(release_input.content.decision_id)
        namespace_path = namespace.replace(".", "/")
        source = GeneratedArtifact.create(
            f"{release_input.target.generated_source_path}/{namespace_path}/{class_name}.g.cs",
            _render_decision(release_input.content, namespace, class_name),
        )
        tests = GeneratedArtifact.create(
            f"{release_input.target.generated_test_path}/{namespace_path}/{class_name}GoldenTests.g.cs",
            _render_golden(release_input, namespace, class_name),
        )
        manifest_document = release_manifest(release_input, [source, tests])
        manifest = GeneratedArtifact.create(
            "release-manifest.json",
            json.dumps(manifest_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
        return [source, tests, manifest]


def render_csharp_preview(content: DecisionContent, namespace: str) -> GeneratedArtifact:
    """Render source only for the non-release orchestration workbench."""
    if not namespace or any(not part.isidentifier() for part in namespace.split(".")):
        raise CSharpGenerationError("a valid C# namespace is required")
    class_name = _class_name(content.decision_id)
    return GeneratedArtifact.create(
        f"preview/{namespace.replace('.', '/')}/{class_name}.g.cs",
        _render_decision(content, namespace, class_name),
    )


def verify_csharp_compile(source: GeneratedArtifact) -> CompileEvidence:
    executable = shutil.which("dotnet")
    if executable is None:
        return CompileEvidence(
            status="COMPILE_NOT_RUN",
            source_hash=source.content_hash,
            detail="dotnet SDK is not installed on this host",
        )
    version_result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=False, timeout=30
    )
    version = version_result.stdout.strip()
    if version_result.returncode != 0 or not version:
        return CompileEvidence(
            status="COMPILE_FAILED",
            source_hash=source.content_hash,
            detail="dotnet SDK version probe failed",
        )
    major = version.split(".", 1)[0]
    if not major.isdigit():
        return CompileEvidence(
            status="COMPILE_FAILED",
            sdk_version=version,
            source_hash=source.content_hash,
            detail="dotnet SDK version is not parseable",
        )
    with tempfile.TemporaryDirectory(prefix="brp-csharp-compile-") as directory:
        root = Path(directory)
        (root / "Generated.cs").write_text(source.content, encoding="utf-8", newline="\n")
        (root / "Generated.csproj").write_text(
            (
                '<Project Sdk="Microsoft.NET.Sdk">\n'
                "  <PropertyGroup>\n"
                f"    <TargetFramework>net{major}.0</TargetFramework>\n"
                "    <ImplicitUsings>disable</ImplicitUsings>\n"
                "    <Nullable>enable</Nullable>\n"
                "  </PropertyGroup>\n"
                "</Project>\n"
            ),
            encoding="utf-8",
            newline="\n",
        )
        result = subprocess.run(
            [executable, "build", "Generated.csproj", "--nologo"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    if result.returncode != 0:
        return CompileEvidence(
            status="COMPILE_FAILED",
            sdk_version=version,
            source_hash=source.content_hash,
            detail=(result.stdout + result.stderr)[-1000:] or "dotnet build failed",
        )
    return CompileEvidence(
        status="COMPILED",
        sdk_version=version,
        source_hash=source.content_hash,
        detail="generated decision compiled with dotnet build",
    )


def _render_decision(content: DecisionContent, namespace: str, class_name: str) -> str:
    _require_unique_csharp_names(content)
    lines = [
        "// <auto-generated />",
        f"// Decision: {content.decision_id}",
        "#nullable enable",
        "using System;",
        "using System.Collections.Generic;",
        "using System.Linq;",
        "",
        f"namespace {namespace};",
        "",
        f"public static class {class_name}",
        "{",
        "    public interface ILookupProvider",
        "    {",
        (
            "        object? Resolve(string reference, "
            "IReadOnlyDictionary<string, object?> keys, string field);"
        ),
        "    }",
        "",
        f"    public sealed record Input({_record_fields(content.inputs)});",
        f"    public sealed record Output({_record_fields(content.outputs)});",
        "",
        f"    public static {_return_type(content)} Evaluate(Input input, ILookupProvider lookups)",
        "    {",
    ]
    if content.hit_policy is HitPolicy.FIRST:
        for rule in content.rules:
            lines.extend(
                [
                    f"        if ({_group(rule.when, content)})",
                    f"            return {_output(rule.then, content)};",
                ]
            )
        assert content.default_output is not None
        lines.append(f"        return {_default_output(content)};")
    elif content.hit_policy is HitPolicy.UNIQUE:
        lines.extend(["        Output? matched = null;", "        var matchCount = 0;"])
        for rule in content.rules:
            lines.extend(
                [
                    f"        if ({_group(rule.when, content)})",
                    "        {",
                    "            matchCount++;",
                    f"            matched = {_output(rule.then, content)};",
                    "        }",
                ]
            )
        lines.extend(
            [
                (
                    "        if (matchCount > 1) throw new InvalidOperationException("
                    '"UNIQUE matched multiple rules");'
                ),
                f"        return matched ?? {_default_output(content)};",
            ]
        )
    else:
        lines.append("        var results = new List<Output>();")
        for rule in content.rules:
            lines.extend(
                [
                    f"        if ({_group(rule.when, content)})",
                    f"            results.Add({_output(rule.then, content)});",
                ]
            )
        lines.append("        return results;")
    lines.extend(["    }", "}", ""])
    return "\n".join(lines)


def _render_golden(release: ReleaseInput, namespace: str, class_name: str) -> str:
    content = release.content
    lines = [
        "// <auto-generated />",
        "#nullable enable",
        "using System;",
        "using System.Collections.Generic;",
        "using Xunit;",
        "",
        f"namespace {namespace};",
        "",
        f"public sealed class {class_name}GoldenTests",
        "{",
        f"    private sealed class GoldenLookups : {class_name}.ILookupProvider",
        "    {",
        (
            "        public object? Resolve(string reference, "
            "IReadOnlyDictionary<string, object?> keys, string field)"
        ),
        "        {",
    ]
    lookup_lines = _golden_lookups(release)
    lines.extend(
        lookup_lines or ['            throw new KeyNotFoundException("No lookup snapshots");']
    )
    lines.extend(["        }", "    }", ""])
    for index, case in enumerate(release.golden_suite.cases, 1):
        inputs = case["input"]
        expected = case["expected"]
        arguments = ", ".join(_literal(inputs[item.name], item.type) for item in content.inputs)
        lines.extend(
            [
                "    [Fact]",
                f"    public void GoldenCase{index:03d}()",
                "    {",
                (
                    f"        var actual = {class_name}.Evaluate("
                    f"new {class_name}.Input({arguments}), new GoldenLookups());"
                ),
            ]
        )
        if content.hit_policy is HitPolicy.COLLECT:
            assert isinstance(expected, list)
            lines.append(f"        Assert.Equal({len(expected)}, actual.Count);")
            for item_index, expected_item in enumerate(expected):
                for output in content.outputs:
                    lines.append(
                        "        Assert.Equal("
                        f"{_literal(expected_item[output.name], output.type)}, "
                        f"actual[{item_index}].{_name(output.name)});"
                    )
        else:
            assert isinstance(expected, dict)
            for output in content.outputs:
                lines.append(
                    f"        Assert.Equal({_literal(expected[output.name], output.type)}, "
                    f"actual.{_name(output.name)});"
                )
        lines.extend(["    }", ""])
    lines.extend(["}", ""])
    return "\n".join(lines)


def _golden_lookups(release: ReleaseInput) -> list[str]:
    snapshots = {item.name: item for item in release.lookup_snapshots}
    lines: list[str] = []
    for lookup in release.content.lookups:
        snapshot = snapshots.get(lookup.name) or snapshots.get(lookup.ref)
        if snapshot is None:
            continue
        key_types = {item.name: item.type for item in lookup.keys}
        output_types = {item.name: item.type for item in lookup.outputs}
        for row in snapshot.rows:
            condition = " && ".join(
                f'Equals(keys["{key}"], {_literal(row[key], key_types[key])})'
                for key in sorted(key_types)
            )
            lines.append(f"            if (reference == {_string(lookup.ref)} && {condition})")
            lines.append("            {")
            lines.append("                return field switch")
            lines.append("                {")
            for field in sorted(output_types):
                lines.append(
                    f'                    "{field}" => {_literal(row[field], output_types[field])},'
                )
            lines.extend(
                [
                    "                    _ => throw new KeyNotFoundException(field),",
                    "                };",
                    "            }",
                ]
            )
    lines.append('            throw new KeyNotFoundException($"{reference}:{field}");')
    return lines


def _group(group: ConditionGroup, content: DecisionContent) -> str:
    children = group.all if group.all is not None else group.any
    assert children is not None
    joiner = " && " if group.all is not None else " || "
    return (
        "("
        + joiner.join(
            _condition(item, content) if isinstance(item, Condition) else _group(item, content)
            for item in children
        )
        + ")"
    )


def _condition(condition: Condition, content: DecisionContent) -> str:
    left_type = _operand_type(condition.left, content)
    left = _operand(condition.left, content, left_type)
    if condition.operator is Operator.EXISTS:
        return f"({left} is not null)"
    assert condition.right is not None
    binary = {
        Operator.GT: ">",
        Operator.GTE: ">=",
        Operator.LT: "<",
        Operator.LTE: "<=",
    }
    if condition.operator in {Operator.EQ, Operator.NE, *binary}:
        right = _operand(condition.right, content, left_type)
        if condition.operator is Operator.EQ:
            return f"Equals({left}, {right})"
        if condition.operator is Operator.NE:
            return f"!Equals({left}, {right})"
        return f"({left} {binary[condition.operator]} {right})"
    if condition.operator is Operator.STARTS_WITH:
        right = _operand(condition.right, content, left_type)
        return f"{left}.StartsWith({right}, StringComparison.Ordinal)"
    assert isinstance(condition.right, LiteralOperand)
    assert isinstance(condition.right.value, list)
    if condition.operator in {Operator.IN, Operator.NOT_IN}:
        listed = ", ".join(_literal(item, left_type) for item in condition.right.value)
        expression = f"new[] {{ {listed} }}.Contains({left})"
        return f"!({expression})" if condition.operator is Operator.NOT_IN else expression
    if condition.operator is Operator.BETWEEN:
        low, high = condition.right.value
        return f"({left} >= {_literal(low, left_type)} && {left} <= {_literal(high, left_type)})"
    raise CSharpGenerationError(f"unsupported operator: {condition.operator}")


def _operand(operand: Operand, content: DecisionContent, expected: ScalarType) -> str:
    if isinstance(operand, InputOperand):
        return f"input.{_name(operand.name)}"
    if isinstance(operand, LiteralOperand):
        if isinstance(operand.value, list):
            raise CSharpGenerationError("list literal is only valid for set/range operators")
        return _literal(operand.value, expected)
    lookup = next(item for item in content.lookups if item.name == operand.lookup)
    keys = ", ".join(
        f'{{ "{name}", {_operand(value, content, _lookup_key_type(lookup, name))} }}'
        for name, value in sorted(operand.keys.items())
    )
    call = (
        f"lookups.Resolve({_string(lookup.ref)}, "
        f"new Dictionary<string, object?> {{ {keys} }}, {_string(operand.field)})"
    )
    return _convert(call, expected)


def _operand_type(operand: Operand, content: DecisionContent) -> ScalarType:
    if isinstance(operand, InputOperand):
        return next(item.type for item in content.inputs if item.name == operand.name)
    if isinstance(operand, LiteralOperand):
        value = operand.value[0] if isinstance(operand.value, list) else operand.value
        return _value_type(value)
    lookup = next(item for item in content.lookups if item.name == operand.lookup)
    return next(item.type for item in lookup.outputs if item.name == operand.field)


def _lookup_key_type(lookup: LookupDefinition, name: str) -> ScalarType:
    return next(item.type for item in lookup.keys if item.name == name)


def _output(actions: Sequence[Action], content: DecisionContent) -> str:
    by_name = {item.output: item.value for item in actions}
    return (
        "new Output("
        + ", ".join(_literal(by_name[item.name], item.type) for item in content.outputs)
        + ")"
    )


def _default_output(content: DecisionContent) -> str:
    assert content.default_output is not None
    return (
        "new Output("
        + ", ".join(
            _literal(content.default_output[item.name], item.type) for item in content.outputs
        )
        + ")"
    )


def _record_fields(fields: Sequence[FieldDefinition]) -> str:
    return ", ".join(f"{_csharp_type(item.type)} {_name(item.name)}" for item in fields)


def _return_type(content: DecisionContent) -> str:
    return "IReadOnlyList<Output>" if content.hit_policy is HitPolicy.COLLECT else "Output"


def _literal(value: object, kind: ScalarType) -> str:
    if kind is ScalarType.STRING:
        return _string(str(value))
    if kind is ScalarType.BOOLEAN:
        return "true" if value is True else "false"
    if kind is ScalarType.INTEGER:
        if type(value) is not int:
            raise CSharpGenerationError("integer literal type mismatch")
        return f"{value}L"
    if kind is ScalarType.DECIMAL:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise CSharpGenerationError("decimal literal type mismatch")
        return f"{format(value, '.15g')}m"
    if kind is ScalarType.DATE:
        return f"DateOnly.Parse({_string(str(value))})"
    raise CSharpGenerationError(f"unsupported scalar type: {kind}")


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _convert(expression: str, kind: ScalarType) -> str:
    return {
        ScalarType.STRING: f"Convert.ToString({expression})!",
        ScalarType.BOOLEAN: f"Convert.ToBoolean({expression})",
        ScalarType.INTEGER: f"Convert.ToInt64({expression})",
        ScalarType.DECIMAL: f"Convert.ToDecimal({expression})",
        ScalarType.DATE: f"DateOnly.Parse(Convert.ToString({expression})!)",
    }[kind]


def _csharp_type(kind: ScalarType) -> str:
    return {
        ScalarType.STRING: "string",
        ScalarType.BOOLEAN: "bool",
        ScalarType.INTEGER: "long",
        ScalarType.DECIMAL: "decimal",
        ScalarType.DATE: "DateOnly",
    }[kind]


def _value_type(value: object) -> ScalarType:
    if type(value) is bool:
        return ScalarType.BOOLEAN
    if type(value) is int:
        return ScalarType.INTEGER
    if type(value) is float:
        return ScalarType.DECIMAL
    return ScalarType.STRING


def _class_name(decision_id: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in decision_id.split("_")) + "Decision"


def _name(value: str) -> str:
    clean = value.replace("$", "_")
    return clean[:1].upper() + clean[1:]


def _require_unique_csharp_names(content: DecisionContent) -> None:
    for label, values in (("input", content.inputs), ("output", content.outputs)):
        names = [_name(item.name).lower() for item in values]
        if len(names) != len(set(names)):
            raise CSharpGenerationError(f"{label} names collide after C# normalization")
