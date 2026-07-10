"""Harden golden-suite governance and evidence immutability."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_golden_governance"
down_revision = "0002_ingestion_fingerprints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "golden_suite_revisions",
        sa.Column(
            "lookup_snapshot_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "golden_suite_lifecycle_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("suite_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["suite_revision_id"],
            ["golden_suite_revisions.id"],
            name="fk_golden_suite_lifecycle_events_suite_revision_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_golden_suite_lifecycle_events"),
    )
    op.execute(
        """
        CREATE TRIGGER golden_cases_immutable
          BEFORE UPDATE OR DELETE ON golden_cases
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();
        CREATE TRIGGER golden_suite_events_immutable
          BEFORE UPDATE OR DELETE ON golden_suite_lifecycle_events
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();

        CREATE FUNCTION brp_reject_golden_identity_mutation() RETURNS trigger AS $$
        BEGIN
          IF NEW.suite_id IS DISTINCT FROM OLD.suite_id
             OR NEW.revision IS DISTINCT FROM OLD.revision
             OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
             OR NEW.lookup_snapshot_hashes IS DISTINCT FROM OLD.lookup_snapshot_hashes
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'BRP_IMMUTABLE_GOLDEN_REVISION_FIELDS';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER golden_suite_revision_identity_immutable
          BEFORE UPDATE ON golden_suite_revisions
          FOR EACH ROW EXECUTE FUNCTION brp_reject_golden_identity_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS golden_suite_revision_identity_immutable ON golden_suite_revisions"
    )
    op.execute("DROP FUNCTION IF EXISTS brp_reject_golden_identity_mutation()")
    op.execute(
        "DROP TRIGGER IF EXISTS golden_suite_events_immutable ON golden_suite_lifecycle_events"
    )
    op.execute("DROP TRIGGER IF EXISTS golden_cases_immutable ON golden_cases")
    op.drop_table("golden_suite_lifecycle_events")
    op.drop_column("golden_suite_revisions", "lookup_snapshot_hashes")
