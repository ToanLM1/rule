from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def load_workflow() -> dict[str, object]:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_workflow_has_every_phase_zero_job() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert set(jobs) == {"platform", "connector", "java-toolchain", "fixture", "ui"}


def test_workflow_never_contacts_shared_aws() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").lower()
    assert "amazonaws.com" not in text
    assert "13.251.6.169" not in text


def test_external_actions_are_major_version_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    action_lines = [line.strip() for line in text.splitlines() if "uses:" in line]
    assert action_lines
    assert all("@v" in line and line.rsplit("@v", 1)[1].isdigit() for line in action_lines)
