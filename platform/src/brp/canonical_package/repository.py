"""Governed persistence and lifecycle for business-facing decision packages."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from brp.canonical_package.compiler import compile_package
from brp.canonical_package.models import CanonicalDecisionPackage
from brp.repository.errors import (
    EffectiveIntervalOverlapError,
    IllegalLifecycleTransitionError,
    SelfApprovalError,
    SubmissionActorError,
)
from brp.repository.models import (
    CanonicalPackage,
    CanonicalPackageEvent,
    CanonicalPackageRevision,
)


class CanonicalPackageRepository:
    def __init__(self, session: Session, *, site_id: UUID) -> None:
        self.session = session
        self.site_id = site_id

    def create(
        self,
        package: CanonicalDecisionPackage,
        *,
        actor: str,
        effective_from: datetime,
        effective_to: datetime | None,
        authored_at: datetime,
        reason: str,
    ) -> CanonicalPackageRevision:
        self._validate_interval(effective_from, effective_to)
        document, compiled, content_hash = self._materialize(
            package, actor=actor, authored_at=authored_at, reason=reason
        )
        record = CanonicalPackage(
            site_id=self.site_id,
            package_key=package.package_id,
            name=package.package_name,
            created_by=actor,
        )
        revision = CanonicalPackageRevision(
            package=record,
            revision=1,
            document=document,
            compiled_decisions=compiled,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor,
        )
        self.session.add(revision)
        self.session.flush()
        self._event(revision, actor, "CREATE_REVISION", "DRAFT", "DRAFT", reason)
        return revision

    def add_revision(
        self,
        package_key: str,
        package: CanonicalDecisionPackage,
        *,
        actor: str,
        effective_from: datetime,
        effective_to: datetime | None,
        authored_at: datetime,
        reason: str,
        base_revision: int,
    ) -> CanonicalPackageRevision:
        self._validate_interval(effective_from, effective_to)
        record = self.session.scalar(
            select(CanonicalPackage)
            .where(
                CanonicalPackage.site_id == self.site_id,
                CanonicalPackage.package_key == package_key,
            )
            .with_for_update()
        )
        if record is None:
            raise LookupError(f"canonical package not found: {package_key}")
        latest = int(
            self.session.scalar(
                select(func.max(CanonicalPackageRevision.revision)).where(
                    CanonicalPackageRevision.package_id == record.id
                )
            )
            or 0
        )
        if latest != base_revision:
            raise RuntimeError(f"revision conflict: expected {base_revision}, latest is {latest}")
        if package.package_id != package_key:
            raise ValueError("packageId cannot change between revisions")
        document, compiled, content_hash = self._materialize(
            package, actor=actor, authored_at=authored_at, reason=reason
        )
        revision = CanonicalPackageRevision(
            package_id=record.id,
            revision=latest + 1,
            document=document,
            compiled_decisions=compiled,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=actor,
        )
        record.name = package.package_name
        self.session.add(revision)
        self.session.flush()
        self._event(revision, actor, "CREATE_REVISION", "DRAFT", "DRAFT", reason)
        return revision

    def list_packages(self) -> list[CanonicalPackage]:
        return list(
            self.session.scalars(
                select(CanonicalPackage)
                .options(joinedload(CanonicalPackage.revisions))
                .where(CanonicalPackage.site_id == self.site_id)
                .order_by(CanonicalPackage.package_key)
            ).unique()
        )

    def get_revision(
        self, package_key: str, revision: int | None = None
    ) -> CanonicalPackageRevision:
        query = (
            select(CanonicalPackageRevision)
            .join(CanonicalPackage)
            .options(joinedload(CanonicalPackageRevision.package))
            .where(
                CanonicalPackage.site_id == self.site_id,
                CanonicalPackage.package_key == package_key,
            )
        )
        if revision is not None:
            query = query.where(CanonicalPackageRevision.revision == revision)
        else:
            query = query.order_by(CanonicalPackageRevision.revision.desc()).limit(1)
        result = self.session.scalar(query)
        if result is None:
            suffix = f"@{revision}" if revision is not None else ""
            raise LookupError(f"canonical package revision not found: {package_key}{suffix}")
        return result

    def submit(self, record: CanonicalPackageRevision, actor: str) -> None:
        self._require_status(record, "DRAFT")
        if actor != record.created_by:
            raise SubmissionActorError("only the package revision creator may submit")
        document = CanonicalDecisionPackage.model_validate(record.document)
        if not document.business_scenarios:
            raise ValueError("at least one business scenario is required before submission")
        record.submitted_by = actor
        record.submitted_at = datetime.now(UTC)
        self._transition(record, actor, "SUBMIT", "SUBMITTED")

    def approve(self, record: CanonicalPackageRevision, actor: str) -> None:
        self._require_status(record, "SUBMITTED")
        if actor in {record.created_by, record.submitted_by}:
            raise SelfApprovalError("package approver must differ from maker")
        self._require_no_approved_overlap(record)
        record.approved_by = actor
        record.decided_at = datetime.now(UTC)
        self._transition(record, actor, "APPROVE", "APPROVED")

    def reject(self, record: CanonicalPackageRevision, actor: str, reason: str) -> None:
        self._require_status(record, "SUBMITTED")
        if actor in {record.created_by, record.submitted_by}:
            raise SelfApprovalError("package rejector must differ from maker")
        if not reason.strip():
            raise ValueError("rejection reason is required")
        record.rejected_by = actor
        record.decided_at = datetime.now(UTC)
        self._transition(record, actor, "REJECT", "REJECTED", reason)

    def audit(self, package_key: str) -> list[CanonicalPackageEvent]:
        return list(
            self.session.scalars(
                select(CanonicalPackageEvent)
                .join(CanonicalPackageRevision)
                .join(CanonicalPackage)
                .where(
                    CanonicalPackage.site_id == self.site_id,
                    CanonicalPackage.package_key == package_key,
                )
                .order_by(CanonicalPackageEvent.id)
            )
        )

    def semantic_diff(
        self, package_key: str, from_revision: int, to_revision: int
    ) -> dict[str, Any]:
        before = CanonicalDecisionPackage.model_validate(
            self.get_revision(package_key, from_revision).document
        )
        after = CanonicalDecisionPackage.model_validate(
            self.get_revision(package_key, to_revision).document
        )
        return package_semantic_diff(before, after)

    @staticmethod
    def _materialize(
        package: CanonicalDecisionPackage, *, actor: str, authored_at: datetime, reason: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        compilation = compile_package(
            package, actor=actor, authored_at=authored_at, reason=reason
        )
        if not compilation.valid:
            detail = "; ".join(
                f"{item.path}: {item.message}" for item in compilation.diagnostics[:10]
            )
            raise ValueError(f"canonical package does not compile: {detail}")
        document = package.model_dump(mode="json", by_alias=True, exclude_none=True)
        rendered = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        compiled = [
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in compilation.decisions
        ]
        return document, compiled, hashlib.sha256(rendered).hexdigest()

    def _transition(
        self,
        record: CanonicalPackageRevision,
        actor: str,
        action: str,
        to_status: str,
        reason: str | None = None,
    ) -> None:
        from_status = record.lifecycle_status
        record.lifecycle_status = to_status
        self._event(record, actor, action, from_status, to_status, reason)

    def _event(
        self,
        record: CanonicalPackageRevision,
        actor: str,
        action: str,
        from_status: str,
        to_status: str,
        reason: str | None,
    ) -> None:
        self.session.add(
            CanonicalPackageEvent(
                revision_id=record.id,
                actor=actor,
                action=action,
                from_status=from_status,
                to_status=to_status,
                reason=reason,
                content_hash=record.content_hash,
            )
        )
        self.session.flush()

    def _require_no_approved_overlap(self, record: CanonicalPackageRevision) -> None:
        query = select(CanonicalPackageRevision.id).where(
            CanonicalPackageRevision.package_id == record.package_id,
            CanonicalPackageRevision.id != record.id,
            CanonicalPackageRevision.lifecycle_status == "APPROVED",
            or_(
                CanonicalPackageRevision.effective_to.is_(None),
                CanonicalPackageRevision.effective_to > record.effective_from,
            ),
        )
        if record.effective_to is not None:
            query = query.where(
                CanonicalPackageRevision.effective_from < record.effective_to
            )
        if self.session.scalar(query.limit(1)) is not None:
            raise EffectiveIntervalOverlapError(
                "approved package effective interval overlaps another revision"
            )

    @staticmethod
    def _require_status(record: CanonicalPackageRevision, expected: str) -> None:
        if record.lifecycle_status != expected:
            raise IllegalLifecycleTransitionError(
                f"expected {expected}, got {record.lifecycle_status}"
            )

    @staticmethod
    def _validate_interval(effective_from: datetime, effective_to: datetime | None) -> None:
        if effective_from.tzinfo is None:
            raise ValueError("effectiveFrom must be timezone-aware")
        if effective_to is not None and (
            effective_to.tzinfo is None or effective_to <= effective_from
        ):
            raise ValueError("effectiveTo must be timezone-aware and after effectiveFrom")


def package_semantic_diff(
    before: CanonicalDecisionPackage, after: CanonicalDecisionPackage
) -> dict[str, Any]:
    before_fields = {item.key: item.model_dump(mode="json") for item in before.vocabulary}
    after_fields = {item.key: item.model_dump(mode="json") for item in after.vocabulary}
    before_decisions = {item.decision_id: item for item in before.decisions}
    after_decisions = {item.decision_id: item for item in after.decisions}
    changed_rows: list[dict[str, Any]] = []
    for decision_id in sorted(before_decisions.keys() & after_decisions.keys()):
        old_rows = {
            item.row_id: item.model_dump(mode="json")
            for item in before_decisions[decision_id].rows
        }
        new_rows = {
            item.row_id: item.model_dump(mode="json")
            for item in after_decisions[decision_id].rows
        }
        for row_id in sorted(old_rows.keys() | new_rows.keys()):
            if old_rows.get(row_id) != new_rows.get(row_id):
                changed_rows.append(
                    {
                        "decisionId": decision_id,
                        "rowId": row_id,
                        "before": old_rows.get(row_id),
                        "after": new_rows.get(row_id),
                    }
                )
    return {
        "packageName": {"before": before.package_name, "after": after.package_name},
        "vocabulary": {
            "added": sorted(after_fields.keys() - before_fields.keys()),
            "removed": sorted(before_fields.keys() - after_fields.keys()),
            "changed": sorted(
                key
                for key in before_fields.keys() & after_fields.keys()
                if before_fields[key] != after_fields[key]
            ),
        },
        "decisions": {
            "added": sorted(after_decisions.keys() - before_decisions.keys()),
            "removed": sorted(before_decisions.keys() - after_decisions.keys()),
            "changedRows": changed_rows,
        },
        "scenariosChanged": (
            [item.model_dump(mode="json") for item in before.business_scenarios]
            != [item.model_dump(mode="json") for item in after.business_scenarios]
        ),
    }
