"""Create immutable decision repository and governed release evidence tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_governed_repository"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_key", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decisions"),
        sa.UniqueConstraint("decision_key", name="uq_decisions_decision_key"),
    )
    op.create_table(
        "decision_contents",
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("content_hash", name="pk_decision_contents"),
    )
    op.create_table(
        "decision_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("submitted_by", sa.String(length=200), nullable=True),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column("rejected_by", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["content_hash"],
            ["decision_contents.content_hash"],
            name="fk_decision_revisions_content_hash_decision_contents",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_decision_revisions_decision_id_decisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_revisions"),
        sa.UniqueConstraint("decision_id", "revision", name="uq_decision_revisions_decision_id"),
    )
    op.create_table(
        "lifecycle_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "transaction_id",
            sa.BigInteger(),
            server_default=sa.text("txid_current()"),
            nullable=False,
        ),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["decision_revisions.id"],
            name="fk_lifecycle_events_revision_id_decision_revisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lifecycle_events"),
    )
    op.create_table(
        "review_queue_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adapter", sa.String(length=100), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_fragment", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("disposition_history", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_queue_items"),
    )
    op.create_table(
        "golden_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_golden_suites_decision_id_decisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_golden_suites"),
        sa.UniqueConstraint("decision_id", name="uq_golden_suites_decision_id"),
    )
    op.create_table(
        "golden_suite_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("submitted_by", sa.String(length=200), nullable=True),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["suite_id"],
            ["golden_suites.id"],
            name="fk_golden_suite_revisions_suite_id_golden_suites",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_golden_suite_revisions"),
        sa.UniqueConstraint("suite_id", "revision", name="uq_golden_suite_revisions_suite_id"),
    )
    op.create_table(
        "golden_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_key", sa.String(length=200), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["suite_revision_id"],
            ["golden_suite_revisions.id"],
            name="fk_golden_cases_suite_revision_id_golden_suite_revisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_golden_cases"),
        sa.UniqueConstraint(
            "suite_revision_id", "case_key", name="uq_golden_cases_suite_revision_id"
        ),
    )
    op.create_table(
        "lookup_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lookup_snapshots"),
        sa.UniqueConstraint("content_hash", name="uq_lookup_snapshots_content_hash"),
    )

    op.execute(
        """
        CREATE FUNCTION brp_reject_immutable_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'BRP_IMMUTABLE_RECORD: % cannot be updated or deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER decision_contents_immutable
          BEFORE UPDATE OR DELETE ON decision_contents
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();

        CREATE TRIGGER lifecycle_events_immutable
          BEFORE UPDATE OR DELETE ON lifecycle_events
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();

        CREATE TRIGGER lookup_snapshots_immutable
          BEFORE UPDATE OR DELETE ON lookup_snapshots
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION brp_reject_revision_identity_mutation() RETURNS trigger AS $$
        BEGIN
          IF NEW.decision_id IS DISTINCT FROM OLD.decision_id
             OR NEW.revision IS DISTINCT FROM OLD.revision
             OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
             OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
             OR NEW.effective_to IS DISTINCT FROM OLD.effective_to
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'BRP_IMMUTABLE_REVISION_FIELDS';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER decision_revision_identity_immutable
          BEFORE UPDATE ON decision_revisions
          FOR EACH ROW EXECUTE FUNCTION brp_reject_revision_identity_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION brp_require_lifecycle_event() RETURNS trigger AS $$
        BEGIN
          IF NEW.lifecycle_status IS DISTINCT FROM OLD.lifecycle_status
             AND NOT EXISTS (
               SELECT 1 FROM lifecycle_events e
               WHERE e.revision_id = NEW.id
                 AND e.from_status = OLD.lifecycle_status
                 AND e.to_status = NEW.lifecycle_status
                 AND e.content_hash = NEW.content_hash
                 AND e.transaction_id = txid_current()
             ) THEN
            RAISE EXCEPTION 'BRP_LIFECYCLE_EVENT_REQUIRED';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE CONSTRAINT TRIGGER decision_revision_status_event
          AFTER UPDATE OF lifecycle_status ON decision_revisions
          DEFERRABLE INITIALLY DEFERRED
          FOR EACH ROW EXECUTE FUNCTION brp_require_lifecycle_event();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS decision_revision_status_event ON decision_revisions")
    op.execute("DROP FUNCTION IF EXISTS brp_require_lifecycle_event()")
    op.execute("DROP TRIGGER IF EXISTS decision_revision_identity_immutable ON decision_revisions")
    op.execute("DROP FUNCTION IF EXISTS brp_reject_revision_identity_mutation()")
    op.execute("DROP TRIGGER IF EXISTS lookup_snapshots_immutable ON lookup_snapshots")
    op.execute("DROP TRIGGER IF EXISTS lifecycle_events_immutable ON lifecycle_events")
    op.execute("DROP TRIGGER IF EXISTS decision_contents_immutable ON decision_contents")
    op.execute("DROP FUNCTION IF EXISTS brp_reject_immutable_mutation()")
    op.drop_table("lookup_snapshots")
    op.drop_table("golden_cases")
    op.drop_table("golden_suite_revisions")
    op.drop_table("golden_suites")
    op.drop_table("review_queue_items")
    op.drop_table("lifecycle_events")
    op.drop_table("decision_revisions")
    op.drop_table("decision_contents")
    op.drop_table("decisions")
