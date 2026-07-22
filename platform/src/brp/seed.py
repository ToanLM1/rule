"""Seed one curated workspace/site for acceptance and internal demonstrations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brp.db import create_database_engine
from brp.governance.golden import GoldenCaseData, GoldenRepository, GoldenSuiteEvidencePolicy
from brp.ir.models import DecisionContent
from brp.repository.lifecycle import LifecycleService
from brp.repository.models import (
    DEFAULT_SITE_ID,
    DEFAULT_WORKSPACE_ID,
    Decision,
    Site,
    SiteProfileRevision,
    Workspace,
)
from brp.repository.service import RevisionRepository

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "conformance"


def main() -> None:
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            if session.scalar(select(func.count()).select_from(Decision)):
                raise RuntimeError("seed refused: decisions already exist")
            workspace = session.get(Workspace, DEFAULT_WORKSPACE_ID)
            site = session.get(Site, DEFAULT_SITE_ID)
            if workspace is None or site is None:
                raise RuntimeError("production control-plane migration has not been applied")
            workspace.workspace_key = "operations"
            workspace.name = "Rules Operations"
            site.site_key = "sg-underwriting"
            site.name = "Singapore Underwriting"
            site.default_locale = "en"
            site.timezone = "Asia/Singapore"
            profile = sample_profile()
            canonical_profile = json.dumps(
                profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            session.add(
                SiteProfileRevision(
                    site_id=site.id,
                    revision=1,
                    document=profile,
                    content_hash=hashlib.sha256(canonical_profile.encode()).hexdigest(),
                    created_by="platform-seed",
                )
            )

            repository = RevisionRepository(session, site_id=site.id)
            effective = datetime(2026, 1, 1, tzinfo=UTC)
            approved = repository.create_decision(
                "enrollment_eligibility",
                fixture("enrollment_eligibility.json"),
                "maker-a",
                effective,
                product_key="CANCER_BASIC",
                flow_key="ENROLLMENT",
            )
            submitted = repository.create_decision(
                "required_documents",
                fixture("required_documents.json"),
                "maker-a",
                effective,
                flow_key="DOCUMENT_COLLECTION",
            )
            repository.create_decision(
                "premium_adjustments",
                fixture("premium_adjustments.json"),
                "maker-a",
                effective,
                flow_key="PRICING",
            )

            golden = GoldenRepository(session, site_id=site.id)
            lookup = golden.snapshot_lookup(
                "Singapore region eligibility",
                [{"region_code": "SEOUL", "eligible": True, "name": "Seoul"}],
                {
                    "ref": "lookup://region_eligibility",
                    "kind": "CURATED_ACCEPTANCE",
                },
                approved=True,
            )
            suite = golden.create_revision(
                "enrollment_eligibility",
                [
                    GoldenCaseData(
                        "minor-is-ineligible",
                        {"age": 17, "productCode": "CANCER_BASIC", "regionCode": "SEOUL"},
                        {"eligible": False, "reasonCode": "UNDER_AGE"},
                        {"kind": "CURATED_ACCEPTANCE", "approvedBy": "product-owner"},
                    )
                ],
                "maker-a",
                lookup_snapshot_hashes=[lookup.content_hash],
            )
            golden.submit(suite, "maker-a")
            golden.approve(suite, "checker-b")
            lifecycle = LifecycleService(session, GoldenSuiteEvidencePolicy())
            lifecycle.submit(approved, "maker-a")
            lifecycle.approve(approved, "checker-b")
            lifecycle.submit(submitted, "maker-a")
            session.commit()
    finally:
        engine.dispose()


def fixture(filename: str) -> DecisionContent:
    document = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    return DecisionContent.model_validate(document)


def sample_profile() -> dict[str, object]:
    return {
        "site": "sg-underwriting",
        "deliveryMode": "B",
        "language": "java",
        "source": {
            "db": {"kind": "postgres", "connectionEnv": "BRP_SOURCE_DATABASE_URL"},
            "repositories": [
                {
                    "alias": "legacy-enrollment",
                    "path": "fixtures/legacy-enrollment",
                    "revision": "88862106124623b598ae167dbbeeaa5ce292e728",
                }
            ],
            "programContexts": [
                {
                    "programId": "ENROLLMENT-API",
                    "kind": "API",
                    "repository": "legacy-enrollment",
                    "class": "legacy.EnrollmentValidator",
                    "method": "evaluate",
                }
            ],
        },
        "adapters": ["code-java", "db-postgres-stored-object", "engine-dmn"],
        "generators": ["java-source"],
        "mappingSpec": "config/mappings/fixture-tables.yaml",
        "target": {
            "language": "java",
            "repository": "out/fixture-remote.git",
            "baseBranch": "main",
            "generatedSourcePath": "src/generated/java",
            "generatedTestPath": "src/generatedTest/java",
            "javaPackage": "brp.rules.generated",
            "buildCommand": "./gradlew test --no-daemon",
            "prProvider": "local-report",
            "composition": {
                "facade": "legacy.rules.EnrollmentRuleModule",
                "decisions": {
                    "premium_adjustments": {
                        "field": "premiumLoadingPct",
                        "aggregate": "SUM",
                    },
                    "required_documents": {
                        "field": "requiredDoc",
                        "aggregate": "DISTINCT",
                    },
                },
            },
        },
    }


if __name__ == "__main__":
    main()
