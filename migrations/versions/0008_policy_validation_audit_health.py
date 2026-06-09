"""policy validation fields, audit enrichment, change audit table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("admin_policies", "admin_domain_policies"):
        op.add_column(table, sa.Column("required_headers", sa.Text(), nullable=False, server_default=""))
        op.add_column(table, sa.Column("forbidden_headers", sa.Text(), nullable=False, server_default=""))
        op.add_column(table, sa.Column("required_params", sa.Text(), nullable=False, server_default=""))
        op.add_column(table, sa.Column("forbidden_params", sa.Text(), nullable=False, server_default=""))

    op.add_column("admin_audit_requests", sa.Column("outcome", sa.String(64), nullable=False, server_default="SUCCESS"))
    op.add_column("admin_audit_requests", sa.Column("denial_reason", sa.Text(), nullable=True))
    op.add_column("admin_audit_requests", sa.Column("denial_check", sa.String(64), nullable=True))

    op.create_table(
        "admin_change_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("admin_tenants.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("resource_summary", sa.String(512), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("admin_change_audit")
    op.drop_column("admin_audit_requests", "denial_check")
    op.drop_column("admin_audit_requests", "denial_reason")
    op.drop_column("admin_audit_requests", "outcome")
    for table in ("admin_domain_policies", "admin_policies"):
        op.drop_column(table, "forbidden_params")
        op.drop_column(table, "required_params")
        op.drop_column(table, "forbidden_headers")
        op.drop_column(table, "required_headers")
