"""Golden-suite execution with explicit executor authority metadata."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from brp.governance.golden import GoldenRepository
from brp.governance.zen import DictLookupResolver, preview
from brp.ir.models import DecisionContent
from brp.repository.models import DecisionRevision, GoldenSuiteRevision


def run_zen_advisory(
    session: Session,
    decision_revision: DecisionRevision,
    suite_revision: GoldenSuiteRevision,
) -> dict[str, Any]:
    return _run_zen_suite(session, decision_revision, suite_revision, authority="ADVISORY")


def run_zen_mode_a(
    session: Session,
    decision_revision: DecisionRevision,
    suite_revision: GoldenSuiteRevision,
) -> dict[str, Any]:
    """Execute Zen as the configured Mode-A production authority."""
    return _run_zen_suite(session, decision_revision, suite_revision, authority="AUTHORITATIVE")


def _run_zen_suite(
    session: Session,
    decision_revision: DecisionRevision,
    suite_revision: GoldenSuiteRevision,
    *,
    authority: str,
) -> dict[str, Any]:
    golden = GoldenRepository(session)
    snapshots = golden.lookup_snapshots(suite_revision.lookup_snapshot_hashes)
    resolver = DictLookupResolver(
        {
            str(snapshot.source.get("ref") or f"lookup://{snapshot.name}"): snapshot.content
            for snapshot in snapshots
        }
    )
    content = DecisionContent.model_validate(decision_revision.content_blob.content)
    results: list[dict[str, Any]] = []
    for case in golden.cases(suite_revision):
        try:
            actual = preview(content, case.input, resolver)["result"]
            passed = actual == case.expected
            results.append(
                {
                    "caseKey": case.case_key,
                    "passed": passed,
                    "expected": case.expected,
                    "actual": actual,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "caseKey": case.case_key,
                    "passed": False,
                    "expected": case.expected,
                    "actual": None,
                    "error": type(exc).__name__,
                }
            )
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "executor": "ZEN",
        "authority": authority,
        "decisionRevision": decision_revision.revision,
        "suiteRevision": suite_revision.revision,
        "suiteHash": suite_revision.content_hash,
        "lookupSnapshots": suite_revision.lookup_snapshot_hashes,
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "cases": results,
    }
