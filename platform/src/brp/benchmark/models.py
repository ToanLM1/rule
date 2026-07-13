"""Strict, versioned benchmark and provider-policy documents."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from brp.ir.models import StrictModel


class DataClassification(StrEnum):
    SYNTHETIC_NON_CUSTOMER = "SYNTHETIC_NON_CUSTOMER"
    REAL_CUSTOMER = "REAL_CUSTOMER"


class GroundTruthConstruct(StrictModel):
    construct_id: str = Field(min_length=1, max_length=200)
    rule_ids: list[str] = Field(min_length=1)
    source_locations: list[str] = Field(min_length=1)


class GroundTruthSlice(StrictModel):
    slice_id: str = Field(min_length=1, max_length=200)
    source_revision: str = Field(min_length=1)
    constructs: list[GroundTruthConstruct]

    @model_validator(mode="after")
    def unique_constructs(self) -> GroundTruthSlice:
        identifiers = [item.construct_id for item in self.constructs]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("construct IDs must be unique within a slice")
        return self


class CustomerApproval(StrictModel):
    approval_reference: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: datetime
    scope_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_providers: list[str] = Field(min_length=1)


class BenchmarkManifest(StrictModel):
    schema_version: Literal[1]
    benchmark_id: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1)
    classification: DataClassification
    slices: list[GroundTruthSlice] = Field(min_length=1)
    approval: CustomerApproval | None = None

    @model_validator(mode="after")
    def unique_slices(self) -> BenchmarkManifest:
        identifiers = [item.slice_id for item in self.slices]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("slice IDs must be unique")
        return self


class ProviderRule(StrictModel):
    provider: str = Field(min_length=1)
    models: list[str] = Field(min_length=1)
    classifications: list[DataClassification] = Field(min_length=1)


class ProviderPolicy(StrictModel):
    schema_version: Literal[1]
    policy_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    rules: list[ProviderRule]

    def allows(self, provider: str, model: str, classification: DataClassification) -> bool:
        return any(
            rule.provider == provider
            and model in rule.models
            and classification in rule.classifications
            for rule in self.rules
        )


class MiningPrediction(StrictModel):
    slice_id: str = Field(min_length=1)
    construct_ids: list[str]
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def unique_predictions(self) -> MiningPrediction:
        if len(self.construct_ids) != len(set(self.construct_ids)):
            raise ValueError("predicted construct IDs must be unique")
        return self
