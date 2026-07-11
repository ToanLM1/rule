import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from brp.adapters.dmn import DmnDecisionTableAdapter
from brp.generators.dmn_export import (
    BRP_NS,
    DmnExportError,
    dmn_semantic_bytes,
    export_dmn,
)
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


def reference() -> JavaSourceReference:
    return JavaSourceReference(
        type="JAVA_SOURCE",
        repository="synthetic",
        revision="abc123",
        file="Eligibility.java",
        line_start=10,
        line_end=20,
    )


def content() -> DecisionContent:
    return DecisionContent(
        decision_id="eligibility",
        decision_name="가입 자격 <검증>",
        profile="RULE_IR_V1",
        schema_version=1,
        program_contexts=[
            ProgramContext(
                program_id="ENROLLMENT",
                kind=ProgramKind.API,
                entry_point="Eligibility#evaluate",
            )
        ],
        hit_policy=HitPolicy.FIRST,
        inputs=[
            InputDefinition(name="age", source_path="applicant.age", type=ScalarType.INTEGER),
            InputDefinition(
                name="productCode",
                source_path="applicant.productCode",
                type=ScalarType.STRING,
            ),
        ],
        outputs=[
            OutputDefinition(name="eligible", type=ScalarType.BOOLEAN),
            OutputDefinition(name="reasonCode", type=ScalarType.STRING),
        ],
        default_output={"eligible": True, "reasonCode": "가입 가능"},
        rules=[
            Rule(
                rule_id="R001",
                when=ConditionGroup(
                    all=[
                        Condition(
                            left=InputOperand(kind="INPUT", name="age"),
                            operator=Operator.LT,
                            right=LiteralOperand(kind="LITERAL", value=18),
                        )
                    ]
                ),
                then=[
                    Action(output="eligible", value=False),
                    Action(output="reasonCode", value="미성년 & 확인"),
                ],
                origin=RuleOrigin.EXTRACTED,
                source_references=[reference()],
                confidence=1.0,
            ),
            Rule(
                rule_id="R002",
                when=ConditionGroup(
                    all=[
                        Condition(
                            left=InputOperand(kind="INPUT", name="productCode"),
                            operator=Operator.IN,
                            right=LiteralOperand(kind="LITERAL", value=["암보험", "저축보험"]),
                        )
                    ]
                ),
                then=[
                    Action(output="eligible", value=True),
                    Action(output="reasonCode", value="상품 허용"),
                ],
                origin=RuleOrigin.EXTRACTED,
                source_references=[reference()],
                confidence=1.0,
            ),
        ],
    )


def test_export_is_byte_stable_safe_and_contains_only_content_metadata() -> None:
    first = export_dmn(content())
    second = export_dmn(content())
    assert first == second
    text = first.content.decode("utf-8")
    assert "가입 자격 &lt;검증&gt;" in text
    assert "미성년 &amp; 확인" in text
    assert "lifecycleStatus" not in text
    assert "approvedBy" not in text
    root = ET.fromstring(first.content)
    hashes = root.findall(f".//{{{BRP_NS}}}canonicalContentHash")
    references = root.findall(f".//{{{BRP_NS}}}sourceReferences")
    assert hashes[0].text == first.decision_content_hash
    assert "Eligibility.java" in (references[0].text or "")


def test_export_reimports_to_identical_canonical_behavior(tmp_path: Path) -> None:
    path = tmp_path / "round-trip.dmn"
    path.write_bytes(export_dmn(content()).content)
    source_adapter = DmnDecisionTableAdapter([path], revision="export:sha256")
    batch = source_adapter.extract(source_adapter.discover(None)[0])
    assert not batch.unmappable
    imported = batch.decisions[0].content
    assert dmn_semantic_bytes(imported) == dmn_semantic_bytes(content())


def test_non_representable_lookup_nested_any_and_operator_are_rejected() -> None:
    starts_with = content().model_copy(deep=True)
    condition = starts_with.rules[0].when.all[0]
    assert isinstance(condition, Condition)
    condition.operator = Operator.STARTS_WITH
    condition.right = LiteralOperand(kind="LITERAL", value="1")
    with pytest.raises(DmnExportError, match="STARTS_WITH"):
        export_dmn(starts_with)

    any_group = content().model_copy(deep=True)
    original = any_group.rules[0].when.all[0]
    any_group.rules[0].when = ConditionGroup(any=[original])
    with pytest.raises(DmnExportError, match="flat all-condition"):
        export_dmn(any_group)


def test_collect_round_trip_has_no_synthetic_default(tmp_path: Path) -> None:
    collect = content().model_copy(deep=True)
    collect.hit_policy = HitPolicy.COLLECT
    collect.default_output = None
    path = tmp_path / "collect.dmn"
    path.write_bytes(export_dmn(collect).content)
    source_adapter = DmnDecisionTableAdapter([path], revision="export:collect")
    imported = source_adapter.extract(source_adapter.discover(None)[0]).decisions[0].content
    assert imported.hit_policy == "COLLECT"
    assert imported.default_output is None
    assert dmn_semantic_bytes(imported) == dmn_semantic_bytes(collect)
