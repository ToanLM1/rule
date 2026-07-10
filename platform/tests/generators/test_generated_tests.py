import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from brp.config.models import load_site_profile
from brp.generators.contracts import GoldenReleaseEvidence, ReleaseEnvelope, ReleaseInput
from brp.generators.java_release import render_golden_junit, render_manifest
from brp.ir.canonical import canonical_bytes
from brp.ir.models import DecisionContent

ROOT = Path(__file__).resolve().parents[3]
TOOLCHAIN = ROOT / "java-toolchain"


def release(expected: int = 20, suite_hash: str = "b" * 64) -> ReleaseInput:
    content = DecisionContent.model_validate_json(
        (ROOT / "platform/tests/fixtures/conformance/premium_adjustments.json").read_text(
            encoding="utf-8"
        )
    )
    target = load_site_profile(ROOT / "config/sites/fixture.yaml").target
    assert target is not None
    return ReleaseInput(
        content=content,
        envelope=ReleaseEnvelope(
            decision_key=content.decision_id,
            revision=1,
            content_hash=hashlib.sha256(canonical_bytes(content)).hexdigest(),
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        ),
        golden_suite=GoldenReleaseEvidence(
            revision=1,
            content_hash=suite_hash,
            cases=[
                {
                    "caseKey": "smoker",
                    "input": {"age": 30, "productCode": "CANCER_BASIC", "smoker": True},
                    "expected": [{"premiumLoadingPct": expected}],
                }
            ],
        ),
        site="fixture",
        target=target,
        site_config_hash="c" * 64,
        generator="java-source",
        generator_version="1.0.0",
    )


def test_junit_compiles_runs_and_detects_planted_failure(tmp_path: Path) -> None:
    java_home = Path(
        os.environ.get("JAVA_HOME", r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot")
    )
    environment = {
        **os.environ,
        "JAVA_HOME": str(java_home),
        "PATH": f"{java_home / 'bin'}{os.pathsep}{os.environ['PATH']}",
    }
    gradle = TOOLCHAIN / ("gradlew.bat" if os.name == "nt" else "gradlew")
    subprocess.run(
        [str(gradle), ":codegen-cli:installDist", "--no-daemon"],
        cwd=TOOLCHAIN,
        env=environment,
        check=True,
    )
    launcher = (
        TOOLCHAIN
        / "codegen-cli/build/install/codegen-cli/bin"
        / ("codegen-cli.bat" if os.name == "nt" else "codegen-cli")
    )
    module = tmp_path / "generated"
    module.mkdir()
    current = release()
    release_file = tmp_path / "release.json"
    release_file.write_bytes(current.canonical_bytes())
    subprocess.run(
        [str(launcher), str(release_file), str(module / "src/generated/java")],
        env=environment,
        check=True,
    )
    junit = render_golden_junit(current)
    test_path = module / junit.path
    test_path.parent.mkdir(parents=True)
    test_path.write_text(junit.content, encoding="utf-8")
    _gradle_project(tmp_path)
    success = subprocess.run(
        [str(gradle), "-p", str(tmp_path), ":generated:test", "--no-daemon"], env=environment
    )
    assert success.returncode == 0
    test_path.write_text(render_golden_junit(release(expected=999)).content, encoding="utf-8")
    failure = subprocess.run(
        [str(gradle), "-p", str(tmp_path), ":generated:test", "--no-daemon", "--rerun-tasks"],
        env=environment,
    )
    assert failure.returncode != 0


def test_manifest_changes_with_suite_evidence() -> None:
    first = render_manifest(release(), [])
    second = render_manifest(release(suite_hash="d" * 64), [])
    assert first.content_hash != second.content_hash
    assert json.loads(first.content)["goldenSuite"]["contentHash"] == "b" * 64


def _gradle_project(root: Path) -> None:
    runtime = (TOOLCHAIN / "brp-rules-runtime").as_posix()
    (root / "settings.gradle.kts").write_text(
        'rootProject.name="generated-test"\n'
        'include("brp-rules-runtime", "generated")\n'
        f'project(":brp-rules-runtime").projectDir=file("{runtime}")\n',
        encoding="utf-8",
    )
    (root / "build.gradle.kts").write_text(
        "allprojects { repositories { mavenCentral() } }\n", encoding="utf-8"
    )
    (root / "generated/build.gradle.kts").write_text(
        "plugins { java }\n"
        "dependencies {\n"
        ' implementation(project(":brp-rules-runtime"))\n'
        ' testImplementation(platform("org.junit:junit-bom:5.10.3"))\n'
        ' testImplementation("org.junit.jupiter:junit-jupiter")\n'
        ' testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine")\n'
        ' testRuntimeOnly("org.junit.platform:junit-platform-launcher")\n'
        "}\n"
        "sourceSets {\n"
        ' main { java.srcDir("src/generated/java") }\n'
        ' test { java.srcDir("src/generatedTest/java") }\n'
        "}\n"
        "tasks.test { useJUnitPlatform() }\n",
        encoding="utf-8",
    )
