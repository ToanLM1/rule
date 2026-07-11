"""Strict, secret-free site profile contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from brp.ir.models import ProgramKind, to_camel

ENV_PATTERN = r"^[A-Z][A-Z0-9_]*$"
ADAPTER_PATTERN = r"^[a-z][a-z0-9-]*$"
ALIAS_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"
JAVA_NAME_PATTERN = r"^[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*$"


class ConfigModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class DeliveryMode(StrEnum):
    A = "A"
    B = "B"


class Language(StrEnum):
    JAVA = "java"
    CSHARP = "csharp"


class DatabaseKind(StrEnum):
    POSTGRES = "postgres"


class Aggregate(StrEnum):
    SUM = "SUM"
    DISTINCT = "DISTINCT"
    FIRST_NON_NULL = "FIRST_NON_NULL"


def _safe_relative_path(value: str) -> str:
    path = Path(value)
    is_absolute = PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    has_parent = ".." in PurePosixPath(value.replace("\\", "/")).parts
    if is_absolute or path.is_absolute() or has_parent:
        raise ValueError("path must be repository-relative and cannot traverse parents")
    if not value or value in {".", "./"}:
        raise ValueError("path must identify a repository child")
    return value.replace("\\", "/")


class DatabaseSource(ConfigModel):
    kind: DatabaseKind
    connection_env: str = Field(pattern=ENV_PATTERN)


class RepositorySource(ConfigModel):
    alias: str = Field(pattern=ALIAS_PATTERN)
    path: str
    revision: str = Field(min_length=1)

    _validate_path = field_validator("path")(_safe_relative_path)


class ProgramContextConfig(ConfigModel):
    program_id: str = Field(min_length=1)
    kind: ProgramKind
    repository: str = Field(pattern=ALIAS_PATTERN)
    class_name: str = Field(alias="class", pattern=JAVA_NAME_PATTERN)
    method: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")


class SourceConfig(ConfigModel):
    db: DatabaseSource
    repositories: list[RepositorySource] = Field(min_length=1)
    program_contexts: list[ProgramContextConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def references_known_repositories(self) -> SourceConfig:
        aliases = [repository.alias for repository in self.repositories]
        if len(aliases) != len(set(aliases)):
            raise ValueError("repository aliases must be unique")
        unknown = {
            context.repository
            for context in self.program_contexts
            if context.repository not in aliases
        }
        if unknown:
            raise ValueError(f"program contexts reference unknown repositories: {sorted(unknown)}")
        return self


class CompositionDecision(ConfigModel):
    field: str = Field(pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    aggregate: Aggregate


class CompositionConfig(ConfigModel):
    facade: str = Field(pattern=JAVA_NAME_PATTERN)
    decisions: dict[str, CompositionDecision] = Field(min_length=1)

    @field_validator("decisions")
    @classmethod
    def valid_decision_keys(
        cls, value: dict[str, CompositionDecision]
    ) -> dict[str, CompositionDecision]:
        invalid = [key for key in value if not re.fullmatch(r"[a-z][a-z0-9_]*", key)]
        if invalid:
            raise ValueError(f"invalid composition decision keys: {invalid}")
        return value


class TargetConfig(ConfigModel):
    language: Language = Language.JAVA
    repository: str
    base_branch: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    generated_source_path: str
    generated_test_path: str
    java_package: str | None = Field(default=None, pattern=JAVA_NAME_PATTERN)
    csharp_namespace: str | None = Field(default=None, pattern=JAVA_NAME_PATTERN)
    build_command: str = Field(min_length=1)
    pr_provider: str = Field(pattern=ADAPTER_PATTERN)
    composition: CompositionConfig

    @field_validator("repository", "generated_source_path", "generated_test_path")
    @classmethod
    def safe_paths(cls, value: str) -> str:
        return _safe_relative_path(value)

    @field_validator("build_command")
    @classmethod
    def single_line_command(cls, value: str) -> str:
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("build command must be a single line")
        return value

    @model_validator(mode="after")
    def language_namespace(self) -> TargetConfig:
        if self.language is Language.JAVA and self.java_package is None:
            raise ValueError("Java target requires javaPackage")
        if self.language is Language.CSHARP and self.csharp_namespace is None:
            raise ValueError("C# target requires csharpNamespace")
        return self


class SiteProfile(ConfigModel):
    site: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    delivery_mode: DeliveryMode
    language: Language
    source: SourceConfig
    adapters: list[str] = Field(min_length=1)
    mapping_spec: str
    target: TargetConfig | None = None

    _validate_mapping_path = field_validator("mapping_spec")(_safe_relative_path)

    @field_validator("adapters")
    @classmethod
    def valid_adapters(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("adapters must be unique")
        invalid = [adapter for adapter in value if not re.fullmatch(ADAPTER_PATTERN, adapter)]
        if invalid:
            raise ValueError(f"invalid adapter names: {invalid}")
        return value

    @model_validator(mode="after")
    def mode_requires_target(self) -> SiteProfile:
        if self.delivery_mode is DeliveryMode.B and self.target is None:
            raise ValueError("Mode B requires target delivery configuration")
        if self.target is not None and self.target.language is not self.language:
            raise ValueError("site and target languages must match")
        return self


def load_site_profile(path: Path) -> SiteProfile:
    """Load YAML without environment expansion; config stores env names only."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("site profile must be a YAML object")
    return SiteProfile.model_validate(document)
