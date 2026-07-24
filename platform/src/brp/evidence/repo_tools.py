"""Read-only bounded tools for a checked-out Git repository."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class RepositoryToolError(ValueError):
    pass


class RepositoryEvidenceTools:
    def __init__(
        self,
        root: Path,
        *,
        timeout_seconds: int = 10,
        max_output_bytes: int = 1_000_000,
        max_file_bytes: int = 250_000,
    ) -> None:
        resolved = root.resolve()
        if not (resolved / ".git").exists():
            raise RepositoryToolError("repository root must contain .git")
        self.root = resolved
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.max_file_bytes = max_file_bytes

    def commit(self) -> str:
        value = self._run(["git", "rev-parse", "HEAD"]).strip()
        if len(value) not in {40, 64} or any(char not in "0123456789abcdef" for char in value):
            raise RepositoryToolError("git returned an invalid immutable commit")
        return value

    def inventory(self, *, suffixes: tuple[str, ...] = (), limit: int = 5000) -> list[str]:
        if limit < 1 or limit > 10_000:
            raise RepositoryToolError("inventory limit must be between 1 and 10000")
        raw = self._run(["git", "ls-files", "-z"])
        files = [item for item in raw.split("\0") if item]
        if suffixes:
            lowered = tuple(item.lower() for item in suffixes)
            files = [item for item in files if item.lower().endswith(lowered)]
        return files[:limit]

    def search(
        self,
        pattern: str,
        *,
        glob: str = "*.java",
        limit: int = 200,
        regex: bool = False,
    ) -> list[dict[str, object]]:
        if not pattern or len(pattern) > 500:
            raise RepositoryToolError("search pattern must contain 1 to 500 characters")
        if not glob or len(glob) > 100 or glob.startswith(("/", "\\")) or ".." in glob:
            raise RepositoryToolError("search glob is unsafe")
        if limit < 1 or limit > 1000:
            raise RepositoryToolError("search limit must be between 1 and 1000")
        command = ["rg", "--json", "--line-number", "--glob", glob]
        if not regex:
            command.append("--fixed-strings")
        command.extend(["--", pattern, "."])
        raw = self._run(command, accepted=(0, 1))
        matches: list[dict[str, object]] = []
        for line in raw.splitlines():
            event = json.loads(line)
            if event.get("type") != "match":
                continue
            data = event["data"]
            relative = self._safe_relative(str(data["path"]["text"]))
            matches.append(
                {
                    "file": relative,
                    "line": int(data["line_number"]),
                    "text": str(data["lines"]["text"]).rstrip("\r\n"),
                }
            )
            if len(matches) >= limit:
                break
        return matches

    def read(
        self, relative_path: str, *, line_start: int = 1, line_end: int = 400
    ) -> dict[str, Any]:
        if line_start < 1 or line_end < line_start or line_end - line_start > 1000:
            raise RepositoryToolError("read range is invalid or exceeds 1001 lines")
        relative = self._safe_relative(relative_path)
        path = (self.root / relative).resolve()
        if not path.is_file() or not path.is_relative_to(self.root):
            raise RepositoryToolError("requested file is unavailable")
        if path.stat().st_size > self.max_file_bytes:
            raise RepositoryToolError("requested file exceeds the configured byte limit")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryToolError("requested file is not valid UTF-8 text") from exc
        lines = text.splitlines()
        selected = lines[line_start - 1 : line_end]
        if not selected:
            raise RepositoryToolError("requested range contains no text")
        snippet = "\n".join(selected)
        return {
            "file": relative,
            "lineStart": line_start,
            "lineEnd": line_start + len(selected) - 1,
            "contentHash": hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
            "snippet": snippet,
        }

    def git_history(self, relative_path: str, *, limit: int = 20) -> list[dict[str, str]]:
        if limit < 1 or limit > 100:
            raise RepositoryToolError("history limit must be between 1 and 100")
        relative = self._safe_relative(relative_path)
        raw = self._run(
            [
                "git",
                "log",
                f"-{limit}",
                "--format=%H%x1f%aI%x1f%s",
                "--",
                relative,
            ]
        )
        result: list[dict[str, str]] = []
        for line in raw.splitlines():
            commit, at, subject = line.split("\x1f", 2)
            result.append({"commit": commit, "at": at, "subject": subject})
        return result

    def _safe_relative(self, value: str) -> str:
        normalized = value.replace("\\", "/").removeprefix("./")
        path = Path(normalized)
        if path.is_absolute() or ".." in path.parts or not normalized:
            raise RepositoryToolError("repository path is unsafe")
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise RepositoryToolError("repository path escapes the checkout")
        return path.as_posix()

    def _run(self, command: list[str], *, accepted: tuple[int, ...] = (0,)) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                check=False,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RepositoryToolError(f"required tool is unavailable: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RepositoryToolError(f"tool timed out: {command[0]}") from exc
        if result.returncode not in accepted:
            raise RepositoryToolError(f"tool failed: {command[0]} (exit {result.returncode})")
        if len(result.stdout) > self.max_output_bytes:
            raise RepositoryToolError(f"tool output exceeds limit: {command[0]}")
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RepositoryToolError(f"tool returned invalid UTF-8: {command[0]}") from exc
