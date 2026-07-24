from datetime import UTC, datetime

from brp.canonical_package import CanonicalDecisionPackage, compile_package
from brp.ir.canonical import canonical_bytes


def package_document() -> dict[str, object]:
    return {
        "packageId": "eligibility_package",
        "packageName": "가입 자격 관리",
        "profile": "CANONICAL_DECISION_PACKAGE_V1",
        "schemaVersion": 1,
        "product": "BASIC",
        "programContexts": [
            {
                "programId": "ENROLLMENT_API",
                "kind": "API",
                "entryPoint": "example.EligibilityFacade#evaluate",
            }
        ],
        "vocabulary": [
            {
                "key": "age",
                "label": "가입 나이",
                "type": "integer",
                "role": "INPUT",
                "sourcePath": "customer.age",
            },
            {"key": "eligible", "label": "가입 가능", "type": "boolean", "role": "OUTPUT"},
            {"key": "reason", "label": "판정 사유", "type": "string", "role": "OUTPUT"},
        ],
        "decisions": [
            {
                "decisionId": "eligibility",
                "name": "가입 자격",
                "hitPolicy": "FIRST",
                "inputFields": ["age"],
                "outputFields": ["eligible", "reason"],
                "defaultOutcome": {"eligible": True, "reason": "ELIGIBLE"},
                "rows": [
                    {
                        "rowId": "UNDER_AGE",
                        "conditions": [{"field": "age", "operator": "LT", "value": 18}],
                        "outcomes": {"eligible": False, "reason": "UNDER_AGE"},
                        "evidenceIds": ["source_age"],
                        "confidence": 0.9,
                    }
                ],
            }
        ],
        "businessScenarios": [
            {
                "scenarioId": "minor_rejected",
                "name": "미성년자 거절",
                "inputs": {"age": 17},
                "expected": {"eligible": False, "reason": "UNDER_AGE"},
                "evidenceIds": ["source_age"],
            }
        ],
        "evidence": [
            {
                "evidenceId": "source_age",
                "summary": "Age guard in the target facade",
                "sourceReference": {
                    "type": "JAVA_SOURCE",
                    "repository": "dummy-rules",
                    "revision": "a" * 40,
                    "file": "src/main/java/example/EligibilityFacade.java",
                    "lineStart": 20,
                    "lineEnd": 22,
                    "symbol": "evaluate",
                },
            }
        ],
        "targetBinding": {
            "repositoryAlias": "dummy-rules",
            "baseBranch": "main",
            "javaPackage": "example.generated",
            "generatedPath": "src/main/java/example/generated",
            "testPath": "src/test/java/example/generated",
            "facade": "example.EligibilityFacade",
            "buildCommands": [["gradlew.bat", "test"]],
        },
    }


def compile_document(document: dict[str, object]):
    package = CanonicalDecisionPackage.model_validate(document)
    return compile_package(
        package,
        actor="business-author",
        authored_at=datetime(2026, 7, 23, tzinfo=UTC),
        reason="Business policy update",
    )


def test_compiles_business_package_to_deterministic_rule_ir() -> None:
    first = compile_document(package_document())
    second = compile_document(package_document())
    assert first.valid is True
    assert first.diagnostics == []
    assert len(first.decisions) == 1
    decision = first.decisions[0]
    assert decision.decision_name == "가입 자격"
    assert decision.rules[0].source_references[0].type == "JAVA_SOURCE"
    assert canonical_bytes(decision) == canonical_bytes(second.decisions[0])


def test_user_authored_row_gets_a_user_action_reference() -> None:
    document = package_document()
    row = document["decisions"][0]["rows"][0]  # type: ignore[index]
    row.pop("evidenceIds")
    row.pop("confidence")
    result = compile_document(document)
    assert result.valid is True
    reference = result.decisions[0].rules[0].source_references[0]
    assert reference.type == "USER_ACTION"


def test_invalid_field_returns_cell_addressed_diagnostic_and_no_partial_ir() -> None:
    document = package_document()
    document["decisions"][0]["rows"][0]["conditions"][0]["field"] = "unknown"  # type: ignore[index]
    result = compile_document(document)
    assert result.valid is False
    assert result.decisions == []
    assert result.diagnostics[0].path == "decisions[0].rows[0].conditions[0].field"
    assert result.diagnostics[0].code == "UNKNOWN_INPUT"


def test_ir_type_error_is_returned_as_a_package_diagnostic() -> None:
    document = package_document()
    document["decisions"][0]["rows"][0]["conditions"][0]["value"] = "eighteen"  # type: ignore[index]
    result = compile_document(document)
    assert result.valid is False
    assert result.decisions == []
    assert any(item.code == "IR_VALIDATION" for item in result.diagnostics)
