from pathlib import Path

from brp.adapters.ui_validation import HtmlValidationAdapter
from brp.ir.canonical import canonical_bytes

HTML = """<!doctype html>
<html><body>
<form id="가입-검증" aria-label="가입 검증">
  <input id="age" name="age" type="number" data-rule-type="integer"
         min="18" max="65" data-error-min="미성년" data-error-max="연령 초과">
  <input id="product" name="productCode" data-rule-in="암보험,저축보험"
         data-error-in="상품 미지원">
  <input id="channel" name="channel" data-rule-eq="ONLINE" data-error-eq="온라인 전용">
  <input id="unsafe" name="memo" required pattern=".*" oninput="steal()">
  <script>globalThis.__must_not_run = true;</script>
</form>
</body></html>
"""


def extract(path: Path):
    source_adapter = HtmlValidationAdapter([path], asset_revision="git:ui-abc")
    return source_adapter.extract(source_adapter.discover(None)[0])


def test_maps_static_validations_with_korean_and_element_provenance(tmp_path: Path) -> None:
    path = tmp_path / "가입.html"
    path.write_text(HTML, encoding="utf-8")
    first = extract(path)
    second = extract(path)

    content = first.decisions[0].content
    assert canonical_bytes(content) == canonical_bytes(second.decisions[0].content)
    assert first.source_snapshot.content_hash == second.source_snapshot.content_hash
    assert content.decision_name == "가입 검증"
    assert content.default_output == {"valid": True, "reasonCode": ""}
    assert [rule.then[1].value for rule in content.rules] == [
        "미성년",
        "연령 초과",
        "상품 미지원",
        "온라인 전용",
    ]
    assert [rule.when.all[0].operator for rule in content.rules] == [
        "LT",
        "GT",
        "NOT_IN",
        "NE",
    ]
    reference = content.rules[0].source_references[0]
    assert reference.type == "UI_ELEMENT"
    assert reference.file == "가입.html"
    assert reference.element_id == "age"
    assert reference.line == 4
    assert reference.revision == first.source_snapshot.content_hash


def test_scripts_framework_and_native_unsupported_rules_reach_review(tmp_path: Path) -> None:
    path = tmp_path / "validation.html"
    path.write_text(HTML, encoding="utf-8")
    batch = extract(path)
    reasons = [item.reason_code for item in batch.unmappable]
    assert reasons.count("UNSUPPORTED_UI_VALIDATION") == 3
    assert "UNSUPPORTED_UI_SCRIPT" in reasons
    assert "steal()" in next(
        item.raw_fragment
        for item in batch.unmappable
        if item.provenance["elementId"] == "unsafe@oninput"
    )


def test_invalid_literals_and_empty_documents_fail_closed_to_review(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.html"
    invalid.write_text(
        '<form id="x"><input id="age" name="age" data-rule-type="integer" min="x"></form>',
        encoding="utf-8",
    )
    batch = extract(invalid)
    assert not batch.decisions
    assert batch.unmappable[0].reason_code == "INVALID_UI_VALIDATION_LITERAL"

    empty = tmp_path / "empty.html"
    empty.write_text("<form id='empty'></form>", encoding="utf-8")
    empty_batch = extract(empty)
    assert not empty_batch.decisions
    assert empty_batch.unmappable[0].reason_code == "NO_UI_VALIDATIONS"


def test_adapter_never_executes_script_content(tmp_path: Path) -> None:
    marker = tmp_path / "executed.txt"
    path = tmp_path / "script.html"
    path.write_text(
        f'<script>require("fs").writeFileSync("{marker}", "bad")</script>',
        encoding="utf-8",
    )
    batch = extract(path)
    assert not marker.exists()
    assert batch.unmappable[0].reason_code == "UNSUPPORTED_UI_SCRIPT"
