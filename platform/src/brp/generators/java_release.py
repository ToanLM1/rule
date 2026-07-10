"""Deterministic JUnit and manifest rendering for generated Java releases."""

from __future__ import annotations

import json

from brp.generators.contracts import GeneratedArtifact, ReleaseInput, release_manifest
from brp.ir.models import HitPolicy, ScalarType


def java_class_name(decision_id: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in decision_id.split("_")) + "Decision"


def render_golden_junit(release: ReleaseInput) -> GeneratedArtifact:
    content = release.content
    class_name = java_class_name(content.decision_id)
    lines = [
        f"package {release.target.java_package};",
        "",
        "import static org.junit.jupiter.api.Assertions.assertEquals;",
        "import java.math.BigDecimal;",
        "import java.time.LocalDate;",
        "import java.util.Map;",
        "import org.junit.jupiter.api.Test;",
        "",
        f"final class {class_name}GoldenTest {{",
    ]
    for index, case in enumerate(release.golden_suite.cases, 1):
        inputs = case["input"]
        expected = case["expected"]
        arguments = ", ".join(
            _java_value(inputs[field.name], field.type) for field in content.inputs
        )
        lines.extend(
            [
                "  @Test",
                f"  void goldenCase{index:03d}() {{",
                f"    var actual = {class_name}.evaluate("
                f"new {class_name}.Input({arguments}), (name, keys) -> Map.of());",
            ]
        )
        if content.hit_policy is HitPolicy.COLLECT:
            assert isinstance(expected, list)
            lines.append(f"    assertEquals({len(expected)}, actual.size());")
            for item_index, item in enumerate(expected):
                for output in content.outputs:
                    lines.append(
                        "    assertEquals("
                        f"{_java_value(item[output.name], output.type)}, "
                        f"actual.get({item_index}).{output.name}());"
                    )
        else:
            assert isinstance(expected, dict)
            for output in content.outputs:
                lines.append(
                    "    assertEquals("
                    f"{_java_value(expected[output.name], output.type)}, "
                    f"actual.{output.name}());"
                )
        lines.extend(("  }", ""))
    lines.append("}")
    text = "\n".join(lines) + "\n"
    path = (
        "src/generatedTest/java/"
        + release.target.java_package.replace(".", "/")
        + f"/{class_name}GoldenTest.java"
    )
    return GeneratedArtifact.create(path, text)


def render_manifest(release: ReleaseInput, artifacts: list[GeneratedArtifact]) -> GeneratedArtifact:
    document = release_manifest(release, artifacts)
    text = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return GeneratedArtifact.create("release-manifest.json", text)


def _java_value(value: object, kind: ScalarType) -> str:
    if kind is ScalarType.STRING:
        return json.dumps(value, ensure_ascii=False)
    if kind is ScalarType.BOOLEAN:
        return str(value).lower()
    if kind is ScalarType.INTEGER:
        return str(value)
    if kind is ScalarType.DECIMAL:
        return f'new BigDecimal("{value}")'
    if kind is ScalarType.DATE:
        return f'LocalDate.parse("{value}")'
    raise ValueError(kind)
