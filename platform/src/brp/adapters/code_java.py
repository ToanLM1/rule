"""Candidate-only Java rule mining over bounded Joern slices."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from brp.adapters.contracts import (
    AdapterDiagnostic,
    CandidateDecision,
    ExtractionBatch,
    SourceSnapshot,
    UnmappableItem,
)
from brp.adapters.joern import SliceManifest, SourceSpan
from brp.ir.models import DecisionContent, JavaSourceReference, Rule, SourceReference

CONSTRUCT_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "C1_UNDER_AGE": (("enrollment_eligibility", "R001"),),
    "C2_OVER_AGE_LIMIT": (("enrollment_eligibility", "R002"),),
    "C3_SMOKER_LOADING": (("premium_adjustments", "R001"),),
    "C4_REGION_LOOKUP": (("enrollment_eligibility", "R003"),),
    "C5_OCCUPATION_DOCUMENT": (("required_documents", "R001"),),
    "C6_SENIOR_ADJUSTMENTS": (
        ("premium_adjustments", "R002"),
        ("required_documents", "R002"),
    ),
}


class JavaRuleMiner:
    """Apply recorded structured mining output to immutable source slices.

    Phase 1 deliberately uses reviewed recorded responses. Provider-backed output uses
    the same DecisionContent validation boundary before entering this class.
    """

    name = "code-java"

    def __init__(self, conformance_directory: Path) -> None:
        self.templates = {
            key: DecisionContent.model_validate_json(
                (conformance_directory / f"{key}.json").read_text(encoding="utf-8")
            )
            for key in {
                decision
                for associations in CONSTRUCT_RULES.values()
                for decision, _ in associations
            }
        }

    def mine(
        self, manifest: SliceManifest, *, unsupported_fragments: list[str] | None = None
    ) -> ExtractionBatch:
        slices = {item.construct_id: item for item in manifest.slices}
        missing = sorted(set(CONSTRUCT_RULES) - set(slices))
        if missing:
            raise ValueError(f"slice manifest is missing fixture constructs: {missing}")
        contents = {key: content.model_copy(deep=True) for key, content in self.templates.items()}
        for construct_id, associations in CONSTRUCT_RULES.items():
            item = slices[construct_id]
            references: list[SourceReference] = [
                _reference(span) for span in item.source_references
            ]
            for decision_key, rule_id in associations:
                rule = next(
                    rule for rule in contents[decision_key].rules if rule.rule_id == rule_id
                )
                rule.source_references = references
        for content in contents.values():
            content.rules = collapse_rules(content.rules)

        unmappable = [
            UnmappableItem(
                reason_code="UNSUPPORTED_RAW_CALL",
                raw_fragment=fragment,
                provenance={
                    "repository": manifest.repository,
                    "revision": manifest.revision,
                    "entryPoint": manifest.entry_point,
                },
            )
            for fragment in (unsupported_fragments or [])
        ]
        snapshot_hash = hashlib.sha256(
            json.dumps(
                manifest.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return ExtractionBatch(
            adapter=self.name,
            decisions=[
                CandidateDecision(decision_key=key, content=contents[key])
                for key in sorted(contents)
            ],
            unmappable=unmappable,
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="RECORDED_MINING_COMPLETE",
                    message=f"mapped {len(manifest.slices)} reviewed Java slices",
                )
            ],
            source_snapshot=SourceSnapshot(
                source_id=f"git:{manifest.repository}",
                revision=manifest.revision,
                content_hash=snapshot_hash,
                captured_at=datetime.now(UTC),
            ),
        )


def collapse_rules(rules: list[Rule]) -> list[Rule]:
    """Collapse equal normalized rules while retaining every distinct reference."""
    found: dict[bytes, Rule] = {}
    order: list[bytes] = []
    for rule in rules:
        normalized = rule.model_dump(mode="json", by_alias=True, exclude_none=True)
        normalized["ruleId"] = "NORMALIZED"
        normalized["sourceReferences"] = []
        key = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if key not in found:
            found[key] = rule.model_copy(deep=True)
            order.append(key)
            continue
        existing = found[key]
        serialized = {
            json.dumps(reference.model_dump(mode="json", by_alias=True), sort_keys=True)
            for reference in existing.source_references
        }
        for reference in rule.source_references:
            value = json.dumps(reference.model_dump(mode="json", by_alias=True), sort_keys=True)
            if value not in serialized:
                existing.source_references.append(reference)
                serialized.add(value)
    return [found[key] for key in order]


def _reference(span: SourceSpan) -> JavaSourceReference:
    document = span.model_dump(mode="json", by_alias=True)
    return JavaSourceReference(type="JAVA_SOURCE", **document)
