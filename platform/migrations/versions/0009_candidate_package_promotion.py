"""Link evidence-agent candidates to governed canonical package revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_candidate_package_promotion"
down_revision = "0008_canonical_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_decisions",
        sa.Column(
            "promoted_package_revision_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_candidate_promoted_package_revision",
        "candidate_decisions",
        "canonical_package_revisions",
        ["promoted_package_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_candidate_promoted_package_revision",
        "candidate_decisions",
        type_="foreignkey",
    )
    op.drop_column("candidate_decisions", "promoted_package_revision_id")
