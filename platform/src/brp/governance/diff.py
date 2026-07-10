"""Stable semantic comparison for canonical decision content."""

from __future__ import annotations

from typing import Any

from brp.ir.models import DecisionContent


def semantic_diff(before: DecisionContent, after: DecisionContent) -> dict[str, Any]:
    """Compare named IR structures and preserve rule-order changes explicitly."""
    before_document = before.model_dump(mode="json", by_alias=True, exclude_none=True)
    after_document = after.model_dump(mode="json", by_alias=True, exclude_none=True)
    before_rules = _keyed(before_document.pop("rules"), "ruleId")
    after_rules = _keyed(after_document.pop("rules"), "ruleId")

    before_ids = list(before_rules)
    after_ids = list(after_rules)
    added = sorted(set(after_rules) - set(before_rules))
    removed = sorted(set(before_rules) - set(after_rules))
    changed: list[dict[str, Any]] = []
    for rule_id in sorted(set(before_rules) & set(after_rules)):
        changes = _changes(before_rules[rule_id], after_rules[rule_id], f"/rules/{rule_id}")
        if changes:
            changed.append({"ruleId": rule_id, "fieldChanges": changes})

    metadata_changes = _changes(before_document, after_document, "")
    if before_ids != after_ids:
        metadata_changes.append({"path": "/rules/order", "before": before_ids, "after": after_ids})
    metadata_changes.sort(key=lambda item: item["path"])
    return {
        "addedRules": added,
        "removedRules": removed,
        "changedRules": changed,
        "metadataChanges": metadata_changes,
    }


def _keyed(value: Any, key: str) -> dict[str, dict[str, Any]]:
    assert isinstance(value, list)
    return {str(item[key]): item for item in value}


def _changes(before: Any, after: Any, path: str) -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path or "/", "before": before, "after": after}]
    if isinstance(before, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}/{_escape(key)}"
            if key not in before:
                changes.append({"path": child_path, "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child_path, "before": before[key], "after": None})
            else:
                changes.extend(_changes(before[key], after[key], child_path))
        return changes
    if isinstance(before, list):
        key = _semantic_key(before, after)
        if key is not None:
            return _changes(_keyed(before, key), _keyed(after, key), path)
        if before != after:
            return [{"path": path or "/", "before": before, "after": after}]
        return []
    if before != after:
        return [{"path": path or "/", "before": before, "after": after}]
    return []


def _semantic_key(before: list[Any], after: list[Any]) -> str | None:
    combined = [*before, *after]
    if not combined or not all(isinstance(item, dict) for item in combined):
        return None
    for candidate in ("name", "programId", "ruleId"):
        if all(candidate in item for item in combined):
            return candidate
    return None


def _escape(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")
