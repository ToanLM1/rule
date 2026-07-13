import os
import subprocess
from pathlib import Path

from brp.delivery import establish_seam_baseline

ROOT = Path(__file__).resolve().parents[3]


def test_fresh_clone_builds_and_legacy_entry_calls_facade(tmp_path: Path) -> None:
    remote = tmp_path / "fixture-remote.git"
    workspace = tmp_path / "baseline-work"
    commit = establish_seam_baseline(ROOT, ROOT / "fixtures/legacy-enrollment", remote, workspace)
    clone = tmp_path / "fresh-clone"
    subprocess.run(["git", "clone", str(remote), str(clone)], check=True)
    java_home = Path(
        os.environ.get("JAVA_HOME", r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot")
    )
    environment = {
        **os.environ,
        "JAVA_HOME": str(java_home),
        "PATH": f"{java_home / 'bin'}{os.pathsep}{os.environ['PATH']}",
    }
    gradle = clone / ("gradlew.bat" if os.name == "nt" else "gradlew")
    subprocess.run([str(gradle), "test", "--no-daemon"], cwd=clone, env=environment, check=True)
    source = (clone / "src/main/java/legacy/EnrollmentValidator.java").read_text(encoding="utf-8")
    assert "EnrollmentRuleModule.evaluate(request, connection)" in source
    assert (
        subprocess.run(
            ["git", "rev-parse", "seam-baseline-v1"],
            cwd=clone,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == commit
    )
