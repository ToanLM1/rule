"""Idempotent GitHub pull-request and GitLab merge-request providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx


class DeliveryProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangeRequest:
    external_id: str
    url: str
    state: str


class ChangeRequestProvider(Protocol):
    def ensure_change_request(
        self, *, repository: str, head: str, base: str, title: str, body: str
    ) -> ChangeRequest: ...


class GitHubProvider:
    def __init__(self, token: str, *, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=20,
        )

    def ensure_change_request(
        self, *, repository: str, head: str, base: str, title: str, body: str
    ) -> ChangeRequest:
        existing = self.client.get(
            f"/repos/{repository}/pulls", params={"state": "open", "head": head, "base": base}
        )
        _raise(existing)
        records = existing.json()
        if records:
            return _github_response(records[0])
        created = self.client.post(
            f"/repos/{repository}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )
        _raise(created)
        return _github_response(created.json())


class GitLabProvider:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://gitlab.com/api/v4",
        client: httpx.Client | None = None,
    ) -> None:
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={"PRIVATE-TOKEN": token},
            timeout=20,
        )

    def ensure_change_request(
        self, *, repository: str, head: str, base: str, title: str, body: str
    ) -> ChangeRequest:
        project = quote(repository, safe="")
        existing = self.client.get(
            f"/projects/{project}/merge_requests",
            params={
                "state": "opened",
                "source_branch": head,
                "target_branch": base,
            },
        )
        _raise(existing)
        records = existing.json()
        if records:
            return _gitlab_response(records[0])
        created = self.client.post(
            f"/projects/{project}/merge_requests",
            json={
                "title": title,
                "source_branch": head,
                "target_branch": base,
                "description": body,
            },
        )
        _raise(created)
        return _gitlab_response(created.json())


def _raise(response: httpx.Response) -> None:
    if response.is_success:
        return
    raise DeliveryProviderError(f"change-request provider returned HTTP {response.status_code}")


def _github_response(value: dict[str, object]) -> ChangeRequest:
    return ChangeRequest(str(value["number"]), str(value["html_url"]), str(value["state"]))


def _gitlab_response(value: dict[str, object]) -> ChangeRequest:
    return ChangeRequest(str(value["iid"]), str(value["web_url"]), str(value["state"]))
