"""Add the multi-site production control plane and durable work queue."""

from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_production_control_plane"
down_revision = "0004_mode_a_publications"
branch_labels = None
depends_on = None

DEFAULT_WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_SITE_ID = UUID("00000000-0000-0000-0000-000000000002")


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("workspace_key", name="uq_workspaces_workspace_key"),
    )
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("default_locale", sa.String(16), server_default="en", nullable=False),
        sa.Column("timezone", sa.String(100), server_default="UTC", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_sites_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sites"),
        sa.UniqueConstraint("workspace_id", "site_key", name="uq_sites_workspace_id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO workspaces (id, workspace_key, name) VALUES "
            "(:workspace_id, 'default', 'Default workspace')"
        ).bindparams(
            sa.bindparam("workspace_id", DEFAULT_WORKSPACE_ID, type_=postgresql.UUID(as_uuid=True))
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO sites (id, workspace_id, site_key, name) VALUES "
            "(:site_id, :workspace_id, 'default', 'Default site')"
        ).bindparams(
            sa.bindparam("site_id", DEFAULT_SITE_ID, type_=postgresql.UUID(as_uuid=True)),
            sa.bindparam(
                "workspace_id", DEFAULT_WORKSPACE_ID, type_=postgresql.UUID(as_uuid=True)
            ),
        )
    )
    op.create_table(
        "site_profile_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name="fk_site_profile_revisions_site_id_sites",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_site_profile_revisions"),
        sa.UniqueConstraint("site_id", "revision", name="uq_site_profile_revisions_site_id"),
    )

    for table in ("decisions", "review_queue_items", "ingestion_fingerprints", "lookup_snapshots"):
        op.add_column(table, sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET site_id = :site_id").bindparams(
                sa.bindparam("site_id", DEFAULT_SITE_ID, type_=postgresql.UUID(as_uuid=True))
            )
        )
        op.alter_column(table, "site_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_site_id_sites", table, "sites", ["site_id"], ["id"], ondelete="CASCADE"
        )
    op.add_column(
        "review_queue_items",
        sa.Column("import_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("decisions", sa.Column("product_key", sa.String(200), nullable=True))
    op.add_column("decisions", sa.Column("flow_key", sa.String(200), nullable=True))
    op.drop_constraint("uq_decisions_decision_key", "decisions", type_="unique")
    op.create_unique_constraint("uq_decisions_site_id", "decisions", ["site_id", "decision_key"])
    op.create_index(
        "ix_decisions_site_product_flow", "decisions", ["site_id", "product_key", "flow_key"]
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="QUEUED", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("lease_owner", sa.String(200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_jobs_site_id_sites", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
    )
    op.create_index("ix_jobs_site_status_created", "jobs", ["site_id", "status", "created_at"])
    op.create_table(
        "import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adapter", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(300), nullable=False),
        sa.Column("source_revision", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), server_default="QUEUED", nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_import_runs_site_id_sites", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_import_runs_job_id_jobs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_import_runs"),
        sa.UniqueConstraint("job_id", name="uq_import_runs_job_id"),
    )
    op.create_foreign_key(
        "fk_review_queue_items_import_run_id_import_runs",
        "review_queue_items",
        "import_runs",
        ["import_run_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "candidate_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_key", sa.String(200), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), server_default="PENDING_REVIEW", nullable=False),
        sa.Column("promoted_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name="fk_candidate_decisions_site_id_sites",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"],
            ["import_runs.id"],
            name="fk_candidate_decisions_import_run_id_import_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["promoted_revision_id"],
            ["decision_revisions.id"],
            name="fk_candidate_decisions_promoted_revision_id_decision_revisions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_decisions"),
        sa.UniqueConstraint(
            "import_run_id", "decision_key", name="uq_candidate_decisions_import_run_id"
        ),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "artifact_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_artifacts_site_id_sites", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_artifacts_job_id_jobs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )
    op.create_table(
        "delivery_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("branch", sa.String(300), nullable=False),
        sa.Column("external_url", sa.String(1000), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_delivery_records_site_id_sites", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_delivery_records_job_id_jobs", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["decision_revision_id"],
            ["decision_revisions.id"],
            name="fk_delivery_records_decision_revision_id_decision_revisions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_delivery_records"),
    )


def downgrade() -> None:
    op.drop_table("delivery_records")
    op.drop_table("artifacts")
    op.drop_table("candidate_decisions")
    op.drop_constraint(
        "fk_review_queue_items_import_run_id_import_runs", "review_queue_items", type_="foreignkey"
    )
    op.drop_table("import_runs")
    op.drop_index("ix_jobs_site_status_created", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_decisions_site_product_flow", table_name="decisions")
    op.drop_constraint("uq_decisions_site_id", "decisions", type_="unique")
    op.create_unique_constraint("uq_decisions_decision_key", "decisions", ["decision_key"])
    op.drop_column("decisions", "flow_key")
    op.drop_column("decisions", "product_key")
    op.drop_column("review_queue_items", "import_run_id")
    for table in ("lookup_snapshots", "ingestion_fingerprints", "review_queue_items", "decisions"):
        op.drop_constraint(f"fk_{table}_site_id_sites", table, type_="foreignkey")
        op.drop_column(table, "site_id")
    op.drop_table("site_profile_revisions")
    op.drop_table("sites")
    op.drop_table("workspaces")
