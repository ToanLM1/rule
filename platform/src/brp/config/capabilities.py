"""Deterministic multi-site source/target capability preflight."""

from __future__ import annotations

import hashlib
import json
import shutil
from enum import StrEnum

from pydantic import Field

from brp.config.models import (
    DatabaseKind,
    DeliveryMode,
    Language,
    SiteProfile,
)
from brp.ir.models import StrictModel


class CapabilityKind(StrEnum):
    SOURCE = "SOURCE"
    TARGET = "TARGET"
    RUNTIME = "RUNTIME"


class CapabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class ToolchainInventory(StrictModel):
    java: bool = False
    dotnet: bool = False
    joern: bool = False
    zen: bool = True
    postgres: bool = False
    sqlite: bool = True

    @classmethod
    def detect(
        cls,
        *,
        postgres: bool = False,
        sqlite: bool = True,
        zen: bool = True,
    ) -> ToolchainInventory:
        return cls(
            java=shutil.which("java") is not None,
            dotnet=shutil.which("dotnet") is not None,
            joern=shutil.which("joern") is not None,
            zen=zen,
            postgres=postgres,
            sqlite=sqlite,
        )


class CapabilityDeclaration(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    kind: CapabilityKind
    languages: list[Language] = Field(default_factory=list)
    databases: list[DatabaseKind] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)


class CapabilityResult(StrictModel):
    name: str
    kind: CapabilityKind
    status: CapabilityStatus
    reasons: list[str] = Field(default_factory=list)


class SiteCapabilityReport(StrictModel):
    site: str
    delivery_mode: DeliveryMode
    language: Language
    database: DatabaseKind
    ready: bool
    capabilities: list[CapabilityResult]

    @property
    def report_hash(self) -> str:
        return _hash(self.model_dump(mode="json", by_alias=True))


class CapabilityMatrix(StrictModel):
    schema_version: int = 1
    reports: list[SiteCapabilityReport]
    matrix_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CapabilityCatalog:
    def __init__(self) -> None:
        self._declarations: dict[tuple[CapabilityKind, str], CapabilityDeclaration] = {}

    def register(self, declaration: CapabilityDeclaration) -> None:
        key = declaration.kind, declaration.name
        if key in self._declarations:
            raise ValueError(
                f"capability already registered: {declaration.kind}/{declaration.name}"
            )
        self._declarations[key] = declaration

    def get(self, kind: CapabilityKind, name: str) -> CapabilityDeclaration | None:
        return self._declarations.get((kind, name))

    @property
    def declarations(self) -> tuple[CapabilityDeclaration, ...]:
        return tuple(
            self._declarations[key]
            for key in sorted(self._declarations, key=lambda item: (item[0].value, item[1]))
        )

    @classmethod
    def builtin(cls) -> CapabilityCatalog:
        catalog = cls()
        for declaration in _BUILTINS:
            catalog.register(declaration)
        return catalog


def evaluate_site(
    profile: SiteProfile,
    inventory: ToolchainInventory,
    *,
    catalog: CapabilityCatalog | None = None,
) -> SiteCapabilityReport:
    selected_catalog = catalog or CapabilityCatalog.builtin()
    results = [
        _evaluate(
            selected_catalog.get(CapabilityKind.SOURCE, name),
            name,
            CapabilityKind.SOURCE,
            profile,
            inventory,
        )
        for name in sorted(profile.adapters)
    ]
    results.extend(
        _evaluate(
            selected_catalog.get(CapabilityKind.TARGET, name),
            name,
            CapabilityKind.TARGET,
            profile,
            inventory,
        )
        for name in profile.selected_generators
    )
    if profile.delivery_mode is DeliveryMode.A:
        declaration = selected_catalog.get(CapabilityKind.RUNTIME, "mode-a-zen")
        results.append(
            _evaluate(
                declaration,
                "mode-a-zen",
                CapabilityKind.RUNTIME,
                profile,
                inventory,
            )
        )
    results.sort(key=lambda item: (item.kind.value, item.name))
    return SiteCapabilityReport(
        site=profile.site,
        delivery_mode=profile.delivery_mode,
        language=profile.language,
        database=profile.source.db.kind,
        ready=all(item.status is CapabilityStatus.AVAILABLE for item in results),
        capabilities=results,
    )


def build_matrix(
    profiles: list[SiteProfile],
    inventory: ToolchainInventory,
    *,
    catalog: CapabilityCatalog | None = None,
) -> CapabilityMatrix:
    sites = [profile.site for profile in profiles]
    if len(sites) != len(set(sites)):
        raise ValueError("site names must be unique in a capability matrix")
    reports = [
        evaluate_site(profile, inventory, catalog=catalog)
        for profile in sorted(profiles, key=lambda item: item.site)
    ]
    document = [item.model_dump(mode="json", by_alias=True) for item in reports]
    return CapabilityMatrix(reports=reports, matrix_hash=_hash(document))


def _evaluate(
    declaration: CapabilityDeclaration | None,
    name: str,
    kind: CapabilityKind,
    profile: SiteProfile,
    inventory: ToolchainInventory,
) -> CapabilityResult:
    if declaration is None:
        return CapabilityResult(
            name=name,
            kind=kind,
            status=CapabilityStatus.UNKNOWN,
            reasons=["capability is not registered"],
        )
    incompatible: list[str] = []
    if declaration.languages and profile.language not in declaration.languages:
        incompatible.append(f"language {profile.language.value} is not supported")
    if declaration.databases and profile.source.db.kind not in declaration.databases:
        incompatible.append(f"database {profile.source.db.kind.value} is not supported")
    if incompatible:
        return CapabilityResult(
            name=name,
            kind=kind,
            status=CapabilityStatus.INCOMPATIBLE,
            reasons=incompatible,
        )
    missing = [tool for tool in declaration.required_tools if not _tool(tool, inventory)]
    if missing:
        return CapabilityResult(
            name=name,
            kind=kind,
            status=CapabilityStatus.UNAVAILABLE,
            reasons=[f"required tool unavailable: {tool}" for tool in missing],
        )
    return CapabilityResult(
        name=name,
        kind=kind,
        status=CapabilityStatus.AVAILABLE,
    )


def _tool(name: str, inventory: ToolchainInventory) -> bool:
    mapping = {
        "java": inventory.java,
        "dotnet": inventory.dotnet,
        "joern": inventory.joern,
        "zen": inventory.zen,
        "postgres": inventory.postgres,
        "sqlite": inventory.sqlite,
    }
    return mapping.get(name, False)


def _hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


_BUILTINS = [
    CapabilityDeclaration(
        name="db-postgres",
        kind=CapabilityKind.SOURCE,
        databases=[DatabaseKind.POSTGRES],
        required_tools=["postgres"],
    ),
    CapabilityDeclaration(
        name="db-postgres-stored-object",
        kind=CapabilityKind.SOURCE,
        databases=[DatabaseKind.POSTGRES],
        required_tools=["postgres"],
    ),
    CapabilityDeclaration(
        name="db-sqlite",
        kind=CapabilityKind.SOURCE,
        databases=[DatabaseKind.SQLITE],
        required_tools=["sqlite"],
    ),
    CapabilityDeclaration(
        name="code-java",
        kind=CapabilityKind.SOURCE,
        languages=[Language.JAVA],
        required_tools=["joern"],
    ),
    CapabilityDeclaration(name="docs-manual", kind=CapabilityKind.SOURCE),
    CapabilityDeclaration(name="engine-dmn", kind=CapabilityKind.SOURCE),
    CapabilityDeclaration(name="engine-native", kind=CapabilityKind.SOURCE),
    CapabilityDeclaration(name="ui-html-validation", kind=CapabilityKind.SOURCE),
    CapabilityDeclaration(
        name="java-source",
        kind=CapabilityKind.TARGET,
        languages=[Language.JAVA],
        required_tools=["java"],
    ),
    CapabilityDeclaration(
        name="csharp-source",
        kind=CapabilityKind.TARGET,
        languages=[Language.CSHARP],
        required_tools=["dotnet"],
    ),
    CapabilityDeclaration(name="jdm-export", kind=CapabilityKind.TARGET),
    CapabilityDeclaration(name="dmn-export", kind=CapabilityKind.TARGET),
    CapabilityDeclaration(
        name="mode-a-zen",
        kind=CapabilityKind.RUNTIME,
        required_tools=["zen"],
    ),
]
