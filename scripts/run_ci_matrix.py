"""Run the Phase-0 CI job commands locally in a deterministic order."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def java_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if os.name == "nt":
        default = Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot")
        java_home = Path(environment.get("JAVA_HOME", default))
        environment["JAVA_HOME"] = str(java_home)
        environment["PATH"] = f"{java_home / 'bin'}{os.pathsep}{environment['PATH']}"
    environment["JAVA_TOOL_OPTIONS"] = "-Dfile.encoding=UTF-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def run(name: str, command: list[str], cwd: Path) -> None:
    print(f"[{name}] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=java_environment(), check=True)


def gradle_command(project: Path, task: str) -> list[str]:
    wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
    return [str(project / wrapper), task, "--no-daemon"]


def main() -> int:
    uv = shutil.which("uv") or "uv"
    pnpm = shutil.which("pnpm") or "pnpm"
    run("platform-lint", [uv, "run", "ruff", "check", "."], ROOT / "platform")
    run("platform-test", [uv, "run", "pytest"], ROOT / "platform")
    run("connector-lint", [uv, "run", "ruff", "check", "."], ROOT / "mcp-db-connector")
    run("connector-test", [uv, "run", "pytest"], ROOT / "mcp-db-connector")
    run("java-toolchain", gradle_command(ROOT / "java-toolchain", "build"), ROOT / "java-toolchain")
    fixture = ROOT / "fixtures" / "legacy-enrollment"
    run("fixture", gradle_command(fixture, "test"), fixture)
    run("ui-build", [pnpm, "build"], ROOT / "ui")
    run("ui-test", [pnpm, "run", "test", "--", "--run"], ROOT / "ui")
    print("Local CI matrix passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
