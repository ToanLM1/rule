# ruff: noqa: E501
"""Local, testable Mode-B seam and delivery primitives."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml


def establish_seam_baseline(
    repository_root: Path,
    fixture_source: Path,
    remote: Path,
    workspace: Path,
) -> str:
    """Create the reviewed one-time façade seam and push/tag main."""
    if remote.exists() or workspace.exists():
        raise FileExistsError("seam baseline targets must not already exist")
    _run(["git", "init", "--bare", "--initial-branch=main", str(remote)])
    shutil.copytree(fixture_source, workspace)
    for transient in (workspace / "build", workspace / ".gradle"):
        if transient.exists():
            shutil.rmtree(transient)
    _run(["git", "init", "-b", "main"], cwd=workspace)
    _run(["git", "config", "user.name", "BRP Fixture"], cwd=workspace)
    _run(["git", "config", "user.email", "brp-fixture@local.invalid"], cwd=workspace)
    _install_generated_sources(repository_root, workspace)
    _apply_facade_seam(workspace)
    _run(_gradle(workspace, "test"), cwd=workspace)
    _run(["git", "add", "."], cwd=workspace)
    _run(["git", "commit", "-m", "feat: establish generated-rules facade seam"], cwd=workspace)
    _run(["git", "tag", "seam-baseline-v1"], cwd=workspace)
    _run(["git", "remote", "add", "origin", str(remote)], cwd=workspace)
    _run(["git", "push", "-u", "origin", "main", "--tags"], cwd=workspace)
    return _capture(["git", "rev-parse", "HEAD"], cwd=workspace)


@dataclass(frozen=True)
class GateResult:
    workspace: Path
    base_commit: str
    manifest_hash: str
    tests: tuple[str, ...]


def transactional_delivery_gate(
    remote: Path,
    baseline: str,
    generated_release: Path,
    workspace: Path,
) -> GateResult:
    """Validate manifest-listed files without creating a branch or commit."""
    if workspace.exists():
        raise FileExistsError(workspace)
    report = workspace.with_suffix(".failure.md")
    try:
        _run(["git", "clone", str(remote), str(workspace)])
        _run(["git", "checkout", "--detach", baseline], cwd=workspace)
        base_commit = _capture(["git", "rev-parse", "HEAD"], cwd=workspace)
        manifest_path = generated_release / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for output in manifest["outputs"]:
            relative = Path(output["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe manifest path: {relative}")
            source = generated_release / relative
            if not source.is_file():
                raise FileNotFoundError(f"manifest output is missing: {relative}")
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(manifest_path, workspace / "release-manifest.json")
        _run(_gradle(workspace, "test"), cwd=workspace)
        return GateResult(
            workspace=workspace,
            base_commit=base_commit,
            manifest_hash=_file_hash(manifest_path),
            tests=("generated-golden", "target-regression"),
        )
    except Exception as exc:
        report.write_text(
            "# Delivery gate failure\n\n"
            f"- baseline: `{baseline}`\n"
            f"- error: `{type(exc).__name__}: {exc}`\n"
            "- branch-created: `false`\n- commit-created: `false`\n",
            encoding="utf-8",
        )
        raise


def _install_generated_sources(root: Path, workspace: Path) -> None:
    toolchain = root / "java-toolchain"
    gradle = toolchain / ("gradlew.bat" if os.name == "nt" else "gradlew")
    _run([str(gradle), ":codegen-cli:installDist", "--no-daemon"], cwd=toolchain)
    launcher = (
        toolchain
        / "codegen-cli/build/install/codegen-cli/bin"
        / ("codegen-cli.bat" if os.name == "nt" else "codegen-cli")
    )
    generated = workspace / "src/generated/java"
    site = yaml.safe_load((root / "config/sites/fixture.yaml").read_text(encoding="utf-8"))
    fixtures = root / "platform/tests/fixtures/conformance"
    with tempfile.TemporaryDirectory(prefix="brp-seam-input-") as directory:
        for name in (
            "enrollment_eligibility",
            "premium_adjustments",
            "required_documents",
        ):
            content = json.loads((fixtures / f"{name}.json").read_text(encoding="utf-8"))
            release = {
                "content": content,
                "envelope": {"revision": 1, "contentHash": "initial"},
                "target": {"javaPackage": site["target"]["java_package"]},
            }
            path = Path(directory) / f"{name}.json"
            path.write_text(json.dumps(release, ensure_ascii=False), encoding="utf-8")
            _run([str(launcher), str(path), str(generated)])
    runtime_source = toolchain / "brp-rules-runtime/src/main/java/brp/runtime"
    shutil.copytree(runtime_source, generated / "brp/runtime")
    facade = generated / "legacy/rules/EnrollmentRuleModule.java"
    facade.parent.mkdir(parents=True, exist_ok=True)
    facade.write_text(LEGACY_FACADE, encoding="utf-8")


def _apply_facade_seam(workspace: Path) -> None:
    build = workspace / "build.gradle.kts"
    build.write_text(
        build.read_text(encoding="utf-8")
        + "\nsourceSets {\n"
        + '  main { java.srcDir("src/generated/java") }\n'
        + '  test { java.srcDir("src/generatedTest/java") }\n'
        + "}\n",
        encoding="utf-8",
    )
    validator = workspace / "src/main/java/legacy/EnrollmentValidator.java"
    source = validator.read_text(encoding="utf-8")
    pattern = re.compile(
        r"  public EnrollmentResult evaluate\(EnrollmentRequest request, Connection connection\)"
        r"\s+throws SQLException \{.*?\n  \}\n\n  private boolean isRegionCovered",
        re.DOTALL,
    )
    replacement = (
        "  public EnrollmentResult evaluate(EnrollmentRequest request, Connection connection)\n"
        "      throws SQLException {\n"
        "    return legacy.rules.EnrollmentRuleModule.evaluate(request, connection);\n"
        "  }\n\n  private boolean isRegionCovered"
    )
    transformed, count = pattern.subn(replacement, source)
    if count != 1:
        raise RuntimeError("fixture seam recipe did not match exactly once")
    validator.write_text(transformed, encoding="utf-8")


def _gradle(workspace: Path, task: str) -> list[str]:
    return [str(workspace / ("gradlew.bat" if os.name == "nt" else "gradlew")), task, "--no-daemon"]


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _capture(command: list[str], *, cwd: Path) -> str:
    return subprocess.run(
        command, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _file_hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


LEGACY_FACADE = r"""package legacy.rules;
import brp.rules.generated.EnrollmentEligibilityDecision;
import brp.rules.generated.PremiumAdjustmentsDecision;
import brp.rules.generated.RequiredDocumentsDecision;
import brp.runtime.Composition;
import brp.runtime.LookupProvider;
import java.sql.Connection;
import java.util.List;
import java.util.Map;
import legacy.model.EnrollmentRequest;
import legacy.model.EnrollmentResult;

public final class EnrollmentRuleModule {
  private static int invocations;
  public static int invocationCount() { return invocations; }
  public static void resetInvocationCount() { invocations = 0; }
  public static EnrollmentResult evaluate(EnrollmentRequest request, Connection connection) {
    invocations++;
    LookupProvider lookup = (name, keys) -> {
      try (var statement = connection.prepareStatement("SELECT eligible FROM region_eligibility WHERE region_code = ?")) {
        statement.setObject(1, keys.get("region_code"));
        try (var rows = statement.executeQuery()) {
          return rows.next() ? Map.of("eligible", rows.getBoolean("eligible")) : Map.of();
        }
      } catch (java.sql.SQLException exception) { throw new IllegalStateException(exception); }
    };
    var eligibility = EnrollmentEligibilityDecision.evaluate(new EnrollmentEligibilityDecision.Input(request.age(), request.productCode(), request.regionCode()), lookup);
    var result = new EnrollmentResult();
    if (!eligibility.eligible()) { result.reject(eligibility.reasonCode()); return result; }
    var premiums = PremiumAdjustmentsDecision.evaluate(new PremiumAdjustmentsDecision.Input(request.age(), request.productCode(), request.smoker()), lookup);
    for (var premium : premiums) result.addPremiumLoading(premium.premiumLoadingPct());
    var documents = RequiredDocumentsDecision.evaluate(new RequiredDocumentsDecision.Input(request.age(), request.productCode(), request.occupationClass()), lookup);
    for (String document : Composition.distinct(documents.stream().map(RequiredDocumentsDecision.Output::requiredDoc).toList())) result.addRequiredDoc(document);
    return result;
  }
}
"""
