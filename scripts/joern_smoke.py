"""Pinned Joern launcher and smoke checks for native or Docker execution."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "config" / "joern.lock.json"


def load_lock() -> dict[str, str]:
    """Load the reviewed Joern version lock."""
    value = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    required = {"image", "digest", "version"}
    if not required.issubset(value):
        raise ValueError(f"Joern lock is missing: {sorted(required - set(value))}")
    return value


def pinned_image(lock: dict[str, str]) -> str:
    return f"{lock['image']}@{lock['digest']}"


def docker_version(lock: dict[str, str]) -> str:
    """Start the pinned CLI non-interactively and parse its banner version."""
    command = ["docker", "run", "--rm", pinned_image(lock), "joern", "--version"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    output = result.stdout + result.stderr
    match = re.search(r"Version:\s*(\d+\.\d+\.\d+)", output)
    if result.returncode != 0 or match is None:
        raise RuntimeError("Pinned Joern image did not start or report a version")
    return match.group(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-only", action="store_true")
    parser.add_argument("--site")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lock = load_lock()
    version = docker_version(lock)
    if version != lock["version"]:
        raise RuntimeError(f"Joern version drift: expected {lock['version']}, got {version}")
    print(f"Joern {version} ({pinned_image(lock)})")
    if args.version_only:
        return 0
    raise SystemExit("Fixture CPG smoke is implemented by T-007; pass --version-only for E-003")


if __name__ == "__main__":
    raise SystemExit(main())
