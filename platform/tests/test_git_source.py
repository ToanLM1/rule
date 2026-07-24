import pytest
from pydantic import ValidationError

from brp.api.v1 import ImportRunRequest
from brp.git_source import public_github_url, safe_repository_subpath, safe_revision


def test_public_github_url_accepts_only_credential_free_github_https() -> None:
    assert (
        public_github_url("https://github.com/example/rules.git")
        == "https://github.com/example/rules.git"
    )
    for value in (
        "http://github.com/example/rules",
        "https://user:token@github.com/example/rules",
        "https://gitlab.com/example/rules",
        "https://github.com/example/rules?token=secret",
        "https://github.com/example/rules/extra",
    ):
        with pytest.raises(ValueError):
            public_github_url(value)


def test_revision_rejects_git_expression_and_option_input() -> None:
    assert safe_revision("feature/public-demo") == "feature/public-demo"
    assert safe_revision("a" * 40) == "a" * 40
    for value in ("--upload-pack=evil", "main..other", "HEAD@{1}", "feature//x"):
        with pytest.raises(ValueError):
            safe_revision(value)


def test_repository_subpath_is_confined() -> None:
    assert safe_repository_subpath(".") == "."
    assert safe_repository_subpath("fixtures/legacy-enrollment") == "fixtures/legacy-enrollment"
    for value in ("../secret", "/absolute", "nested/../../secret", "C:\\repo"):
        with pytest.raises(ValueError):
            safe_repository_subpath(value)


def test_code_java_accepts_direct_public_repository_without_profile() -> None:
    request = ImportRunRequest.model_validate(
        {
            "siteId": "00000000-0000-0000-0000-000000000001",
            "adapter": "code-java",
            "filename": "repository.java",
            "revision": "main",
            "repositoryUrl": "https://github.com/example/rules",
            "repositoryAlias": "dummy-rules",
            "className": "example.Rules",
            "method": "evaluate",
        }
    )
    assert request.profile_revision is None
    assert request.repository_url == "https://github.com/example/rules"


def test_code_java_requires_exactly_one_repository_source() -> None:
    base = {
        "siteId": "00000000-0000-0000-0000-000000000001",
        "adapter": "code-java",
        "filename": "repository.java",
        "revision": "main",
        "repositoryAlias": "dummy-rules",
        "className": "example.Rules",
        "method": "evaluate",
    }
    with pytest.raises(ValidationError):
        ImportRunRequest.model_validate(base)
    with pytest.raises(ValidationError):
        ImportRunRequest.model_validate(
            {
                **base,
                "profileRevision": 1,
                "repositoryUrl": "https://github.com/example/rules",
            }
        )
