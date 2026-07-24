"""Validated runtime configuration for self-hosted deployments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from pydantic import Field, field_validator, model_validator

from brp.ir.models import StrictModel


class RuntimeSettings(StrictModel):
    environment: str = "development"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    trusted_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=100)
    database_pool_timeout_seconds: int = Field(default=10, ge=1, le=120)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    database_statement_timeout_ms: int = Field(default=30_000, ge=1_000, le=600_000)
    artifact_root: Path = Path("output/artifacts")
    artifact_backend: Literal["local", "s3"] = "local"
    artifact_bucket: str | None = None
    artifact_prefix: str = "brp"
    repository_root: Path = Path(".")
    worker_stale_seconds: int = Field(default=180, ge=30, le=3600)
    require_worker_heartbeat: bool = False

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "staging", "production"}:
            raise ValueError("environment must be development, test, staging, or production")
        return normalized

    @model_validator(mode="after")
    def s3_requires_bucket(self) -> RuntimeSettings:
        if self.artifact_backend == "s3" and not self.artifact_bucket:
            raise ValueError("BRP_ARTIFACT_BUCKET is required for S3 artifact storage")
        return self

    @classmethod
    def from_environment(cls) -> RuntimeSettings:
        def csv(name: str, fallback: str) -> tuple[str, ...]:
            return tuple(
                item.strip() for item in os.getenv(name, fallback).split(",") if item.strip()
            )

        return cls(
            environment=os.getenv("BRP_ENVIRONMENT", "development"),
            cors_origins=csv("BRP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
            trusted_hosts=csv("BRP_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver"),
            database_pool_size=int(os.getenv("BRP_DATABASE_POOL_SIZE", "5")),
            database_max_overflow=int(os.getenv("BRP_DATABASE_MAX_OVERFLOW", "5")),
            database_pool_timeout_seconds=int(os.getenv("BRP_DATABASE_POOL_TIMEOUT_SECONDS", "10")),
            database_connect_timeout_seconds=int(
                os.getenv("BRP_DATABASE_CONNECT_TIMEOUT_SECONDS", "5")
            ),
            database_statement_timeout_ms=int(
                os.getenv("BRP_DATABASE_STATEMENT_TIMEOUT_MS", "30000")
            ),
            artifact_root=Path(os.getenv("BRP_ARTIFACT_ROOT", "output/artifacts")),
            artifact_backend=cast(
                Literal["local", "s3"], os.getenv("BRP_ARTIFACT_BACKEND", "local")
            ),
            artifact_bucket=os.getenv("BRP_ARTIFACT_BUCKET") or None,
            artifact_prefix=os.getenv("BRP_ARTIFACT_PREFIX", "brp"),
            repository_root=Path(os.getenv("BRP_REPOSITORY_ROOT", ".")),
            worker_stale_seconds=int(os.getenv("BRP_WORKER_STALE_SECONDS", "180")),
            require_worker_heartbeat=os.getenv("BRP_REQUIRE_WORKER_HEARTBEAT", "false").lower()
            == "true",
        )
