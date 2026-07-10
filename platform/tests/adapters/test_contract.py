import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from brp.adapters.contracts import (
    SOURCE_ADAPTER_CAPABILITY,
    CandidateDecision,
    ExtractionBatch,
    Source,
    SourceSnapshot,
)
from brp.adapters.registry import AdapterRegistry
from brp.ir.models import DecisionContent

FIXTURE = Path(__file__).parents[1] / "fixtures/conformance/enrollment_eligibility.json"


class FixtureAdapter:
    name = "fixture"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [Source(source_id="fixture:one", kind="fixture")]

    def extract(self, source: Source) -> ExtractionBatch:
        content = DecisionContent.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
        return ExtractionBatch(
            adapter=self.name,
            decisions=[CandidateDecision(decision_key="enrollment_eligibility", content=content)],
            source_snapshot=SourceSnapshot(
                source_id=source.source_id,
                revision="fixture-v1",
                content_hash="a" * 64,
                captured_at=datetime.now(UTC),
            ),
        )


def test_registry_resolves_capability_versioned_adapter() -> None:
    registry = AdapterRegistry()
    registry.register(FixtureAdapter())
    assert registry.names == ("fixture",)
    assert registry.get("fixture").extract(Source(source_id="x", kind="fixture")).decisions


def test_registry_rejects_duplicate_and_unknown_capability() -> None:
    registry = AdapterRegistry()
    registry.register(FixtureAdapter())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FixtureAdapter())
    adapter = FixtureAdapter()
    adapter.capability_version = "source-adapter/v2"
    with pytest.raises(ValueError, match="unsupported capability"):
        AdapterRegistry().register(adapter)


def test_batch_is_strict_and_requires_a_result() -> None:
    snapshot = SourceSnapshot(
        source_id="x", revision="1", content_hash="0" * 64, captured_at=datetime.now(UTC)
    )
    with pytest.raises(ValidationError, match="at least one result"):
        ExtractionBatch(adapter="fixture", source_snapshot=snapshot)
    with pytest.raises(ValidationError):
        Source.model_validate(json.loads('{"sourceId":"x","kind":"fixture","secret":"no"}'))
