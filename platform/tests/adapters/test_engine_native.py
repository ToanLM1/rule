from pathlib import Path

import pytest

from brp.adapters.dmn import BpmnDocumentError
from brp.adapters.engine_native import EngineNativeAdapter
from brp.ir.canonical import canonical_bytes

DRL = """package synthetic.rules

rule "under-age"
when
  Applicant(age < 18)
then
  result.setEligible(false);
  result.setReasonCode("미성년");
end

rule "over-age"
when
  Applicant(age > 65)
then
  result.setEligible(false);
  result.setReasonCode("연령 초과");
end

rule "default"
salience -1000
when
  Applicant()
then
  result.setEligible(true);
  result.setReasonCode("가입 가능");
end
"""


def extract(path: Path):
    source_adapter = EngineNativeAdapter([path], asset_revision="git:engine-123")
    return source_adapter.extract(source_adapter.discover(None)[0])


def test_imports_restricted_drl_with_default_korean_and_rule_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / "가입규칙.drl"
    path.write_text(DRL, encoding="utf-8")
    first = extract(path)
    second = extract(path)
    assert not first.unmappable
    content = first.decisions[0].content
    assert canonical_bytes(content) == canonical_bytes(second.decisions[0].content)
    assert content.default_output == {"eligible": True, "reasonCode": "가입 가능"}
    assert [rule.then[1].value for rule in content.rules] == ["미성년", "연령 초과"]
    reference = content.rules[0].source_references[0]
    assert reference.type == "ENGINE_ASSET"
    assert reference.engine_format == "DRL"
    assert reference.asset_id == "가입규칙.drl"
    assert reference.revision == "git:engine-123"
    assert reference.rule_id == "under-age"
    assert reference.line_start == 3
    assert reference.content_hash == first.source_snapshot.content_hash


def test_unsupported_consequence_routes_rule_to_review(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.drl"
    unsafe = DRL.replace(
        'result.setReasonCode("연령 초과");',
        "result.setReasonCode(externalService.reason());",
    )
    path.write_text(unsafe, encoding="utf-8")
    batch = extract(path)
    assert batch.decisions
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_DRL_LITERAL"
    assert batch.unmappable[0].provenance["ruleId"] == "over-age"
    assert "externalService" in batch.unmappable[0].raw_fragment


def test_missing_default_prevents_partial_decision(tmp_path: Path) -> None:
    path = tmp_path / "no-default.drl"
    path.write_text(DRL[: DRL.index('rule "default"')], encoding="utf-8")
    batch = extract(path)
    assert not batch.decisions
    assert batch.unmappable[-1].reason_code == "DRL_DEFAULT_REQUIRED"


def test_odm_is_classified_for_customer_mapping_not_guessed(tmp_path: Path) -> None:
    path = tmp_path / "rules.odm"
    path.write_text(
        '<ruleProject vendor="IBM"><name>가입 정책</name></ruleProject>', encoding="utf-8"
    )
    batch = extract(path)
    assert not batch.decisions
    assert batch.unmappable[0].reason_code == "ODM_FORMAT_REQUIRES_CUSTOMER_MAPPING"
    assert batch.unmappable[0].provenance["engineFormat"] == "ODM"
    assert "가입 정책" in batch.unmappable[0].raw_fragment


def test_bpmn_workflow_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "workflow.bpmn"
    path.write_text(
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
        encoding="utf-8",
    )
    with pytest.raises(BpmnDocumentError, match="workflow assets"):
        extract(path)
