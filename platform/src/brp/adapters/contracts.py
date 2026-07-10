"""Capability-versioned contracts shared by all source adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, model_validator

from brp.ir.models import DecisionContent, StrictModel

SOURCE_ADAPTER_CAPABILITY = "source-adapter/v1"


class Source(StrictModel):
    """A bounded, secret-free unit an adapter can extract."""

    source_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    locator: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(StrictModel):
    source_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime


class CandidateDecision(StrictModel):
    decision_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    content: DecisionContent


class AdapterDiagnostic(StrictModel):
    level: str = Field(pattern=r"^(INFO|WARNING|ERROR)$")
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class UnmappableItem(StrictModel):
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    raw_fragment: str = Field(min_length=1)
    provenance: dict[str, Any] = Field(min_length=1)


class ExtractionBatch(StrictModel):
    adapter: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    capability_version: str = SOURCE_ADAPTER_CAPABILITY
    decisions: list[CandidateDecision] = Field(default_factory=list)
    unmappable: list[UnmappableItem] = Field(default_factory=list)
    diagnostics: list[AdapterDiagnostic] = Field(default_factory=list)
    source_snapshot: SourceSnapshot

    @model_validator(mode="after")
    def has_result(self) -> ExtractionBatch:
        if not self.decisions and not self.unmappable and not self.diagnostics:
            raise ValueError("an extraction batch must report at least one result")
        return self


@runtime_checkable
class SourceAdapter(Protocol):
    """Minimal plug-in boundary; adapters remain site-agnostic."""

    name: str
    capability_version: str

    def discover(self, site_config: object) -> list[Source]: ...

    def extract(self, source: Source) -> ExtractionBatch: ...
