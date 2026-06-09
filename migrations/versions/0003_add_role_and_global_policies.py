"""add role to users and global_policies table

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("role", sa.String(20), nullable=False, server_default="admin"),
    )
    op.create_table(
        "admin_global_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("admin_tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("requires_auth", sa.Boolean, nullable=False, default=False),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=True),
        sa.Column("allowed_roles", sa.Text, nullable=False, default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_global_policies")
    op.drop_column("admin_users", "role")