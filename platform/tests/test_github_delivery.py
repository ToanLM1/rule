import json
from pathlib import Path

import pytest

from brp.github_delivery import GitHubDeliveryError, publish_pull_request

HEAD = "a" * 40


def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "delivery"
    (root / ".git").mkdir(parents=True)
    return root


def response(command: list[str], cwd: Path | None, *, existing: bool = False) -> str:
    assert cwd is not None
    if command[:4] == ["git", "remote", "get-url", "origin"]:
        return "https://github.com/example/rules.git\n"
    if command[:3] == ["git", "ls-remote", "--heads"]:
        return f"{HEAD}\trefs/heads/rules/release-42\n"
    if command[:3] == ["gh", "pr", "list"]:
        return json.dumps([{"number": 7}] if existing else [])
    if command[:3] == ["gh", "pr", "create"]:
        body_path = Path(command[command.index("--body-file") + 1])
        assert body_path.read_text(encoding="utf-8") == "Evidence and test summary"
        return "https://github.com/example/rules/pull/7\n"
    if command[:3] == ["gh", "pr", "view"]:
        return json.dumps(
            {
                "number": 7,
                "url": "https://github.com/example/rules/pull/7",
                "baseRefName": "main",
                "headRefName": "rules/release-42",
                "headRefOid": HEAD,
                "state": "OPEN",
            }
        )
    raise AssertionError(command)


def test_creates_and_independently_verifies_pull_request(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], cwd: Path | None) -> str:
        calls.append(command)
        return response(command, cwd)

    result = publish_pull_request(
        workspace=workspace(tmp_path),
        repository_url="https://github.com/example/rules",
        base_branch="main",
        head_branch="rules/release-42",
        expected_head=HEAD,
        title="Generated rules release 42",
        body="Evidence and test summary",
        runner=runner,
    )

    assert result.url.endswith("/pull/7")
    assert result.reused is False
    assert any(command[:3] == ["gh", "pr", "create"] for command in calls)
    assert calls[-1][:3] == ["gh", "pr", "view"]


def test_reuses_single_open_pull_request_idempotently(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], cwd: Path | None) -> str:
        calls.append(command)
        return response(command, cwd, existing=True)

    result = publish_pull_request(
        workspace=workspace(tmp_path),
        repository_url="https://github.com/example/rules.git",
        base_branch="main",
        head_branch="rules/release-42",
        expected_head=HEAD,
        title="Generated rules release 42",
        body="Evidence and test summary",
        runner=runner,
    )

    assert result.reused is True
    assert not any(command[:3] == ["gh", "pr", "create"] for command in calls)


def test_refuses_unverified_remote_head(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path | None) -> str:
        if command[:3] == ["git", "ls-remote", "--heads"]:
            return f"{'b' * 40}\trefs/heads/rules/release-42\n"
        return response(command, cwd)

    with pytest.raises(GitHubDeliveryError, match="does not match"):
        publish_pull_request(
            workspace=workspace(tmp_path),
            repository_url="https://github.com/example/rules",
            base_branch="main",
            head_branch="rules/release-42",
            expected_head=HEAD,
            title="Generated rules release 42",
            body="Evidence and test summary",
            runner=runner,
        )
