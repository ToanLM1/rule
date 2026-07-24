import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from brp.evidence import EvidenceBundle, RepositoryEvidenceTools, RepositoryToolError


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    source = root / "src" / "main" / "java" / "sample" / "Policy.java"
    test = root / "src" / "test" / "java" / "sample" / "PolicyTest.java"
    source.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    source.write_text(
        "package sample;\npublic class Policy {\n  boolean eligible(int age) {\n"
        "    return age >= 18;\n  }\n}\n",
        encoding="utf-8",
    )
    test.write_text(
        "package sample;\nclass PolicyTest { /* age 17 is rejected */ }\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return root


def test_inventory_search_read_and_history_are_bounded(tmp_path: Path) -> None:
    tools = RepositoryEvidenceTools(repository(tmp_path))
    assert len(tools.commit()) == 40
    assert tools.inventory(suffixes=(".java",)) == [
        "src/main/java/sample/Policy.java",
        "src/test/java/sample/PolicyTest.java",
    ]
    match = tools.search("eligible", limit=1)[0]
    assert match["file"] == "src/main/java/sample/Policy.java"
    span = tools.read(str(match["file"]), line_start=2, line_end=4)
    assert span["lineStart"] == 2
    assert span["lineEnd"] == 4
    assert len(span["contentHash"]) == 64
    assert tools.git_history(str(match["file"]))[0]["subject"] == "fixture"


@pytest.mark.parametrize("path", ["../secret.txt", "C:/Windows/win.ini", "/etc/passwd"])
def test_read_rejects_paths_outside_the_repository(tmp_path: Path, path: str) -> None:
    tools = RepositoryEvidenceTools(repository(tmp_path))
    with pytest.raises(RepositoryToolError, match="unsafe|escapes"):
        tools.read(path)


def test_read_rejects_oversized_and_binary_files(tmp_path: Path) -> None:
    root = repository(tmp_path)
    oversized = root / "large.java"
    oversized.write_text("x" * 100, encoding="utf-8")
    binary = root / "binary.java"
    binary.write_bytes(b"\xff\xfe")
    tools = RepositoryEvidenceTools(root, max_file_bytes=50)
    with pytest.raises(RepositoryToolError, match="byte limit"):
        tools.read("large.java")
    tools = RepositoryEvidenceTools(root)
    with pytest.raises(RepositoryToolError, match="UTF-8"):
        tools.read("binary.java")


def test_evidence_bundle_requires_real_span_references(tmp_path: Path) -> None:
    commit = RepositoryEvidenceTools(repository(tmp_path)).commit()
    with pytest.raises(ValidationError, match="unknown spans"):
        EvidenceBundle.model_validate(
            {
                "bundleId": "bundle_one",
                "repository": {
                    "repositoryUrl": "https://github.com/example/rules",
                    "commit": commit,
                },
                "hypothesis": "Age controls eligibility",
                "fieldEvidence": [
                    {
                        "fieldPath": "decisions[0].rows[0].conditions[0]",
                        "spanIds": ["missing"],
                        "confidence": 0.8,
                        "explanation": "Guard expression",
                    }
                ],
                "escalation": {"tier": "HUMAN", "reason": "Missing supporting span"},
            }
        )


def test_subprocess_timeout_is_bounded_and_redacts_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = RepositoryEvidenceTools(repository(tmp_path), timeout_seconds=1)
    sensitive_pattern = "customer-secret-rule"

    def time_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        command = args[0]
        raise subprocess.TimeoutExpired(command, 1, output=b"partial", stderr=b"credential")

    monkeypatch.setattr(subprocess, "run", time_out)
    with pytest.raises(RepositoryToolError) as caught:
        tools.search(sensitive_pattern)

    message = str(caught.value)
    assert message == "tool timed out: rg"
    assert sensitive_pattern not in message
    assert "credential" not in message


def test_subprocess_failure_does_not_expose_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = RepositoryEvidenceTools(repository(tmp_path))

    def fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args[0], 2, stdout=b"", stderr=b"secret stderr")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(RepositoryToolError) as caught:
        tools.commit()

    assert str(caught.value) == "tool failed: git (exit 2)"
    assert "secret stderr" not in str(caught.value)
