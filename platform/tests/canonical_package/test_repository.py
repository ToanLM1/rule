from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from brp.canonical_package import CanonicalDecisionPackage
from brp.canonical_package.repository import (
    CanonicalPackageRepository,
    package_semantic_diff,
)
from brp.repository.errors import SelfApprovalError
from brp.repository.models import CanonicalPackageRevision
from tests.canonical_package.test_compiler import package_document


def package() -> CanonicalDecisionPackage:
    return CanonicalDecisionPackage.model_validate(package_document())


def revision(document: CanonicalDecisionPackage) -> CanonicalPackageRevision:
    return CanonicalPackageRevision(
        id=uuid4(),
        package_id=uuid4(),
        revision=1,
        document=document.model_dump(mode="json", by_alias=True, exclude_none=True),
        compiled_decisions=[],
        content_hash="a" * 64,
        lifecycle_status="DRAFT",
        effective_from=datetime(2026, 7, 23, tzinfo=UTC),
        created_by="maker-a",
    )


def test_package_materialization_is_deterministic() -> None:
    first = CanonicalPackageRepository._materialize(
        package(),
        actor="maker-a",
        authored_at=datetime(2026, 7, 23, tzinfo=UTC),
        reason="Policy update",
    )
    second = CanonicalPackageRepository._materialize(
        package(),
        actor="maker-a",
        authored_at=datetime(2026, 7, 23, tzinfo=UTC),
        reason="Policy update",
    )
    assert first == second
    assert len(first[2]) == 64


def test_package_lifecycle_enforces_maker_checker() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    repository = CanonicalPackageRepository(session, site_id=uuid4())
    record = revision(package())

    repository.submit(record, "maker-a")
    assert record.lifecycle_status == "SUBMITTED"
    with pytest.raises(SelfApprovalError):
        repository.approve(record, "maker-a")

    repository.approve(record, "checker-b")
    assert record.lifecycle_status == "APPROVED"
    assert record.approved_by == "checker-b"
    assert session.flush.call_count == 2


def test_semantic_diff_reports_business_row_and_scenario_changes() -> None:
    before = package()
    document = package_document()
    document["decisions"][0]["rows"][0]["conditions"][0]["value"] = 21  # type: ignore[index]
    document["businessScenarios"][0]["inputs"]["age"] = 20  # type: ignore[index]
    after = CanonicalDecisionPackage.model_validate(document)

    result = package_semantic_diff(before, after)

    changed = result["decisions"]["changedRows"]
    assert changed[0]["decisionId"] == "eligibility"
    assert changed[0]["rowId"] == "UNDER_AGE"
    assert result["scenariosChanged"] is True
