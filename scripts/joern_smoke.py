"""Pinned Joern launcher and smoke checks for native or Docker execution."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

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


def run_checked(command: list[str], *, timeout: int) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        tail = "\n".join(output.splitlines()[-30:])
        raise RuntimeError(f"Joern command failed ({result.returncode}):\n{tail}")
    return output


def fixture_repository(site_path: Path) -> Path:
    document = yaml.safe_load(site_path.read_text(encoding="utf-8"))
    repositories = document["source"]["repositories"]
    path = ROOT / repositories[0]["path"]
    if not path.is_dir():
        raise FileNotFoundError(f"Fixture repository not found: {path}")
    return path.resolve()


def docker_mount(path: Path, target: str, *, read_only: bool = False) -> str:
    suffix = ":ro" if read_only else ""
    return f"{path}:{target}{suffix}"


def fixture_smoke(lock: dict[str, str], site_path: Path) -> tuple[int, int]:
    image = pinned_image(lock)
    source = fixture_repository(site_path)
    query = (ROOT / "scripts" / "joern_method_count.sc").resolve()
    with tempfile.TemporaryDirectory(prefix="brp-joern-") as temporary:
        output_dir = Path(temporary).resolve()
        build_command = [
            "docker",
            "run",
            "--rm",
            "-v",
            docker_mount(source, "/workspace/source", read_only=True),
            "-v",
            docker_mount(output_dir, "/workspace/out"),
            image,
            "javasrc2cpg",
            "/workspace/source",
            "--output",
            "/workspace/out/cpg.bin",
        ]
        run_checked(build_command, timeout=300)

        query_command = [
            "docker",
            "run",
            "--rm",
            "-v",
            docker_mount(output_dir, "/workspace/out"),
            "-v",
            docker_mount(query, "/workspace/query.sc", read_only=True),
            image,
            "joern",
            "--script",
            "/workspace/query.sc",
            "--param",
            "cpgFile=/workspace/out/cpg.bin",
        ]
        output = run_checked(query_command, timeout=180)

    method_match = re.search(r"BRP_METHOD_COUNT=(\d+)", output)
    target_match = re.search(r"BRP_TARGET_COUNT=(\d+)", output)
    if method_match is None or target_match is None:
        raise RuntimeError("Joern smoke markers were not emitted")
    return int(method_match.group(1)), int(target_match.group(1))


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
    if not args.site:
        raise SystemExit("--site is required unless --version-only is used")
    site_path = (ROOT / args.site).resolve()
    method_count, target_count = fixture_smoke(lock, site_path)
    print(f"Method count: {method_count}; EnrollmentValidator.evaluate: {target_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
