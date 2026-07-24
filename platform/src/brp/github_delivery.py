"""Secret-safe GitHub pull-request publication after authoritative delivery gates."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from brp.git_source import public_github_url

BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class GitHubDeliveryError(RuntimeError):
    """A remote branch or pull-request invariant was not satisfied."""


@dataclass(frozen=True)
class PullRequestEvidence:
    repository: str
    number: int
    url: str
    base_branch: str
    head_branch: str
    head_commit: str
    state: str
    reused: bool


CommandRunner = Callable[[list[str], Path | None], str]


def publish_pull_request(
    *,
    workspace: Path,
    repository_url: str,
    base_branch: str,
    head_branch: str,
    expected_head: str,
    title: str,
    body: str,
    runner: CommandRunner | None = None,
    environment: dict[str, str] | None = None,
) -> PullRequestEvidence:
    """Create or reuse the release PR only after independently verifying its remote head."""

    normalized_url = public_github_url(repository_url)
    repository = _repository_slug(normalized_url)
    _validate_ref("base branch", base_branch)
    _validate_ref("head branch", head_branch)
    if not COMMIT.fullmatch(expected_head):
        raise GitHubDeliveryError("expected head must be an immutable 40-character commit")
    if not title.strip() or len(title) > 256:
        raise GitHubDeliveryError("pull-request title must contain 1 to 256 characters")
    if not body.strip() or len(body.encode("utf-8")) > 100_000:
        raise GitHubDeliveryError("pull-request body must contain 1 to 100000 UTF-8 bytes")
    if not (workspace.resolve() / ".git").exists():
        raise GitHubDeliveryError("delivery workspace must be a Git checkout")

    execute = runner or (
        lambda command, cwd: _capture(command, cwd, environment=environment)
    )
    remote = execute(["git", "remote", "get-url", "origin"], workspace).strip()
    if _repository_slug(public_github_url(remote)) != repository:
        raise GitHubDeliveryError("origin does not match the configured GitHub repository")
    remote_line = execute(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{head_branch}"],
        workspace,
    ).strip()
    remote_head = remote_line.split(maxsplit=1)[0] if remote_line else ""
    if remote_head != expected_head:
        raise GitHubDeliveryError("remote branch head does not match tested delivery commit")

    existing = _parse_pull_requests(
        execute(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repository,
                "--state",
                "open",
                "--head",
                head_branch,
                "--json",
                "number,url,headRefOid,baseRefName,headRefName,state",
                "--limit",
                "10",
            ],
            workspace,
        )
    )
    if len(existing) > 1:
        raise GitHubDeliveryError("multiple open pull requests exist for the delivery branch")
    reused = bool(existing)
    if not reused:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".md", delete=False
        ) as handle:
            handle.write(body)
            body_path = Path(handle.name)
        try:
            execute(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    repository,
                    "--base",
                    base_branch,
                    "--head",
                    head_branch,
                    "--title",
                    title,
                    "--body-file",
                    str(body_path),
                ],
                workspace,
            )
        finally:
            body_path.unlink(missing_ok=True)

    document = json.loads(
        execute(
            [
                "gh",
                "pr",
                "view",
                head_branch,
                "--repo",
                repository,
                "--json",
                "number,url,headRefOid,baseRefName,headRefName,state",
            ],
            workspace,
        )
    )
    _verify_pull_request(document, base_branch, head_branch, expected_head)
    return PullRequestEvidence(
        repository=repository,
        number=int(document["number"]),
        url=str(document["url"]),
        base_branch=base_branch,
        head_branch=head_branch,
        head_commit=expected_head,
        state=str(document["state"]),
        reused=reused,
    )


def _capture(
    command: list[str],
    cwd: Path | None,
    *,
    environment: dict[str, str] | None = None,
) -> str:
    process_environment = os.environ.copy()
    process_environment.update(environment or {})
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=process_environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise GitHubDeliveryError(f"required delivery tool is unavailable: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubDeliveryError(f"delivery tool timed out: {command[0]}") from exc
    if completed.returncode != 0:
        raise GitHubDeliveryError(
            f"delivery tool failed: {command[0]} (exit {completed.returncode})"
        )
    return completed.stdout


def _repository_slug(url: str) -> str:
    return urlsplit(url).path.strip("/").removesuffix(".git")


def _validate_ref(label: str, value: str) -> None:
    if not BRANCH.fullmatch(value) or ".." in value or "@{" in value or "//" in value:
        raise GitHubDeliveryError(f"{label} is unsafe")


def _parse_pull_requests(value: str) -> list[dict[str, Any]]:
    try:
        document = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GitHubDeliveryError("GitHub CLI returned invalid JSON") from exc
    if not isinstance(document, list) or any(not isinstance(item, dict) for item in document):
        raise GitHubDeliveryError("GitHub CLI returned an invalid pull-request list")
    return document


def _verify_pull_request(
    document: object, base_branch: str, head_branch: str, expected_head: str
) -> None:
    if not isinstance(document, dict):
        raise GitHubDeliveryError("GitHub CLI returned an invalid pull request")
    expected = {
        "baseRefName": base_branch,
        "headRefName": head_branch,
        "headRefOid": expected_head,
        "state": "OPEN",
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise GitHubDeliveryError("pull request does not match the verified delivery branch")
    if not isinstance(document.get("number"), int) or not str(document.get("url", "")).startswith(
        "https://github.com/"
    ):
        raise GitHubDeliveryError("pull request identity is invalid")
