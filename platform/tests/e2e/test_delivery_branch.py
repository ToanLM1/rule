import subprocess
from pathlib import Path

from brp.delivery import (
    establish_seam_baseline,
    publish_delivery_branch,
    transactional_delivery_gate,
)
from tests.e2e.test_delivery_gate import release_from_baseline

ROOT = Path(__file__).resolve().parents[3]


def test_success_creates_commit_push_and_review_report(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    baseline = tmp_path / "baseline"
    establish_seam_baseline(ROOT, ROOT / "fixtures/legacy-enrollment", remote, baseline)
    release = tmp_path / "release"
    release.mkdir()
    release_from_baseline(baseline, release)
    gate = transactional_delivery_gate(remote, "seam-baseline-v1", release, tmp_path / "delivery")
    result = publish_delivery_branch(
        gate,
        "enrollment_eligibility",
        2,
        {"changedRules": [{"ruleId": "R001", "path": "/when"}]},
    )
    assert result.branch == "rules/gen-enrollment_eligibility-r2"
    remote_head = subprocess.run(
        ["git", "--git-dir", str(remote), "rev-parse", result.branch],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert remote_head == result.head_commit
    report = result.review_report.read_text(encoding="utf-8")
    assert result.base_commit in report
    assert result.head_commit in report
    assert "Semantic rule diff" in report
    assert "release-manifest.json" in report
