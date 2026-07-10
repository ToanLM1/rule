"""Immutable golden suites, lookup snapshots, and maker-checker evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brp.repository.errors import (
    ApprovalEvidenceError,
    DecisionNotFoundError,
    IllegalLifecycleTransitionError,
    SelfApprovalError,
    SubmissionActorError,
)
from brp.repository.models import (
    Decision,
    DecisionRevision,
    GoldenCase,
    GoldenSuite,
    GoldenSuiteLifecycleEvent,
    GoldenSuiteRevision,
    LookupSnapshot,
)


@dataclass(frozen=True)
class GoldenCaseData:
    case_key: str
    input: dict[str, Any]
    expected: dict[str, Any] | list[dict[str, Any]]
    provenance: dict[str, Any]


class GoldenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_revision(
        self,
        decision_key: str,
        cases: list[GoldenCaseData],
        actor: str,
        *,
        lookup_snapshot_hashes: list[str] | None = None,
    ) -> GoldenSuiteRevision:
        decision = self.session.scalar(
            select(Decision).where(Decision.decision_key == decision_key).with_for_update()
        )
        if decision is None:
            raise DecisionNotFoundError(decision_key)
        suite = self.session.scalar(
            select(GoldenSuite).where(GoldenSuite.decision_id == decision.id)
        )
        if suite is None:
            suite = GoldenSuite(decision_id=decision.id)
            self.session.add(suite)
            self.session.flush()
        latest = self.session.scalar(
            select(func.max(GoldenSuiteRevision.revision)).where(
                GoldenSuiteRevision.suite_id == suite.id
            )
        )
        ordered = sorted(cases, key=lambda item: item.case_key)
        if len({case.case_key for case in ordered}) != len(ordered):
            raise ValueError("golden case keys must be unique")
        snapshots = sorted(lookup_snapshot_hashes or [])
        document = {
            "cases": [
                {
                    "caseKey": case.case_key,
                    "input": case.input,
                    "expected": case.expected,
                    "provenance": case.provenance,
                }
                for case in ordered
            ],
            "lookupSnapshotHashes": snapshots,
        }
        content_hash = _hash(document)
        revision = GoldenSuiteRevision(
            suite_id=suite.id,
            revision=(latest or 0) + 1,
            lifecycle_status="DRAFT",
            content_hash=content_hash,
            lookup_snapshot_hashes=snapshots,
            created_by=actor,
        )
        self.session.add(revision)
        self.session.flush()
        self.session.add_all(
            GoldenCase(
                suite_revision_id=revision.id,
                case_key=case.case_key,
                input=case.input,
                expected=case.expected,
                provenance=case.provenance,
            )
            for case in ordered
        )
        self._event(revision, actor, "CREATE_REVISION", "DRAFT", "DRAFT")
        self.session.flush()
        return revision

    def submit(self, revision: GoldenSuiteRevision, actor: str) -> GoldenSuiteRevision:
        if revision.lifecycle_status != "DRAFT":
            raise IllegalLifecycleTransitionError("golden suite must be DRAFT")
        if actor != revision.created_by:
            raise SubmissionActorError("only golden-suite creator may submit")
        revision.submitted_by = actor
        self._event(revision, actor, "SUBMIT", "DRAFT", "SUBMITTED")
        revision.lifecycle_status = "SUBMITTED"
        self.session.flush()
        return revision

    def approve(self, revision: GoldenSuiteRevision, actor: str) -> GoldenSuiteRevision:
        if revision.lifecycle_status != "SUBMITTED":
            raise IllegalLifecycleTransitionError("golden suite must be SUBMITTED")
        if actor in {revision.created_by, revision.submitted_by}:
            raise SelfApprovalError("golden-suite approver must differ from maker")
        snapshots = list(
            self.session.scalars(
                select(LookupSnapshot).where(
                    LookupSnapshot.content_hash.in_(revision.lookup_snapshot_hashes)
                )
            )
        )
        if len(snapshots) != len(revision.lookup_snapshot_hashes) or any(
            not snapshot.approved for snapshot in snapshots
        ):
            raise ApprovalEvidenceError("all referenced lookup snapshots must be approved")
        revision.approved_by = actor
        self._event(revision, actor, "APPROVE", "SUBMITTED", "APPROVED")
        revision.lifecycle_status = "APPROVED"
        self.session.flush()
        return revision

    def cases(self, revision: GoldenSuiteRevision) -> list[GoldenCase]:
        return list(
            self.session.scalars(
                select(GoldenCase)
                .where(GoldenCase.suite_revision_id == revision.id)
                .order_by(GoldenCase.case_key)
            )
        )

    def get_revision(self, decision_key: str, revision: int) -> GoldenSuiteRevision:
        record = self.session.scalar(
            select(GoldenSuiteRevision)
            .join(GoldenSuite)
            .join(Decision)
            .where(
                Decision.decision_key == decision_key,
                GoldenSuiteRevision.revision == revision,
            )
        )
        if record is None:
            raise DecisionNotFoundError(f"golden suite {decision_key}@{revision}")
        return record

    def lookup_snapshots(self, hashes: list[str]) -> list[LookupSnapshot]:
        if not hashes:
            return []
        records = list(
            self.session.scalars(
                select(LookupSnapshot)
                .where(LookupSnapshot.content_hash.in_(hashes))
                .order_by(LookupSnapshot.content_hash)
            )
        )
        if len(records) != len(hashes):
            raise ApprovalEvidenceError("golden suite references missing lookup snapshots")
        return records

    def approved_for_decision(self, decision_id: object) -> GoldenSuiteRevision | None:
        return self.session.scalar(
            select(GoldenSuiteRevision)
            .join(GoldenSuite)
            .where(
                GoldenSuite.decision_id == decision_id,
                GoldenSuiteRevision.lifecycle_status == "APPROVED",
            )
            .order_by(GoldenSuiteRevision.revision.desc())
            .limit(1)
        )

    def snapshot_lookup(
        self,
        name: str,
        rows: list[dict[str, Any]],
        source: dict[str, Any],
        *,
        approved: bool = False,
    ) -> LookupSnapshot:
        ordered = sorted(rows, key=lambda row: _canonical(row))
        content_hash = _hash(ordered)
        existing = self.session.scalar(
            select(LookupSnapshot).where(LookupSnapshot.content_hash == content_hash)
        )
        if existing is not None:
            return existing
        snapshot = LookupSnapshot(
            name=name,
            content_hash=content_hash,
            content=ordered,
            source=source,
            approved=approved,
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def _event(
        self,
        revision: GoldenSuiteRevision,
        actor: str,
        action: str,
        from_status: str,
        to_status: str,
    ) -> None:
        self.session.add(
            GoldenSuiteLifecycleEvent(
                suite_revision_id=revision.id,
                actor=actor,
                action=action,
                from_status=from_status,
                to_status=to_status,
                content_hash=revision.content_hash,
            )
        )


class GoldenSuiteEvidencePolicy:
    def __init__(
        self,
        *,
        minimum_cases: int = 1,
        require_lookup_snapshot: bool = False,
    ) -> None:
        if minimum_cases < 1:
            raise ValueError("minimum_cases must be positive")
        self.minimum_cases = minimum_cases
        self.require_lookup_snapshot = require_lookup_snapshot

    def require_approved_evidence(self, session: Session, revision: DecisionRevision) -> None:
        repository = GoldenRepository(session)
        suite = repository.approved_for_decision(revision.decision_id)
        if suite is None:
            raise ApprovalEvidenceError("approved golden-suite evidence is required")
        if len(repository.cases(suite)) < self.minimum_cases:
            raise ApprovalEvidenceError(
                f"release evidence requires at least {self.minimum_cases} golden cases"
            )
        if self.require_lookup_snapshot and not suite.lookup_snapshot_hashes:
            raise ApprovalEvidenceError("release evidence requires a lookup snapshot")


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
