"""audit events table and JWT policy fields

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("admin_tenants.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("route_id", sa.String(36), nullable=True, index=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("upstream_url", sa.Text, nullable=False, server_default=""),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("client_ip", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )

    for table in ("admin_policies", "admin_domain_policies"):
        op.add_column(table, sa.Column("jwt_validate_exp", sa.Boolean(), nullable=False, server_default="true"))
        op.add_column(table, sa.Column("jwt_issuer", sa.String(255), nullable=True))
        op.add_column(table, sa.Column("jwt_audience", sa.String(255), nullable=True))
        op.add_column(table, sa.Column("jwt_clock_skew_seconds", sa.Integer(), nullable=False, server_default="30"))


def downgrade() -> None:
    for table in ("admin_domain_policies", "admin_policies"):
        op.drop_column(table, "jwt_clock_skew_seconds")
        op.drop_column(table, "jwt_audience")
        op.drop_column(table, "jwt_issuer")
        op.drop_column(table, "jwt_validate_exp")
    op.drop_table("admin_audit_requests")
