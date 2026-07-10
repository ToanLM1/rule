"""Pinned Java reachability and bounded decision slicing contracts.

The locator consumes the same method facts emitted by the pinned Joern smoke path.  Its
source fallback keeps unit tests and air-gapped fixture runs deterministic; production
runs can replace ``method_facts`` with CPGQL output without changing the slice contract.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pydantic import Field

from brp.ir.models import StrictModel


class LocatedMethod(StrictModel):
    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    file: str
    class_name: str
    method: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    source: str
    entry_point: bool = False


class JoernLocator:
    """Locate an entry method and only its reachable private helpers."""

    def __init__(self, repository: Path, alias: str, revision: str = "HEAD") -> None:
        self.repository = repository.resolve()
        self.alias = alias
        self.revision = _resolve_revision(self.repository, revision)

    def locate(self, class_name: str, method: str) -> list[LocatedMethod]:
        relative = Path("src/main/java") / Path(*class_name.split("."))
        path = (self.repository / relative).with_suffix(".java")
        if not path.is_file():
            raise FileNotFoundError(f"Java entry class not found: {class_name}")
        text = path.read_text(encoding="utf-8")
        facts = _method_facts(text)
        by_name = {fact[0]: fact for fact in facts}
        if method not in by_name:
            raise ValueError(f"entry method not found: {class_name}#{method}")

        reachable: list[str] = []
        pending = [method]
        while pending:
            current = pending.pop(0)
            if current in reachable:
                continue
            reachable.append(current)
            body = by_name[current][3]
            called = sorted(
                name
                for name in by_name
                if name != current and re.search(rf"\b{re.escape(name)}\s*\(", body)
            )
            pending.extend(called)

        file_name = path.relative_to(self.repository).as_posix()
        return [
            LocatedMethod(
                repository=self.alias,
                revision=self.revision,
                file=file_name,
                class_name=class_name,
                method=name,
                line_start=by_name[name][1],
                line_end=by_name[name][2],
                source=by_name[name][3],
                entry_point=name == method,
            )
            for name in reachable
        ]


JavaLocator = JoernLocator


def _resolve_revision(repository: Path, revision: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", revision],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    resolved = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ValueError("source revision must resolve to an immutable commit")
    return resolved


def _method_facts(source: str) -> list[tuple[str, int, int, str]]:
    lines = source.splitlines()
    signature = re.compile(
        r"^\s*(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>\[\], ?]+)\s+"
        r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\("
    )
    facts: list[tuple[str, int, int, str]] = []
    index = 0
    while index < len(lines):
        match = signature.search(lines[index])
        if match is None:
            index += 1
            continue
        start = index
        depth = 0
        seen_open = False
        while index < len(lines):
            depth += lines[index].count("{") - lines[index].count("}")
            seen_open = seen_open or "{" in lines[index]
            if seen_open and depth == 0:
                break
            index += 1
        end = min(index, len(lines) - 1)
        facts.append((match.group("name"), start + 1, end + 1, "\n".join(lines[start : end + 1])))
        index += 1
    return facts
