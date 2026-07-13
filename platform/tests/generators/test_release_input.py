import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from brp.config.models import load_site_profile
from brp.generators.contracts import (
    GeneratedArtifact,
    GoldenReleaseEvidence,
    ReleaseEnvelope,
    ReleaseInput,
    release_manifest,
)
from brp.ir.canonical import canonical_bytes
from brp.ir.models import DecisionContent

ROOT = Path(__file__).resolve().parents[3]


def release() -> ReleaseInput:
    content = DecisionContent.model_validate_json(
        (ROOT / "platform/tests/fixtures/conformance/enrollment_eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    content_hash = hashlib.sha256(canonical_bytes(content)).hexdigest()
    target = load_site_profile(ROOT / "config/sites/fixture.yaml").target
    assert target is not None
    return ReleaseInput(
        content=content,
        envelope=ReleaseEnvelope(
            decision_key="enrollment_eligibility",
            revision=1,
            content_hash=content_hash,
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        ),
        golden_suite=GoldenReleaseEvidence(
            revision=1,
            content_hash="b" * 64,
            cases=[{"caseKey": "under-age", "input": {"age": 17}, "expected": {"eligible": False}}],
        ),
        site="fixture",
        target=target,
        site_config_hash="c" * 64,
        generator="java-source",
        generator_version="1.0.0",
    )


def test_release_input_and_manifest_are_byte_deterministic() -> None:
    first = release()
    second = release()
    assert first.canonical_bytes() == second.canonical_bytes()
    artifacts = [GeneratedArtifact.create("B.java", "B"), GeneratedArtifact.create("A.java", "A")]
    manifest = release_manifest(first, artifacts)
    assert [item["path"] for item in manifest["outputs"]] == ["A.java", "B.java"]
    assert json.dumps(manifest, sort_keys=True, ensure_ascii=False)


def test_release_rejects_mismatched_content_hash() -> None:
    document = release().model_dump(mode="json", by_alias=True)
    document["envelope"]["contentHash"] = "0" * 64
    with pytest.raises(ValidationError, match="does not match"):
        ReleaseInput.model_validate(document)
