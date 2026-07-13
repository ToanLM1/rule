import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from brp.delivery import establish_seam_baseline, transactional_delivery_gate

ROOT = Path(__file__).resolve().parents[3]


def release_from_baseline(workspace: Path, release: Path) -> None:
    relative = Path("src/generated/java/brp/rules/generated/EnrollmentEligibilityDecision.java")
    target = release / relative
    target.parent.mkdir(parents=True)
    target.write_bytes((workspace / relative).read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (release / "release-manifest.json").write_text(
        json.dumps(
            {
                "releaseHash": "a" * 64,
                "outputs": [{"path": relative.as_posix(), "hash": digest}],
            }
        ),
        encoding="utf-8",
    )


def test_gate_success_and_corrupted_source_cleanup(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    baseline_work = tmp_path / "baseline"
    establish_seam_baseline(ROOT, ROOT / "fixtures/legacy-enrollment", remote, baseline_work)
    release = tmp_path / "release"
    release.mkdir()
    release_from_baseline(baseline_work, release)
    success_work = tmp_path / "success-work"
    result = transactional_delivery_gate(remote, "seam-baseline-v1", release, success_work)
    assert result.tests == ("generated-golden", "target-regression")
    assert _capture(["git", "branch", "--show-current"], success_work) == ""

    source = next(release.rglob("EnrollmentEligibilityDecision.java"))
    source.write_text("this is not Java", encoding="utf-8")
    failed_work = tmp_path / "failed-work"
    with pytest.raises(subprocess.CalledProcessError):
        transactional_delivery_gate(remote, "seam-baseline-v1", release, failed_work)
    assert failed_work.exists()
    assert _capture(["git", "branch", "--show-current"], failed_work) == ""
    assert _capture(["git", "rev-parse", "HEAD"], failed_work) == result.base_commit
    assert failed_work.with_suffix(".failure.md").is_file()


def _capture(command: list[str], cwd: Path) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()
