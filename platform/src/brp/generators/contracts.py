"""ADR-8 release inputs and target generator capability boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, model_validator

from brp.config.models import TargetConfig
from brp.ir.canonical import canonical_bytes
from brp.ir.models import DecisionContent, StrictModel


class ReleaseEnvelope(StrictModel):
    decision_key: str
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    effective_from: datetime
    effective_to: datetime | None = None


class GoldenReleaseEvidence(StrictModel):
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    cases: list[dict[str, Any]] = Field(min_length=1)


class LookupReleaseSnapshot(StrictModel):
    snapshot_id: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    name: str
    rows: list[dict[str, Any]]


class ReleaseInput(StrictModel):
    content: DecisionContent
    envelope: ReleaseEnvelope
    golden_suite: GoldenReleaseEvidence
    lookup_snapshots: list[LookupReleaseSnapshot] = Field(default_factory=list)
    site: str
    target: TargetConfig
    site_config_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    generator: str
    generator_version: str

    @model_validator(mode="after")
    def content_hash_matches(self) -> ReleaseInput:
        actual = hashlib.sha256(canonical_bytes(self.content)).hexdigest()
        if actual != self.envelope.content_hash:
            raise ValueError("release envelope content hash does not match canonical content")
        hashes = [snapshot.content_hash for snapshot in self.lookup_snapshots]
        if len(hashes) != len(set(hashes)):
            raise ValueError("lookup snapshots must be unique")
        return self

    def canonical_bytes(self) -> bytes:
        document = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def release_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class GeneratedArtifact(StrictModel):
    path: str
    content: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def create(cls, path: str, content: str) -> GeneratedArtifact:
        return cls(
            path=path,
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )


@runtime_checkable
class TargetGenerator(Protocol):
    name: str
    version: str

    def supports(self, profile: str, target: TargetConfig) -> bool: ...

    def generate(self, release_input: ReleaseInput) -> list[GeneratedArtifact]: ...


def release_manifest(
    release_input: ReleaseInput, artifacts: list[GeneratedArtifact]
) -> dict[str, Any]:
    return {
        "releaseHash": release_input.release_hash,
        "decision": {
            "key": release_input.envelope.decision_key,
            "revision": release_input.envelope.revision,
            "contentHash": release_input.envelope.content_hash,
        },
        "goldenSuite": {
            "revision": release_input.golden_suite.revision,
            "contentHash": release_input.golden_suite.content_hash,
        },
        "lookupSnapshots": [
            {"id": item.snapshot_id, "hash": item.content_hash}
            for item in release_input.lookup_snapshots
        ],
        "siteConfigHash": release_input.site_config_hash,
        "generator": {
            "name": release_input.generator,
            "version": release_input.generator_version,
        },
        "outputs": [
            {"path": artifact.path, "hash": artifact.content_hash}
            for artifact in sorted(artifacts, key=lambda item: item.path)
        ],
    }
