"""Add immutable Mode-A publication history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_mode_a_publications"
down_revision = "0003_golden_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mode_a_publications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("decision_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=200), nullable=False),
        sa.Column("previous_publication_id", sa.BigInteger(), nullable=True),
        sa.Column("source_publication_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_hash", sa.String(length=64), nullable=False),
        sa.Column("suite_hash", sa.String(length=64), nullable=False),
        sa.Column("jdm_hash", sa.String(length=64), nullable=False),
        sa.Column("jdm_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "lookup_snapshot_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["decision_revision_id"],
            ["decision_revisions.id"],
            name="fk_mode_a_pub_decision_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["suite_revision_id"],
            ["golden_suite_revisions.id"],
            name="fk_mode_a_pub_suite_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_publication_id"],
            ["mode_a_publications.id"],
            name="fk_mode_a_pub_previous",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_publication_id"],
            ["mode_a_publications.id"],
            name="fk_mode_a_pub_source",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mode_a_publications"),
    )
    op.create_index(
        "ix_mode_a_publications_channel_id",
        "mode_a_publications",
        ["channel", "id"],
    )
    op.execute(
        """
        CREATE TRIGGER mode_a_publications_immutable
          BEFORE UPDATE OR DELETE ON mode_a_publications
          FOR EACH ROW EXECUTE FUNCTION brp_reject_immutable_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS mode_a_publications_immutable ON mode_a_publications")
    op.drop_index("ix_mode_a_publications_channel_id", table_name="mode_a_publications")
    op.drop_table("mode_a_publications")
