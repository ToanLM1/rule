"""Scope ingestion and lookup content hashes to a site."""

from alembic import op

revision = "0007_site_scoped_hashes"
down_revision = "0006_worker_heartbeats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_ingestion_fingerprints_fingerprint", "ingestion_fingerprints", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingestion_fingerprints_site_id",
        "ingestion_fingerprints",
        ["site_id", "fingerprint"],
    )
    op.drop_constraint("uq_lookup_snapshots_content_hash", "lookup_snapshots", type_="unique")
    op.create_unique_constraint(
        "uq_lookup_snapshots_site_id", "lookup_snapshots", ["site_id", "content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_lookup_snapshots_site_id", "lookup_snapshots", type_="unique"
    )
    op.create_unique_constraint(
        "uq_lookup_snapshots_content_hash", "lookup_snapshots", ["content_hash"]
    )
    op.drop_constraint(
        "uq_ingestion_fingerprints_site_id", "ingestion_fingerprints", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ingestion_fingerprints_fingerprint", "ingestion_fingerprints", ["fingerprint"]
    )
