"""Content-addressed artifact storage with local and S3-compatible backends."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from brp.settings import RuntimeSettings


class ArtifactStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    content_hash: str
    size_bytes: int


class ArtifactStore(Protocol):
    def put(self, key: str, content: bytes) -> StoredArtifact: ...

    def get(self, key: str) -> bytes: ...


class S3Body(Protocol):
    def read(self) -> bytes: ...


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> object: ...

    def get_object(self, **kwargs: object) -> dict[str, Any]: ...


def safe_storage_key(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    if (
        not normalized
        or ".." in normalized.split("/")
        or not re.fullmatch(r"[A-Za-z0-9._/-]+", normalized)
    ):
        raise ArtifactStorageError("artifact storage key is unsafe")
    return normalized


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes) -> StoredArtifact:
        safe = safe_storage_key(key)
        destination = (self.root / safe).resolve()
        if self.root not in destination.parents:
            raise ArtifactStorageError("artifact path escapes storage root")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
        return StoredArtifact(safe, hashlib.sha256(content).hexdigest(), len(content))

    def get(self, key: str) -> bytes:
        safe = safe_storage_key(key)
        path = (self.root / safe).resolve()
        if self.root not in path.parents or not path.is_file():
            raise ArtifactStorageError("artifact does not exist")
        return path.read_bytes()


class S3ArtifactStore:
    def __init__(self, *, bucket: str, prefix: str = "brp", client: S3Client | None = None) -> None:
        if not bucket.strip():
            raise ValueError("artifact bucket is required")
        if client is None:
            try:
                import boto3  # type: ignore[import-untyped]
            except ImportError as exc:  # pragma: no cover - deployment dependency guard
                raise ArtifactStorageError("boto3 is required for S3 artifact storage") from exc
            client = cast(S3Client, boto3.client("s3"))
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, key: str) -> str:
        safe = safe_storage_key(key)
        return f"{self.prefix}/{safe}" if self.prefix else safe

    def put(self, key: str, content: bytes) -> StoredArtifact:
        digest = hashlib.sha256(content).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=content,
            Metadata={"sha256": digest},
        )
        return StoredArtifact(safe_storage_key(key), digest, len(content))

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        return cast(S3Body, response["Body"]).read()


def artifact_store(settings: RuntimeSettings | None = None) -> ArtifactStore:
    runtime = settings or RuntimeSettings.from_environment()
    if runtime.artifact_backend == "local":
        return LocalArtifactStore(runtime.artifact_root)
    assert runtime.artifact_bucket is not None
    return S3ArtifactStore(bucket=runtime.artifact_bucket, prefix=runtime.artifact_prefix)
