"""Fail-fast structural verification for the fresh-checkout demo guide."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_GUIDE_TEXT = (
    "bash scripts/demo-mode-b.sh",
    "pwsh -File scripts/demo-mode-b.ps1",
    "BEFORE: ELIGIBLE",
    "AFTER: REJECTED(UNDER_AGE)",
    "EXECUTOR: GENERATED_JAVA",
    "ADVISORY",
    "AUTHORITATIVE",
)
REQUIRED_FILES = (
    "architecture.md",
    "IMPLEMENTATION_PLAN.md",
    "config/sites/fixture.yaml",
    "scripts/demo_mode_b.py",
    "scripts/demo-mode-b.sh",
    "scripts/demo-mode-b.ps1",
    "platform/uv.lock",
    "mcp-db-connector/uv.lock",
    "ui/pnpm-lock.yaml",
    "java-toolchain/gradle/wrapper/gradle-wrapper.jar",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", type=Path, required=True)
    args = parser.parse_args()
    guide = (
        (ROOT / args.guide).resolve() if not args.guide.is_absolute() else args.guide
    )
    if not guide.is_file():
        raise SystemExit(f"guide not found: {guide}")
    text = guide.read_text(encoding="utf-8")
    missing_text = [value for value in REQUIRED_GUIDE_TEXT if value not in text]
    missing_files = [value for value in REQUIRED_FILES if not (ROOT / value).is_file()]
    if missing_text or missing_files:
        raise SystemExit(
            f"guide verification failed; missing text={missing_text}, missing files={missing_files}"
        )
    required_tools = ("git", "uv", "java", "node", "pnpm", "docker")
    unavailable = [tool for tool in required_tools if shutil.which(tool) is None]
    if unavailable:
        raise SystemExit(f"required tools unavailable: {unavailable}")
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(
        f"Fresh-checkout guide verified: platform={platform.platform()} commit={commit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
