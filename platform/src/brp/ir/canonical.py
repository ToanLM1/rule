"""Canonical UTF-8 serialization for Rule IR content hashes and manifests."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from brp.ir.models import DecisionContent


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical IR forbids non-finite numbers")
    if isinstance(value, dict):
        for item in value.values():
            _reject_non_finite(item)
    elif isinstance(value, list):
        for item in value:
            _reject_non_finite(item)


def canonical_bytes(content: DecisionContent | Mapping[str, Any]) -> bytes:
    """Validate and render semantic content with stable keys and preserved list order."""
    decision = (
        content if isinstance(content, DecisionContent) else DecisionContent.model_validate(content)
    )
    document = decision.model_dump(mode="json", by_alias=True, exclude_none=True)
    _reject_non_finite(document)
    text = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("content", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    document = json.loads(args.content.read_text(encoding="utf-8"))
    sys.stdout.buffer.write(canonical_bytes(document) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
