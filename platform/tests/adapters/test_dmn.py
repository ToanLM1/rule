# ruff: noqa: E501 -- keeping complete DMN XML elements readable in the fixture

from pathlib import Path

import pytest

from brp.adapters.dmn import BpmnDocumentError, DmnDecisionTableAdapter
from brp.ir.canonical import canonical_bytes

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"


def write_dmn(path: Path, *, hit_policy: str = "FIRST", unsupported: bool = False) -> None:
    condition = "if age > 10 then 1 else 0" if unsupported else "&lt; 18"
    path.write_text(
        f'''<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="{DMN_NS}" id="defs" name="가입 규칙">
  <decision id="eligibility" name="가입 자격">
    <decisionTable id="table-eligibility" hitPolicy="{hit_policy}">
      <input id="input-age" label="age"><inputExpression id="expr-age" typeRef="integer"><text>applicant.age</text></inputExpression></input>
      <input id="input-product" label="productCode"><inputExpression id="expr-product" typeRef="string"><text>applicant.productCode</text></inputExpression></input>
      <output id="output-eligible" name="eligible" typeRef="boolean"/>
      <output id="output-reason" name="reasonCode" typeRef="string"/>
      <rule id="rule-under-age"><inputEntry id="age-under"><text>{condition}</text></inputEntry><inputEntry id="product-any"><text>-</text></inputEntry><outputEntry id="out-false"><text>false</text></outputEntry><outputEntry id="out-korean"><text>"미성년"</text></outputEntry></rule>
      <rule id="rule-products"><inputEntry id="age-any"><text>-</text></inputEntry><inputEntry id="product-list"><text>"암보험","저축보험"</text></inputEntry><outputEntry id="out-true"><text>true</text></outputEntry><outputEntry id="out-product"><text>"상품 허용"</text></outputEntry></rule>
      <rule id="rule-default"><inputEntry id="default-age"><text>-</text></inputEntry><inputEntry id="default-product"><text>-</text></inputEntry><outputEntry id="default-true"><text>true</text></outputEntry><outputEntry id="default-reason"><text>"가입 가능"</text></outputEntry></rule>
    </decisionTable>
  </decision>
</definitions>''',
        encoding="utf-8",
    )


@pytest.mark.parametrize("hit_policy", ["FIRST", "UNIQUE"])
def test_imports_restricted_table_with_korean_and_exact_provenance(
    tmp_path: Path, hit_policy: str
) -> None:
    path = tmp_path / "가입규칙.dmn"
    write_dmn(path, hit_policy=hit_policy)
    adapter = DmnDecisionTableAdapter([path], revision="git:abc123")
    batch = adapter.extract(adapter.discover(None)[0])
    assert not batch.unmappable
    content = batch.decisions[0].content
    assert content.hit_policy == hit_policy
    assert content.default_output == {"eligible": True, "reasonCode": "가입 가능"}
    assert content.rules[0].source_references[0].element_id == "rule-under-age"
    assert content.rules[0].source_references[0].revision == "git:abc123"
    assert "미성년" in canonical_bytes(content).decode("utf-8")
    assert content.rules[1].when.all[0].operator == "IN"


def test_collect_keeps_wildcard_as_exists_rule(tmp_path: Path) -> None:
    path = tmp_path / "collect.dmn"
    write_dmn(path, hit_policy="COLLECT")
    batch = DmnDecisionTableAdapter([path], revision="asset-v1").extract(
        DmnDecisionTableAdapter([path], revision="asset-v1").discover(None)[0]
    )
    content = batch.decisions[0].content
    assert content.hit_policy == "COLLECT"
    assert content.default_output is None
    assert content.rules[-1].when.all[0].operator == "EXISTS"


def test_unsupported_feel_reaches_review_with_element_location(tmp_path: Path) -> None:
    path = tmp_path / "unsupported.dmn"
    write_dmn(path, unsupported=True)
    adapter = DmnDecisionTableAdapter([path], revision="asset-v2")
    batch = adapter.extract(adapter.discover(None)[0])
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_FEEL"
    assert batch.unmappable[0].provenance["elementId"] == "rule-under-age"
    assert batch.decisions[0].content.rules[0].rule_id == "rule_products"


def test_bpmn_is_rejected_not_coerced(tmp_path: Path) -> None:
    path = tmp_path / "workflow.bpmn"
    path.write_text(
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p"/></definitions>',
        encoding="utf-8",
    )
    adapter = DmnDecisionTableAdapter([path], revision="asset-v1")
    with pytest.raises(BpmnDocumentError, match="workflow orchestration"):
        adapter.extract(adapter.discover(None)[0])
