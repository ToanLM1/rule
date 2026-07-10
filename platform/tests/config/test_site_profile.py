import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from brp.config import load_site_profile
from brp.config.models import SiteProfile

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "config" / "sites" / "fixture.yaml"


def document() -> dict[str, object]:
    value = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_fixture_profile_parses() -> None:
    profile = load_site_profile(FIXTURE)
    assert profile.site == "fixture"
    assert profile.source.program_contexts[0].class_name == "legacy.EnrollmentValidator"
    assert profile.target is not None
    assert profile.target.composition.decisions["premium_adjustments"].aggregate == "SUM"


@pytest.mark.parametrize(
    "path",
    ["../secrets", "config/../../secrets", "C:\\secrets\\target", "/etc/passwd"],
)
def test_source_path_traversal_and_absolute_paths_fail(path: str) -> None:
    value = document()
    value["source"]["repositories"][0]["path"] = path
    with pytest.raises(ValidationError, match="repository-relative"):
        SiteProfile.model_validate(value)


def test_connection_value_cannot_replace_environment_name() -> None:
    value = document()
    value["source"]["db"]["connection_env"] = "postgresql://user:secret@db/brp"
    with pytest.raises(ValidationError, match="String should match pattern"):
        SiteProfile.model_validate(value)


def test_secret_fields_are_forbidden() -> None:
    value = document()
    value["source"]["db"]["password"] = "secret"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SiteProfile.model_validate(value)


def test_unknown_setting_is_forbidden() -> None:
    value = document()
    value["target"]["custom_shell_hook"] = "danger"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SiteProfile.model_validate(value)


def test_unknown_program_repository_is_rejected() -> None:
    value = document()
    value["source"]["program_contexts"][0]["repository"] = "missing"
    with pytest.raises(ValidationError, match="unknown repositories"):
        SiteProfile.model_validate(value)


def test_duplicate_adapters_are_rejected() -> None:
    value = document()
    value["adapters"].append(value["adapters"][0])
    with pytest.raises(ValidationError, match="unique"):
        SiteProfile.model_validate(value)


def test_invalid_composition_aggregate_is_rejected() -> None:
    value = document()
    value["target"]["composition"]["decisions"]["premium_adjustments"][
        "aggregate"
    ] = "EVAL"
    with pytest.raises(ValidationError):
        SiteProfile.model_validate(value)


def test_mode_b_requires_target() -> None:
    value = document()
    value.pop("target")
    with pytest.raises(ValidationError, match="requires target"):
        SiteProfile.model_validate(value)


def test_model_validation_does_not_mutate_input() -> None:
    value = document()
    original = copy.deepcopy(value)
    SiteProfile.model_validate(value)
    assert value == original
