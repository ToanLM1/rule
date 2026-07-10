"""Persist idempotent adapter ingestion fingerprints."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_ingestion_fingerprints"
down_revision = "0001_governed_repository"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_fingerprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("adapter", sa.String(length=100), nullable=False),
        sa.Column("capability_version", sa.String(length=100), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_hash", sa.String(length=64), nullable=False),
        sa.Column("decision_key", sa.String(length=200), nullable=True),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["decision_revisions.id"],
            name="fk_ingestion_fingerprints_revision_id_decision_revisions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_fingerprints"),
        sa.UniqueConstraint("fingerprint", name="uq_ingestion_fingerprints_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_fingerprints")
