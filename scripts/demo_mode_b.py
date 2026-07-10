"""Shared repeatable Mode-B demonstration used by shell launchers."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from brp.adapters.contracts import (
    AdapterDiagnostic,
    CandidateDecision,
    ExtractionBatch,
    SourceSnapshot,
    UnmappableItem,
)
from brp.db import create_database_engine
from brp.delivery import (
    establish_seam_baseline,
    prove_delivered_execution,
    publish_delivery_branch,
    transactional_delivery_gate,
)
from brp.governance.golden import (
    GoldenCaseData,
    GoldenRepository,
    GoldenSuiteEvidencePolicy,
)
from brp.ingestion import IngestionRunner
from brp.ir.models import DecisionContent
from brp.repository.lifecycle import LifecycleService
from brp.repository.review_queue import ReviewQueueService, ReviewStatus
from brp.repository.service import RevisionRepository

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
FIXTURE = PLATFORM / "tests/fixtures/conformance/enrollment_eligibility.json"


def main() -> int:
    started = time.perf_counter()
    command.upgrade(Config(PLATFORM / "alembic.ini"), "head")
    engine = create_database_engine()
    run_id = uuid4().hex[:10]
    key = f"demo_enrollment_{run_id}"
    now = datetime.now(UTC)
    initial = content(18)
    with Session(engine) as session:
        batch = ExtractionBatch(
            adapter="code-java",
            decisions=[CandidateDecision(decision_key=key, content=initial)],
            unmappable=[
                UnmappableItem(
                    reason_code="UNSUPPORTED_RAW_CALL",
                    raw_fragment="legacy.sideEffect(request)",
                    provenance={"fixture": "EnrollmentValidator.java", "line": 99},
                )
            ],
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO", code="DEMO_INGEST", message="recorded fixture mining"
                )
            ],
            source_snapshot=SourceSnapshot(
                source_id="git:legacy-enrollment",
                revision="fixture-v1",
                content_hash="1" * 64,
                captured_at=now,
            ),
        )
        ingest = IngestionRunner(session).ingest(
            [batch], actor="maker-a", effective_from=now
        )
        queue = ReviewQueueService(session)
        for item in queue.list_open():
            if item.source_snapshot_hash == "1" * 64:
                queue.dispose(
                    item.id,
                    status=ReviewStatus.REJECTED,
                    actor="checker-b",
                    reason="unsupported side effect excluded from IR",
                )
        golden = GoldenRepository(session)
        snapshot = golden.snapshot_lookup(
            "region_eligibility",
            [
                {"region_code": "SEOUL", "eligible": True, "name": "서울"},
                {"region_code": "JEJU", "eligible": False, "name": "제주"},
            ],
            {"ref": "lookup://region_eligibility", "table": "region_eligibility"},
            approved=True,
        )
        suite1 = golden.create_revision(
            key,
            [golden_case(True, "ELIGIBLE")],
            "maker-a",
            lookup_snapshot_hashes=[snapshot.content_hash],
        )
        golden.submit(suite1, "maker-a")
        golden.approve(suite1, "checker-b")
        repository = RevisionRepository(session)
        revision1 = repository.get_revision(key, 1)
        lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
        lifecycle.submit(revision1, "maker-a")
        lifecycle.approve(revision1, "checker-b")
        session.commit()

        with tempfile.TemporaryDirectory(prefix="brp-mode-b-demo-") as directory:
            work = Path(directory)
            remote = work / "fixture-remote.git"
            baseline = work / "baseline"
            establish_seam_baseline(
                ROOT, ROOT / "fixtures/legacy-enrollment", remote, baseline
            )
            before = prove_delivered_execution(remote, "main", work / "before")
            print(extract_outcome("BEFORE", before.output))

            revision2 = repository.add_revision(
                key, content(19), "maker-a", now + timedelta(seconds=1)
            )
            suite2 = golden.create_revision(
                key,
                [golden_case(False, "UNDER_AGE")],
                "maker-a",
                lookup_snapshot_hashes=[snapshot.content_hash],
            )
            golden.submit(suite2, "maker-a")
            golden.approve(suite2, "checker-b")
            lifecycle.submit(revision2, "maker-a")
            lifecycle.retire(revision1, "checker-b", reason="superseded by approved r2")
            lifecycle.approve(revision2, "checker-b")
            session.commit()

            release = create_release(
                baseline, work / "release", revision2, suite2, snapshot
            )
            gate = transactional_delivery_gate(
                remote, "seam-baseline-v1", release, work / "gate"
            )
            delivery = publish_delivery_branch(
                gate, key, 2, {"minimumAge": {"before": 18, "after": 19}}
            )
            after = prove_delivered_execution(
                remote, delivery.branch, work / "delivered"
            )
            print(extract_outcome("AFTER", after.output))
            print("EXECUTOR: GENERATED_JAVA")
            print(f"REVISION: {key}@2")
            print(f"SUITE: r{suite2.revision} {suite2.content_hash}")
            print(f"LOOKUP: {snapshot.content_hash}")
            print(f"MANIFEST: {after.manifest_hash}")
            print(f"BRANCH: {delivery.branch}")
            print(f"DELIVERY COMMIT: {delivery.head_commit}")
            print(f"INGESTED: {ingest.inserted_revisions}; REVIEWED: 1")
    engine.dispose()
    print(f"TOTAL_SECONDS: {time.perf_counter() - started:.3f}")
    return 0


def content(minimum_age: int) -> DecisionContent:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["rules"][0]["when"]["all"][0]["right"]["value"] = minimum_age
    return DecisionContent.model_validate(document)


def golden_case(eligible: bool, reason: str) -> GoldenCaseData:
    return GoldenCaseData(
        case_key="age-eighteen",
        input={"age": 18, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
        expected={"eligible": eligible, "reasonCode": reason},
        provenance={"type": "LEGACY_BEHAVIOR", "entry": "EnrollmentValidator#evaluate"},
    )


def create_release(
    baseline: Path, release: Path, revision: object, suite: object, snapshot: object
) -> Path:
    relative = Path(
        "src/generated/java/brp/rules/generated/EnrollmentEligibilityDecision.java"
    )
    source = (baseline / relative).read_text(encoding="utf-8")
    source = source.replace(
        "RuleSupport.compare(input.age(), 18) < 0",
        "RuleSupport.compare(input.age(), 19) < 0",
    )
    target = release / relative
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    output_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "releaseHash": hashlib.sha256(
            f"{revision.content_hash}{suite.content_hash}{snapshot.content_hash}".encode()
        ).hexdigest(),
        "decision": {
            "revision": revision.revision,
            "contentHash": revision.content_hash,
        },
        "goldenSuite": {"revision": suite.revision, "contentHash": suite.content_hash},
        "lookupSnapshots": [snapshot.content_hash],
        "outputs": [{"path": relative.as_posix(), "hash": output_hash}],
    }
    (release / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return release


def extract_outcome(label: str, output: str) -> str:
    line = next(value for value in output.splitlines() if "OUTCOME:" in value)
    return f"{label}: {line.split('OUTCOME:', 1)[1].strip()}"


if __name__ == "__main__":
    raise SystemExit(main())
