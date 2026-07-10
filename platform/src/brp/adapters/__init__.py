"""Source-adapter contracts and registry."""

from brp.adapters.contracts import (
    AdapterDiagnostic,
    CandidateDecision,
    ExtractionBatch,
    Source,
    SourceSnapshot,
    UnmappableItem,
)
from brp.adapters.registry import AdapterRegistry

__all__ = [
    "AdapterDiagnostic",
    "AdapterRegistry",
    "CandidateDecision",
    "ExtractionBatch",
    "Source",
    "SourceSnapshot",
    "UnmappableItem",
]
