"""Safe acquisition of public GitHub repositories for bounded source imports."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

GITHUB_PATH = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$")
REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
SUBPATH = re.compile(r"^(?:\.|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)$")


def public_github_url(value: str) -> str:
    """Validate and normalize an unauthenticated github.com repository URL."""

    parsed = urlsplit(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not GITHUB_PATH.fullmatch(parsed.path)
    ):
        raise ValueError("repositoryUrl must be a public https://github.com/<owner>/<repo> URL")
    path = parsed.path.removesuffix("/")
    return urlunsplit(("https", "github.com", path, "", ""))


def safe_revision(value: str) -> str:
    """Reject option-like and rev-expression input while allowing normal branches/tags/SHAs."""

    revision = value.strip()
    if not REVISION.fullmatch(revision) or ".." in revision or "@{" in revision or "//" in revision:
        raise ValueError("revision must be a branch, tag, or commit without Git rev expressions")
    return revision


def safe_repository_subpath(value: str) -> str:
    """Allow a repository root or a confined monorepo child directory."""

    subpath = value.strip().replace("\\", "/")
    if not SUBPATH.fullmatch(subpath) or ".." in subpath.split("/"):
        raise ValueError("repositoryPath must be a confined repository-relative directory")
    return subpath


def checkout_public_repository(url: str, revision: str, destination: Path) -> str:
    """Clone an allowlisted public repository and detach at an immutable commit."""

    normalized_url = public_github_url(url)
    normalized_revision = safe_revision(revision)
    subprocess.run(
        [
            "git",
            "-c",
            "credential.helper=",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            normalized_url,
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    completed = subprocess.run(
        ["git", "rev-parse", f"{normalized_revision}^{{commit}}"],
        cwd=destination,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    commit = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("source revision does not resolve to an immutable commit")
    subprocess.run(
        ["git", "checkout", "--detach", commit],
        cwd=destination,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return commit
