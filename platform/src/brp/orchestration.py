"""Safe, non-persistent local workbench orchestration for Phase-3 capabilities."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from brp.adapters.contracts import ExtractionBatch
from brp.adapters.db_stored_object import PostgresStoredObjectAdapter
from brp.adapters.dmn import DmnDecisionTableAdapter
from brp.adapters.engine_native import EngineNativeAdapter
from brp.adapters.ui_validation import HtmlValidationAdapter
from brp.config.capabilities import (
    CapabilityCatalog,
    CapabilityMatrix,
    ToolchainInventory,
    build_matrix,
)
from brp.config.models import SiteProfile
from brp.generators.csharp import render_csharp_preview, verify_csharp_compile
from brp.generators.dmn_export import export_dmn
from brp.ir.models import DecisionContent

EVIDENCE_LABEL = "LOCAL_PREVIEW_NON_AUTHORITATIVE"
SUPPORTED_ADAPTERS = frozenset(
    {
        "db-postgres-stored-object",
        "ui-html-validation",
        "engine-native",
        "engine-dmn",
    }
)
SUPPORTED_GENERATORS = frozenset({"dmn-export", "csharp-source"})


class OrchestrationError(ValueError):
    pass


class _InlineStoredReader:
    def __init__(self, source: str, schema: str, object_name: str) -> None:
        self.source = source
        self.schema = schema
        self.object_name = object_name

    def stored_procedure_source(self, schema: str, procedure: str) -> str:
        if (schema, procedure) != (self.schema, self.object_name):
            raise OrchestrationError("stored object is outside the inline allowlist")
        return self.source


def catalog() -> dict[str, object]:
    declarations = CapabilityCatalog.builtin().declarations
    inventory = ToolchainInventory.detect(postgres=True, sqlite=True, zen=True)
    return {
        "evidenceLabel": EVIDENCE_LABEL,
        "persistent": False,
        "adapters": sorted(SUPPORTED_ADAPTERS),
        "generators": sorted(SUPPORTED_GENERATORS),
        "capabilities": [item.model_dump(mode="json", by_alias=True) for item in declarations],
        "hostInventory": inventory.model_dump(mode="json", by_alias=True),
        "boundaries": [
            "Inputs are parsed in memory or an isolated temporary directory",
            "Scripts, SQL statements, and engine consequences are never executed",
            "Candidates and generated previews are not persisted or approved",
            "Release generation still requires governed repository workflows",
        ],
    }


def preflight(profiles: list[SiteProfile], inventory: ToolchainInventory) -> CapabilityMatrix:
    return build_matrix(profiles, inventory)


def extract_inline(
    *,
    adapter: str,
    content: str,
    filename: str,
    revision: str,
    connection_alias: str,
    schema_name: str,
    object_name: str,
) -> ExtractionBatch:
    if adapter not in SUPPORTED_ADAPTERS:
        raise OrchestrationError(f"adapter is not exposed by the local workbench: {adapter}")
    _safe_filename(filename)
    if adapter == "db-postgres-stored-object":
        reader = _InlineStoredReader(content, schema_name, object_name)
        stored_adapter = PostgresStoredObjectAdapter(
            reader,
            connection_alias=connection_alias,
            objects=[(schema_name, object_name)],
        )
        return stored_adapter.extract(stored_adapter.discover(None)[0])
    with tempfile.TemporaryDirectory(prefix="brp-orchestration-") as directory:
        path = Path(directory) / filename
        path.write_text(content, encoding="utf-8", newline="\n")
        source_adapter: HtmlValidationAdapter | EngineNativeAdapter | DmnDecisionTableAdapter
        if adapter == "ui-html-validation":
            source_adapter = HtmlValidationAdapter([path], asset_revision=revision)
        elif adapter == "engine-native":
            source_adapter = EngineNativeAdapter([path], asset_revision=revision)
        else:
            source_adapter = DmnDecisionTableAdapter([path], revision=revision)
        discovered = source_adapter.discover(None)
        if not discovered:
            raise OrchestrationError("filename extension is incompatible with the adapter")
        return source_adapter.extract(discovered[0])


def generate_preview(
    *, generator: str, content: DecisionContent, csharp_namespace: str
) -> dict[str, object]:
    if generator == "dmn-export":
        dmn_artifact = export_dmn(content)
        return {
            "generator": generator,
            "evidenceLabel": EVIDENCE_LABEL,
            "persistent": False,
            "authoritative": False,
            "path": f"preview/{content.decision_id}.dmn",
            "content": dmn_artifact.content.decode("utf-8"),
            "contentHash": dmn_artifact.content_hash,
            "decisionContentHash": dmn_artifact.decision_content_hash,
        }
    if generator == "csharp-source":
        csharp_artifact = render_csharp_preview(content, csharp_namespace)
        compile_evidence = verify_csharp_compile(csharp_artifact)
        return {
            "generator": generator,
            "evidenceLabel": EVIDENCE_LABEL,
            "persistent": False,
            "authoritative": False,
            "path": csharp_artifact.path,
            "content": csharp_artifact.content,
            "contentHash": csharp_artifact.content_hash,
            "compileEvidence": compile_evidence.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
        }
    raise OrchestrationError(f"generator is not exposed by the local workbench: {generator}")


def _safe_filename(value: str) -> None:
    if (
        not value
        or Path(value).name != value
        or value in {".", ".."}
        or re.search(r"[\\/\x00]", value)
    ):
        raise OrchestrationError("filename must be a safe basename")
