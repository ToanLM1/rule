"""Export the committed JSON Schema from the canonical Pydantic model."""

from __future__ import annotations

import json
from pathlib import Path

from brp.ir.models import DecisionContent

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = ROOT / "docs" / "ir-v1.schema.json"


def schema_text() -> str:
    schema = DecisionContent.model_json_schema(by_alias=True, mode="validation")
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def export_schema(output: Path = DEFAULT_OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(schema_text(), encoding="utf-8", newline="\n")
    return output


def main() -> int:
    print(export_schema())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
