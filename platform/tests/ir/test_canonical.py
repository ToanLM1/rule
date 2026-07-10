import copy
import json
import subprocess
import sys
from pathlib import Path

from brp.ir.canonical import canonical_bytes

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "conformance"
    / "enrollment_eligibility.json"
)


def load() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def reversed_mapping(value: object) -> object:
    if isinstance(value, dict):
        return {key: reversed_mapping(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reversed_mapping(item) for item in value]
    return value


def test_object_key_order_does_not_change_canonical_bytes() -> None:
    document = load()
    assert canonical_bytes(document) == canonical_bytes(reversed_mapping(document))


def test_list_order_remains_semantic() -> None:
    document = load()
    changed = copy.deepcopy(document)
    changed["rules"] = list(reversed(changed["rules"]))
    assert canonical_bytes(document) != canonical_bytes(changed)


def test_korean_is_emitted_as_utf8_not_ascii_escapes() -> None:
    rendered = canonical_bytes(load())
    assert "가입 자격 판정".encode() in rendered
    assert b"\\uac00" not in rendered


def test_fresh_processes_emit_identical_bytes() -> None:
    command = [sys.executable, "-m", "brp.ir.canonical", str(FIXTURE)]
    first = subprocess.check_output(command)
    second = subprocess.check_output(command)
    assert first == second
