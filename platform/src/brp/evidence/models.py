"""Immutable structured evidence returned by repository bootstrap analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from brp.ir.models import IDENTIFIER_PATTERN, StrictModel


class RepositoryIdentity(StrictModel):
    repository_url: str = Field(min_length=1)
    commit: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    subpath: str = "."
    entry_point_hypothesis: str | None = None


class EvidenceSpan(StrictModel):
    span_id: str = Field(pattern=IDENTIFIER_PATTERN)
    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    snippet: str = Field(min_length=1, max_length=50_000)
    symbol: str | None = None

    @model_validator(mode="after")
    def ordered_lines(self) -> EvidenceSpan:
        if self.line_end < self.line_start:
            raise ValueError("lineEnd must not precede lineStart")
        return self


class FieldEvidence(StrictModel):
    field_path: str = Field(min_length=1)
    span_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1)


class TestEvidence(StrictModel):
    file: str = Field(min_length=1)
    command: list[str] = Field(default_factory=list)
    status: Literal["DISCOVERED", "PASSED", "FAILED", "NOT_RUN"]
    summary: str = Field(min_length=1)


class ToolTranscriptEntry(StrictModel):
    sequence: int = Field(ge=1)
    tool: Literal["inventory", "search", "read", "git_history", "syntax", "semantic"]
    request: dict[str, object]
    result_summary: str = Field(min_length=1)
    truncated: bool = False


class EscalationRecommendation(StrictModel):
    tier: Literal["NONE", "SYNTAX", "SEMANTIC", "HEAVY", "HUMAN"]
    question: str | None = None
    reason: str = Field(min_length=1)


class EvidenceBundle(StrictModel):
    bundle_id: str = Field(pattern=IDENTIFIER_PATTERN)
    repository: RepositoryIdentity
    hypothesis: str = Field(min_length=1)
    spans: list[EvidenceSpan] = Field(default_factory=list)
    field_evidence: list[FieldEvidence] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_calls: list[str] = Field(default_factory=list)
    alternative_interpretations: list[str] = Field(default_factory=list)
    test_evidence: list[TestEvidence] = Field(default_factory=list)
    transcript: list[ToolTranscriptEntry] = Field(default_factory=list)
    escalation: EscalationRecommendation

    @model_validator(mode="after")
    def references_existing_spans(self) -> EvidenceBundle:
        span_ids = {span.span_id for span in self.spans}
        unknown = {
            span_id
            for field in self.field_evidence
            for span_id in field.span_ids
            if span_id not in span_ids
        }
        if unknown:
            raise ValueError(f"field evidence references unknown spans: {sorted(unknown)}")
        sequences = [entry.sequence for entry in self.transcript]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("transcript sequence must be contiguous and start at 1")
        return self
