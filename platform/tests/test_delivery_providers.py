import httpx

from brp.delivery_providers import GitHubProvider, GitLabProvider


def test_github_reuses_existing_pull_request_without_creating_another() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(
            200,
            json=[{"number": 42, "html_url": "https://github.test/pr/42", "state": "open"}],
        )

    client = httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler))
    result = GitHubProvider("secret", client=client).ensure_change_request(
        repository="org/repo", head="rules/gen-x-r1", base="main", title="x", body="evidence"
    )
    assert result.external_id == "42"
    assert calls == ["GET"]


def test_gitlab_creates_merge_request_when_none_exists() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(
            201,
            json={"iid": 7, "web_url": "https://gitlab.test/mr/7", "state": "opened"},
        )

    client = httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler))
    result = GitLabProvider("secret", client=client).ensure_change_request(
        repository="org/repo", head="rules/gen-x-r1", base="main", title="x", body="evidence"
    )
    assert result.external_id == "7"
    assert calls == ["GET", "POST"]
