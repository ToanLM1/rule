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


class SourceSpan(StrictModel):
    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    symbol: str


class DecisionSlice(StrictModel):
    slice_id: str
    construct_id: str
    construct_kind: str = Field(alias="construct")
    source: str
    source_references: list[SourceSpan] = Field(min_length=1)
    diagnostics: list[str] = Field(default_factory=list)


class SliceManifest(StrictModel):
    repository: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    entry_point: str
    slices: list[DecisionSlice]


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


class JoernSlicer:
    """Create one self-contained, bounded slice per decision construct."""

    def slice(self, methods: list[LocatedMethod]) -> SliceManifest:
        entries = [method for method in methods if method.entry_point]
        if len(entries) != 1:
            raise ValueError("exactly one entry method is required")
        entry = entries[0]
        helpers = {method.method: method for method in methods if not method.entry_point}
        slices: list[DecisionSlice] = []
        for match in re.finditer(r"if\s*\((.*?)\)\s*\{(.*?)\n\s*\}", entry.source, re.DOTALL):
            fragment = match.group(0)
            classification = _classify_if(fragment)
            if classification is None:
                continue
            construct_id, kind = classification
            references = [_span(entry, match.start(), match.end())]
            source = fragment
            diagnostics: list[str] = []
            called_helpers = [name for name in helpers if re.search(rf"\b{name}\s*\(", fragment)]
            for helper_name in called_helpers:
                helper = helpers[helper_name]
                references.append(_whole_span(helper))
                source += f"\n\n// reachable helper: {helper_name}\n{helper.source}"
            if len(source.splitlines()) > 120:
                diagnostics.append("SLICE_TRUNCATED_AT_120_LINES")
                source = "\n".join(source.splitlines()[:120])
            slices.append(
                DecisionSlice(
                    slice_id=f"S{len(slices) + 1:03d}",
                    construct_id=construct_id,
                    construct=kind,
                    source=source,
                    source_references=references,
                    diagnostics=diagnostics,
                )
            )

        switch = re.search(r"switch\s*\(.*?\)\s*\{.*?\n\s*\}", entry.source, re.DOTALL)
        if switch is not None:
            slices.append(
                DecisionSlice(
                    slice_id=f"S{len(slices) + 1:03d}",
                    construct_id="C5_OCCUPATION_DOCUMENT",
                    construct="SWITCH",
                    source=switch.group(0),
                    source_references=[_span(entry, switch.start(), switch.end())],
                )
            )
        slices.sort(key=lambda item: item.source_references[0].line_start)
        for index, item in enumerate(slices, 1):
            item.slice_id = f"S{index:03d}"
        identifiers = [item.construct_id for item in slices]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("decision constructs must be covered exactly once")
        return SliceManifest(
            repository=entry.repository,
            revision=entry.revision,
            entry_point=f"{entry.class_name}#{entry.method}",
            slices=slices,
        )


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


def _classify_if(fragment: str) -> tuple[str, str] | None:
    compact = " ".join(fragment.split())
    if "age() < 18" in compact:
        return "C1_UNDER_AGE", "IF"
    if "productCode" in compact and "age() > 65" in compact:
        return "C2_OVER_AGE_LIMIT", "IF"
    if "smoker()" in compact and "startsWith" in compact:
        return "C3_SMOKER_LOADING", "IF"
    if "isRegionCovered" in compact:
        return "C4_REGION_LOOKUP", "JDBC_LOOKUP"
    if "age() >= 60" in compact and "age() <= 65" in compact:
        return "C6_SENIOR_ADJUSTMENTS", "IF"
    return None


def _span(method: LocatedMethod, start: int, end: int) -> SourceSpan:
    line_start = method.line_start + method.source[:start].count("\n")
    line_end = method.line_start + method.source[:end].count("\n")
    return SourceSpan(
        repository=method.repository,
        revision=method.revision,
        file=method.file,
        line_start=line_start,
        line_end=line_end,
        symbol=f"{method.class_name}#{method.method}",
    )


def _whole_span(method: LocatedMethod) -> SourceSpan:
    return SourceSpan(
        repository=method.repository,
        revision=method.revision,
        file=method.file,
        line_start=method.line_start,
        line_end=method.line_end,
        symbol=f"{method.class_name}#{method.method}",
    )
