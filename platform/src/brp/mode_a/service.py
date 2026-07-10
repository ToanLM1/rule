"""Append-only Mode-A publication, execution, audit, and rollback."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from brp.governance.golden import GoldenRepository
from brp.governance.runner import run_zen_mode_a
from brp.governance.zen import DictLookupResolver, export_jdm, preview
from brp.ir.models import DecisionContent
from brp.repository.errors import ModeAPublicationError
from brp.repository.models import Decision, ModeAPublication
from brp.repository.service import RevisionRepository


class ModeAService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def publish(
        self,
        decision_key: str,
        revision: int,
        suite_revision: int,
        actor: str,
        *,
        channel: str = "production",
        as_of: datetime | None = None,
    ) -> ModeAPublication:
        actor, channel = _identity(actor, channel)
        self._lock_decision(decision_key)
        decision = RevisionRepository(self.session).get_revision(decision_key, revision)
        suite = GoldenRepository(self.session).get_revision(decision_key, suite_revision)
        instant = as_of or datetime.now(UTC)
        if decision.lifecycle_status != "APPROVED":
            raise ModeAPublicationError("Mode-A publish requires an approved decision revision")
        if not _effective(decision.effective_from, decision.effective_to, instant):
            raise ModeAPublicationError("Mode-A publish requires an effective decision revision")
        if suite.lifecycle_status != "APPROVED":
            raise ModeAPublicationError("Mode-A publish requires an approved golden suite")
        validation = run_zen_mode_a(self.session, decision, suite)
        if validation["failed"] != 0 or validation["passed"] == 0:
            raise ModeAPublicationError("authoritative Zen golden validation failed")

        content = DecisionContent.model_validate(decision.content_blob.content)
        document = export_jdm(content).document
        previous = self.active(decision_key, channel=channel, required=False)
        record = ModeAPublication(
            decision_revision_id=decision.id,
            suite_revision_id=suite.id,
            channel=channel,
            action="PUBLISH",
            actor=actor,
            previous_publication_id=previous.id if previous is not None else None,
            source_publication_id=None,
            decision_hash=decision.content_hash,
            suite_hash=suite.content_hash,
            jdm_hash=_hash(document),
            jdm_document=document,
            lookup_snapshot_hashes=list(suite.lookup_snapshot_hashes),
            validation_result=validation,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def rollback(
        self,
        decision_key: str,
        target_publication_id: int,
        actor: str,
        *,
        channel: str = "production",
    ) -> ModeAPublication:
        actor, channel = _identity(actor, channel)
        self._lock_decision(decision_key)
        current = self.active(decision_key, channel=channel)
        assert current is not None
        target = self._publication(decision_key, target_publication_id, channel)
        if target.id == current.id:
            raise ModeAPublicationError("rollback target is already active")
        self._verify_artifact(target)
        validation = run_zen_mode_a(self.session, target.decision_revision, target.suite_revision)
        if validation["failed"] != 0 or validation["passed"] == 0:
            raise ModeAPublicationError("rollback target no longer passes its golden suite")
        record = ModeAPublication(
            decision_revision_id=target.decision_revision_id,
            suite_revision_id=target.suite_revision_id,
            channel=channel,
            action="ROLLBACK",
            actor=actor,
            previous_publication_id=current.id,
            source_publication_id=target.id,
            decision_hash=target.decision_hash,
            suite_hash=target.suite_hash,
            jdm_hash=target.jdm_hash,
            jdm_document=target.jdm_document,
            lookup_snapshot_hashes=list(target.lookup_snapshot_hashes),
            validation_result=validation,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def active(
        self,
        decision_key: str,
        *,
        channel: str = "production",
        required: bool = True,
    ) -> ModeAPublication | None:
        record = self.session.scalar(
            select(ModeAPublication)
            .join(ModeAPublication.decision_revision)
            .join(Decision)
            .where(Decision.decision_key == decision_key, ModeAPublication.channel == channel)
            .order_by(ModeAPublication.id.desc())
            .limit(1)
        )
        if record is None and required:
            raise ModeAPublicationError(f"no active Mode-A publication for {decision_key}")
        return record

    def history(self, decision_key: str, *, channel: str = "production") -> list[ModeAPublication]:
        return list(
            self.session.scalars(
                select(ModeAPublication)
                .join(ModeAPublication.decision_revision)
                .join(Decision)
                .where(
                    Decision.decision_key == decision_key,
                    ModeAPublication.channel == channel,
                )
                .order_by(ModeAPublication.id)
            )
        )

    def execute(
        self,
        decision_key: str,
        inputs: dict[str, object],
        *,
        channel: str = "production",
    ) -> dict[str, object]:
        publication = self.active(decision_key, channel=channel)
        assert publication is not None
        self._verify_artifact(publication)
        golden = GoldenRepository(self.session)
        snapshots = golden.lookup_snapshots(publication.lookup_snapshot_hashes)
        resolver = DictLookupResolver(
            {
                str(snapshot.source.get("ref") or f"lookup://{snapshot.name}"): snapshot.content
                for snapshot in snapshots
            }
        )
        content = DecisionContent.model_validate(publication.decision_revision.content_blob.content)
        result = preview(content, inputs, resolver)
        return {
            "executor": "ZEN",
            "authority": "AUTHORITATIVE",
            "publicationId": publication.id,
            "decisionRevision": publication.decision_revision.revision,
            "result": result["result"],
        }

    def _publication(
        self, decision_key: str, publication_id: int, channel: str
    ) -> ModeAPublication:
        record = self.session.scalar(
            select(ModeAPublication)
            .join(ModeAPublication.decision_revision)
            .join(Decision)
            .where(
                Decision.decision_key == decision_key,
                ModeAPublication.channel == channel,
                ModeAPublication.id == publication_id,
            )
        )
        if record is None:
            raise ModeAPublicationError("rollback target is not a publication in this channel")
        return record

    @staticmethod
    def _verify_artifact(publication: ModeAPublication) -> None:
        decision = publication.decision_revision
        suite = publication.suite_revision
        if decision.content_hash != publication.decision_hash:
            raise ModeAPublicationError("published decision hash mismatch")
        if suite.content_hash != publication.suite_hash:
            raise ModeAPublicationError("published suite hash mismatch")
        if _hash(publication.jdm_document) != publication.jdm_hash:
            raise ModeAPublicationError("published JDM hash mismatch")
        current = export_jdm(DecisionContent.model_validate(decision.content_blob.content)).document
        if _hash(current) != publication.jdm_hash:
            raise ModeAPublicationError("runtime JDM exporter differs from published artifact")

    def _lock_decision(self, decision_key: str) -> None:
        self.session.scalar(
            select(Decision).where(Decision.decision_key == decision_key).with_for_update()
        )


def _effective(start: datetime, end: datetime | None, instant: datetime) -> bool:
    return start <= instant and (end is None or instant < end)


def _identity(actor: str, channel: str) -> tuple[str, str]:
    if not actor.strip() or not channel.strip():
        raise ModeAPublicationError("actor and channel are required")
    return actor.strip(), channel.strip()


def _hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()
