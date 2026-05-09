"""add admin_policies table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"  # ajuste para o ID da última migration existente
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "route_id",
            sa.String(36),
            sa.ForeignKey("admin_routes.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("requires_auth", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("allowed_roles", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_policies")