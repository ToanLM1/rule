import json
from pathlib import Path

import yaml

from brp.config.capabilities import (
    CapabilityStatus,
    ToolchainInventory,
    build_matrix,
    evaluate_site,
)
from brp.config.models import SiteProfile

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "config/sites/fixture.yaml"


def base_document() -> dict[str, object]:
    document = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def java_profile() -> SiteProfile:
    document = base_document()
    document["site"] = "java-site"
    document["generators"] = ["java-source", "dmn-export"]
    return SiteProfile.model_validate(document)


def mode_a_dmn_profile() -> SiteProfile:
    document = base_document()
    document["site"] = "dmn-site"
    document["delivery_mode"] = "A"
    document["adapters"] = ["engine-dmn"]
    document["generators"] = ["jdm-export", "dmn-export"]
    document.pop("target")
    return SiteProfile.model_validate(document)


def csharp_profile() -> SiteProfile:
    document = base_document()
    document["site"] = "csharp-site"
    document["language"] = "csharp"
    document["adapters"] = ["docs-manual", "ui-html-validation"]
    document["generators"] = ["csharp-source", "dmn-export"]
    target = document["target"]
    assert isinstance(target, dict)
    target["language"] = "csharp"
    target.pop("java_package")
    target["csharp_namespace"] = "Customer.Generated.Rules"
    target["build_command"] = "dotnet test"
    return SiteProfile.model_validate(document)


def inventory(*, dotnet: bool = True) -> ToolchainInventory:
    return ToolchainInventory(
        java=True,
        dotnet=dotnet,
        joern=True,
        zen=True,
        postgres=True,
        sqlite=True,
    )


def test_compatible_java_dmn_and_csharp_paths_are_ready() -> None:
    for profile in [java_profile(), mode_a_dmn_profile(), csharp_profile()]:
        report = evaluate_site(profile, inventory())
        assert report.ready, report.model_dump(mode="json")
        assert all(item.status is CapabilityStatus.AVAILABLE for item in report.capabilities)
    dmn = evaluate_site(mode_a_dmn_profile(), inventory())
    assert {item.name for item in dmn.capabilities} >= {
        "engine-dmn",
        "jdm-export",
        "dmn-export",
        "mode-a-zen",
    }


def test_unavailable_toolchains_and_incompatible_database_fail_preflight() -> None:
    csharp = evaluate_site(csharp_profile(), inventory(dotnet=False))
    assert not csharp.ready
    unavailable = next(item for item in csharp.capabilities if item.name == "csharp-source")
    assert unavailable.status == "UNAVAILABLE"
    assert unavailable.reasons == ["required tool unavailable: dotnet"]

    document = base_document()
    document["site"] = "bad-db"
    source = document["source"]
    assert isinstance(source, dict)
    database = source["db"]
    assert isinstance(database, dict)
    database["kind"] = "sqlite"
    document["adapters"] = ["db-postgres"]
    incompatible = evaluate_site(SiteProfile.model_validate(document), inventory())
    result = next(item for item in incompatible.capabilities if item.name == "db-postgres")
    assert result.status == "INCOMPATIBLE"
    assert result.reasons == ["database sqlite is not supported"]


def test_unknown_engine_or_executable_ui_code_is_not_silently_enabled() -> None:
    document = base_document()
    document["site"] = "unknown-site"
    document["adapters"] = ["engine-unknown", "ui-code"]
    report = evaluate_site(SiteProfile.model_validate(document), inventory())
    assert not report.ready
    assert {item.status for item in report.capabilities if item.kind == "SOURCE"} == {
        CapabilityStatus.UNKNOWN
    }


def test_matrix_is_order_independent_deterministic_and_secret_free() -> None:
    profiles = [java_profile(), mode_a_dmn_profile(), csharp_profile()]
    first = build_matrix(profiles, inventory())
    second = build_matrix(list(reversed(profiles)), inventory())
    assert first == second
    assert first.matrix_hash == second.matrix_hash
    assert [item.site for item in first.reports] == [
        "csharp-site",
        "dmn-site",
        "java-site",
    ]
    encoded = json.dumps(first.model_dump(mode="json", by_alias=True), sort_keys=True)
    assert "BRP_DATABASE_URL" not in encoded
    assert "password" not in encoded.lower()
    assert all(len(item.report_hash) == 64 for item in first.reports)
