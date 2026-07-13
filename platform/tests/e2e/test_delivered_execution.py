import hashlib
import json
from pathlib import Path

from brp.delivery import (
    establish_seam_baseline,
    prove_delivered_execution,
    publish_delivery_branch,
    transactional_delivery_gate,
)

ROOT = Path(__file__).resolve().parents[3]


def test_fresh_delivery_clone_executes_changed_rule_through_facade(
    tmp_path: Path,
) -> None:
    remote = tmp_path / "remote.git"
    baseline = tmp_path / "baseline"
    establish_seam_baseline(ROOT, ROOT / "fixtures/legacy-enrollment", remote, baseline)
    relative = Path("src/generated/java/brp/rules/generated/EnrollmentEligibilityDecision.java")
    release = tmp_path / "release"
    source = (baseline / relative).read_text(encoding="utf-8")
    assert "RuleSupport.compare(input.age(), 18) < 0" in source
    changed = source.replace(
        "RuleSupport.compare(input.age(), 18) < 0",
        "RuleSupport.compare(input.age(), 19) < 0",
    )
    target = release / relative
    target.parent.mkdir(parents=True)
    target.write_text(changed, encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (release / "release-manifest.json").write_text(
        json.dumps(
            {
                "releaseHash": "2" * 64,
                "outputs": [{"path": relative.as_posix(), "hash": digest}],
            }
        ),
        encoding="utf-8",
    )
    gate = transactional_delivery_gate(remote, "seam-baseline-v1", release, tmp_path / "gate")
    delivered = publish_delivery_branch(
        gate,
        "enrollment_eligibility",
        2,
        {"minimumAge": {"before": 18, "after": 19}},
    )
    main = prove_delivered_execution(remote, "main", tmp_path / "main-proof")
    branch = prove_delivered_execution(remote, delivered.branch, tmp_path / "branch-proof")
    assert "OUTCOME: ELIGIBLE" in main.output
    assert "OUTCOME: REJECTED(UNDER_AGE)" in branch.output
    assert "FACADE_CALLS: 1" in main.output
    assert "FACADE_CALLS: 1" in branch.output
    assert branch.commit == delivered.head_commit
    assert branch.manifest_hash == gate.manifest_hash
