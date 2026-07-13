import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from brp.config.models import (
    Aggregate,
    CompositionConfig,
    CompositionDecision,
    Language,
    TargetConfig,
)
from brp.generators.contracts import (
    GoldenReleaseEvidence,
    LookupReleaseSnapshot,
    ReleaseEnvelope,
    ReleaseInput,
)
from brp.generators.csharp import CSharpGenerator, verify_csharp_compile
from brp.ir.canonical import canonical_bytes
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DecisionContent,
    HitPolicy,
    InputDefinition,
    InputOperand,
    JavaSourceReference,
    LiteralOperand,
    Operator,
    OutputDefinition,
    ProgramContext,
    ProgramKind,
    Rule,
    RuleOrigin,
    ScalarType,
)

ROOT = Path(__file__).resolve().parents[3]


def target() -> TargetConfig:
    return TargetConfig(
        language=Language.CSHARP,
        repository="fixtures/csharp-target",
        base_branch="main",
        generated_source_path="src/Generated",
        generated_test_path="tests/Generated",
        csharp_namespace="Brp.Generated.Rules",
        build_command="dotnet test",
        pr_provider="local",
        composition=CompositionConfig(
            facade="Brp.Generated.RuleFacade",
            decisions={
                "enrollment_eligibility": CompositionDecision(
                    field="eligible", aggregate=Aggregate.FIRST_NON_NULL
                )
            },
        ),
    )


def enrollment() -> DecisionContent:
    return DecisionContent.model_validate_json(
        (ROOT / "platform/tests/fixtures/conformance/enrollment_eligibility.json").read_text(
            encoding="utf-8"
        )
    )


def release(content: DecisionContent, *, expected: object) -> ReleaseInput:
    content_hash = hashlib.sha256(canonical_bytes(content)).hexdigest()
    return ReleaseInput(
        content=content,
        envelope=ReleaseEnvelope(
            decision_key=content.decision_id,
            revision=1,
            content_hash=content_hash,
            effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        ),
        golden_suite=GoldenReleaseEvidence(
            revision=1,
            content_hash="b" * 64,
            cases=[
                {
                    "caseKey": "synthetic",
                    "input": {
                        item.name: {
                            ScalarType.STRING: "CANCER_BASIC",
                            ScalarType.INTEGER: 17,
                            ScalarType.DECIMAL: 1.25,
                            ScalarType.BOOLEAN: True,
                            ScalarType.DATE: "2026-08-01",
                        }[item.type]
                        for item in content.inputs
                    },
                    "expected": expected,
                }
            ],
        ),
        lookup_snapshots=[
            LookupReleaseSnapshot(
                snapshot_id="region-v1",
                content_hash="c" * 64,
                name="regionEligibility",
                rows=[{"region_code": "CANCER_BASIC", "eligible": True}],
            )
        ]
        if content.lookups
        else [],
        site="synthetic-csharp",
        target=target(),
        site_config_hash="d" * 64,
        generator="csharp-source",
        generator_version="1.0.0",
    )


def test_csharp_release_is_deterministic_hashed_and_has_lookup_and_golden_contracts() -> None:
    current = release(enrollment(), expected={"eligible": False, "reasonCode": "UNDER_AGE"})
    generator = CSharpGenerator()
    first = generator.generate(current)
    second = generator.generate(current)
    assert [(item.path, item.content_hash) for item in first] == [
        (item.path, item.content_hash) for item in second
    ]
    source, golden, manifest = first
    assert "public interface ILookupProvider" in source.content
    assert "lookup://region_eligibility" in source.content
    assert "미성년" not in source.content
    assert "GoldenLookups" in golden.content
    assert "Assert.Equal(false, actual.Eligible);" in golden.content
    document = json.loads(manifest.content)
    assert document["generator"] == {"name": "csharp-source", "version": "1.0.0"}
    assert document["outputs"] == sorted(
        [
            {"path": source.path, "hash": source.content_hash},
            {"path": golden.path, "hash": golden.content_hash},
        ],
        key=lambda item: item["path"],
    )


def operator_content() -> DecisionContent:
    input_types = {
        "s": ScalarType.STRING,
        "i": ScalarType.INTEGER,
        "d": ScalarType.DECIMAL,
        "b": ScalarType.BOOLEAN,
    }
    cases = [
        ("s", Operator.EQ, "A"),
        ("b", Operator.NE, True),
        ("i", Operator.GT, 1),
        ("d", Operator.GTE, 1.25),
        ("i", Operator.LT, 9),
        ("i", Operator.LTE, 10),
        ("i", Operator.IN, [1, 2]),
        ("s", Operator.NOT_IN, ["제주", "울릉"]),
        ("i", Operator.BETWEEN, [3, 7]),
        ("s", Operator.EXISTS, None),
        ("s", Operator.STARTS_WITH, "CANCER"),
    ]
    reference = JavaSourceReference(
        type="JAVA_SOURCE",
        repository="synthetic",
        revision="1",
        file="Operators.java",
        line_start=1,
        line_end=1,
    )
    rules = []
    for index, (field, operator, value) in enumerate(cases, 1):
        rules.append(
            Rule(
                rule_id=f"R{index:03d}",
                when=ConditionGroup(
                    all=[
                        Condition(
                            left=InputOperand(kind="INPUT", name=field),
                            operator=operator,
                            right=(
                                None
                                if operator is Operator.EXISTS
                                else LiteralOperand(kind="LITERAL", value=value)
                            ),
                        )
                    ]
                ),
                then=[Action(output="code", value=f"OP_{operator.value}")],
                origin=RuleOrigin.EXTRACTED,
                source_references=[reference],
                confidence=1.0,
            )
        )
    return DecisionContent(
        decision_id="operator_matrix",
        decision_name="연산자 행렬",
        profile="RULE_IR_V1",
        schema_version=1,
        program_contexts=[
            ProgramContext(
                program_id="CSHARP-PROOF",
                kind=ProgramKind.SERVICE,
                entry_point="Operators#evaluate",
            )
        ],
        hit_policy=HitPolicy.COLLECT,
        inputs=[InputDefinition(name=name, type=kind) for name, kind in input_types.items()],
        outputs=[OutputDefinition(name="code", type=ScalarType.STRING)],
        rules=rules,
    )


def test_all_ir_operators_and_hit_policies_render() -> None:
    collect_release = release(operator_content(), expected=[])
    source = CSharpGenerator().generate(collect_release)[0].content
    for fragment in [
        "Equals(",
        "!Equals(",
        " > ",
        " >= ",
        " < ",
        " <= ",
        ".Contains(",
        "!(new[]",
        " && ",
        " is not null",
        ".StartsWith(",
        "IReadOnlyList<Output>",
    ]:
        assert fragment in source

    unique = enrollment().model_copy(deep=True)
    unique.hit_policy = HitPolicy.UNIQUE
    unique_source = (
        CSharpGenerator()
        .generate(release(unique, expected={"eligible": False, "reasonCode": "UNDER_AGE"}))[0]
        .content
    )
    assert "matchCount > 1" in unique_source
    first_source = (
        CSharpGenerator()
        .generate(release(enrollment(), expected={"eligible": False, "reasonCode": "UNDER_AGE"}))[0]
        .content
    )
    assert 'return new Output(false, "UNDER_AGE")' in first_source


def test_compile_gate_is_explicit_and_never_claims_unrun_execution() -> None:
    source = CSharpGenerator().generate(
        release(enrollment(), expected={"eligible": False, "reasonCode": "UNDER_AGE"})
    )[0]
    evidence = verify_csharp_compile(source)
    assert evidence.source_hash == source.content_hash
    assert evidence.status in {"COMPILED", "COMPILE_NOT_RUN"}
    if evidence.status == "COMPILE_NOT_RUN":
        assert "not installed" in evidence.detail
