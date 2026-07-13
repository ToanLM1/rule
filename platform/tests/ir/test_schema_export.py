import json
from pathlib import Path

from brp.ir.schema_export import DEFAULT_OUTPUT, schema_text


def test_committed_schema_matches_fresh_export() -> None:
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == schema_text()


def test_schema_describes_content_not_repository_envelope() -> None:
    schema = json.loads(schema_text())
    properties = schema["properties"]
    assert "decisionId" in properties
    assert "status" not in properties
    assert "revision" not in properties
    assert schema["additionalProperties"] is False


def test_schema_output_is_inside_repository_docs() -> None:
    root = Path(__file__).resolve().parents[3]
    assert root / "docs" / "ir-v1.schema.json" == DEFAULT_OUTPUT
