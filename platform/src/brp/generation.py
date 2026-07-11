"""Repository-aware, atomic deterministic generation orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from brp.config.models import SiteProfile
from brp.generators.contracts import (
    GeneratedArtifact,
    GoldenReleaseEvidence,
    LookupReleaseSnapshot,
    ReleaseEnvelope,
    ReleaseInput,
)
from brp.generators.java_release import java_class_name, render_golden_junit, render_manifest
from brp.governance.golden import GoldenRepository
from brp.ir.models import DecisionContent
from brp.repository.errors import ApprovalEvidenceError
from brp.repository.service import RevisionRepository


class ReleaseBuilder(Protocol):
    name: str
    version: str

    def build(self, release: ReleaseInput) -> list[GeneratedArtifact]: ...


class GenerationOrchestrator:
    def __init__(self, session: Session, builder: ReleaseBuilder) -> None:
        self.session = session
        self.builder = builder

    def generate(
        self,
        profile: SiteProfile,
        decision_key: str,
        output_root: Path,
        *,
        revision: int | None = None,
        as_of: datetime | None = None,
    ) -> Path:
        if profile.target is None:
            raise ValueError("generation requires a Mode-B target")
        decision = RevisionRepository(self.session).resolve_approved(
            decision_key, revision=revision, as_of=as_of
        )
        golden_repository = GoldenRepository(self.session)
        suite = golden_repository.approved_for_decision(decision.decision_id)
        if suite is None:
            raise ApprovalEvidenceError("approved golden suite is required for generation")
        cases = golden_repository.cases(suite)
        snapshots = golden_repository.lookup_snapshots(suite.lookup_snapshot_hashes)
        release = ReleaseInput(
            content=DecisionContent.model_validate(decision.content_blob.content),
            envelope=ReleaseEnvelope(
                decision_key=decision_key,
                revision=decision.revision,
                content_hash=decision.content_hash,
                effective_from=decision.effective_from,
                effective_to=decision.effective_to,
            ),
            golden_suite=GoldenReleaseEvidence(
                revision=suite.revision,
                content_hash=suite.content_hash,
                cases=[
                    {
                        "caseKey": case.case_key,
                        "input": case.input,
                        "expected": case.expected,
                        "provenance": case.provenance,
                    }
                    for case in cases
                ],
            ),
            lookup_snapshots=[
                LookupReleaseSnapshot(
                    snapshot_id=str(snapshot.id),
                    content_hash=snapshot.content_hash,
                    name=snapshot.name,
                    rows=snapshot.content,
                )
                for snapshot in snapshots
            ],
            site=profile.site,
            target=profile.target,
            site_config_hash=_hash(
                profile.model_dump(mode="json", by_alias=True, exclude_none=True)
            ),
            generator=self.builder.name,
            generator_version=self.builder.version,
        )
        artifacts = self.builder.build(release)
        junit = render_golden_junit(release)
        all_artifacts = [*artifacts, junit]
        all_artifacts.append(render_manifest(release, all_artifacts))
        destination = output_root / decision_key / f"r{decision.revision}"
        _atomic_write(destination, all_artifacts)
        return destination


class JavaCliReleaseBuilder:
    name = "java-source"
    version = "1.0.0"

    def __init__(self, repository_root: Path) -> None:
        self.root = repository_root

    def build(self, release: ReleaseInput) -> list[GeneratedArtifact]:
        if release.target.java_package is None:
            raise ValueError("java-source builder requires a Java target")
        toolchain = self.root / "java-toolchain"
        gradle = toolchain / ("gradlew.bat" if os.name == "nt" else "gradlew")
        subprocess.run(
            [str(gradle), ":codegen-cli:installDist", "--no-daemon"],
            cwd=toolchain,
            check=True,
        )
        launcher = (
            toolchain
            / "codegen-cli/build/install/codegen-cli/bin"
            / ("codegen-cli.bat" if os.name == "nt" else "codegen-cli")
        )
        with tempfile.TemporaryDirectory(prefix="brp-java-cli-") as directory:
            temporary = Path(directory)
            release_path = temporary / "release-input.json"
            release_path.write_bytes(release.canonical_bytes())
            source_root = temporary / "source"
            subprocess.run([str(launcher), str(release_path), str(source_root)], check=True)
            relative_java = (
                Path(release.target.java_package.replace(".", "/"))
                / f"{java_class_name(release.content.decision_id)}.java"
            )
            source = (source_root / relative_java).read_text(encoding="utf-8")
            artifact_path = Path(release.target.generated_source_path) / relative_java
            return [GeneratedArtifact.create(artifact_path.as_posix(), source)]


def _atomic_write(destination: Path, artifacts: list[GeneratedArtifact]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        for artifact in artifacts:
            relative = Path(artifact.path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe generated artifact path: {artifact.path}")
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(artifact.content, encoding="utf-8", newline="\n")
        if destination.exists():
            if _tree_hash(destination) == _tree_hash(temporary):
                shutil.rmtree(temporary)
                return
            backup = destination.with_name(f".{destination.name}-previous")
            if backup.exists():
                shutil.rmtree(backup)
            destination.replace(backup)
            temporary.replace(destination)
            shutil.rmtree(backup)
        else:
            temporary.replace(destination)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def _hash(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
