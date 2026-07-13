"""Generate the three fixture decisions, compile a façade, and execute it."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / "java-toolchain"
FIXTURES = ROOT / "platform/tests/fixtures/conformance"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    gradle = TOOLCHAIN / ("gradlew.bat" if os.name == "nt" else "gradlew")
    run(
        [
            str(gradle),
            ":codegen-cli:installDist",
            ":brp-rules-runtime:classes",
            "--no-daemon",
        ],
        cwd=TOOLCHAIN,
    )
    launcher = (
        TOOLCHAIN
        / "codegen-cli/build/install/codegen-cli/bin"
        / ("codegen-cli.bat" if os.name == "nt" else "codegen-cli")
    )
    with tempfile.TemporaryDirectory(prefix="brp-generated-") as temporary:
        workspace = Path(temporary)
        sources = workspace / "src"
        site = yaml.safe_load(
            (ROOT / "config/sites/fixture.yaml").read_text(encoding="utf-8")
        )
        for name in (
            "enrollment_eligibility",
            "premium_adjustments",
            "required_documents",
        ):
            content = json.loads(
                (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
            )
            canonical = json.dumps(
                content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
            release = {
                "content": content,
                "envelope": {
                    "revision": 1,
                    "contentHash": hashlib.sha256(canonical).hexdigest(),
                },
                "target": {"javaPackage": site["target"]["java_package"]},
            }
            release_path = workspace / f"{name}.json"
            release_path.write_text(
                json.dumps(release, ensure_ascii=False), encoding="utf-8"
            )
            run([str(launcher), str(release_path), str(sources)])

        facade = sources / "brp/rules/generated/EnrollmentRuleModule.java"
        facade.parent.mkdir(parents=True, exist_ok=True)
        facade.write_text(FACADE, encoding="utf-8")
        harness = sources / "brp/rules/generated/FixtureHarness.java"
        harness.write_text(HARNESS, encoding="utf-8")
        classes = workspace / "classes"
        classes.mkdir()
        runtime = TOOLCHAIN / "brp-rules-runtime/build/classes/java/main"
        java_sources = sorted(str(path) for path in sources.rglob("*.java"))
        run(
            [
                "javac",
                "-encoding",
                "UTF-8",
                "-cp",
                str(runtime),
                "-d",
                str(classes),
                *java_sources,
            ]
        )
        run(
            [
                "java",
                "-cp",
                os.pathsep.join((str(classes), str(runtime))),
                "brp.rules.generated.FixtureHarness",
            ]
        )
    print(
        "Generated fixture compiled and executed: SUM, DISTINCT, FIRST_NON_NULL, Korean, lookup hit/miss"
    )
    return 0


FACADE = r"""package brp.rules.generated;
import brp.runtime.Composition;
import brp.runtime.LookupProvider;
import java.util.ArrayList;
import java.util.List;

public final class EnrollmentRuleModule {
  public record Result(boolean eligible, String reasonCode, int premiumLoadingPct, List<String> requiredDocs) {}
  public static Result evaluate(int age, String product, boolean smoker, String region, int occupation, LookupProvider lookup) {
    var eligibility = EnrollmentEligibilityDecision.evaluate(new EnrollmentEligibilityDecision.Input(age, product, region), lookup);
    var premiums = PremiumAdjustmentsDecision.evaluate(new PremiumAdjustmentsDecision.Input(age, product, smoker), lookup);
    var documents = RequiredDocumentsDecision.evaluate(new RequiredDocumentsDecision.Input(age, product, occupation), lookup);
    var values = premiums.stream().map(PremiumAdjustmentsDecision.Output::premiumLoadingPct).toList();
    var docs = documents.stream().map(RequiredDocumentsDecision.Output::requiredDoc).toList();
    return new Result(eligibility.eligible(), eligibility.reasonCode(), Composition.sum(values).intValue(), Composition.distinct(docs));
  }
}
"""

HARNESS = r"""package brp.rules.generated;
import brp.runtime.LookupProvider;
import java.util.Map;
public final class FixtureHarness {
  public static void main(String[] args) {
    LookupProvider lookup = (name, keys) -> Map.of("eligible", "SEOUL".equals(keys.get("region_code")));
    var result = EnrollmentRuleModule.evaluate(62, "CANCER_BASIC", true, "SEOUL", 4, lookup);
    if (!result.eligible() || result.premiumLoadingPct() != 50 || !result.requiredDocs().equals(java.util.List.of("DOC_HEALTH_CHECK"))) throw new AssertionError(result);
    var miss = EnrollmentRuleModule.evaluate(40, "CANCER_BASIC", false, "제주", 1, lookup);
    if (miss.eligible() || !"REGION_NOT_COVERED".equals(miss.reasonCode())) throw new AssertionError(miss);
  }
}
"""


if __name__ == "__main__":
    raise SystemExit(main())
