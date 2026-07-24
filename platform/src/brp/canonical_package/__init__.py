"""Business-authored canonical decision packages and deterministic compilation."""

from brp.canonical_package.compiler import PackageCompilation, PackageDiagnostic, compile_package
from brp.canonical_package.models import CanonicalDecisionPackage
from brp.canonical_package.repository import CanonicalPackageRepository, package_semantic_diff

__all__ = [
    "CanonicalDecisionPackage",
    "CanonicalPackageRepository",
    "PackageCompilation",
    "PackageDiagnostic",
    "compile_package",
    "package_semantic_diff",
]
