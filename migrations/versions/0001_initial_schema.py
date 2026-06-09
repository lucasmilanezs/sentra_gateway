"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22

Cria as tabelas iniciais do plano Admin:
  - admin_tenants
  - admin_users
  - admin_routes
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("alias", sa.String(128), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
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
    op.create_index("ix_admin_tenants_alias", "admin_tenants", ["alias"], unique=True)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("admin_tenants.id"), nullable=True),
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
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)

    op.create_table(
        "admin_routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("admin_tenants.id"),
            nullable=False,
        ),
        sa.Column("path_pattern", sa.String(512), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("backend_url", sa.Text, nullable=False),
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
    op.create_index(
        "ix_admin_routes_tenant_id", "admin_routes", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("admin_routes")
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_index("ix_admin_tenants_alias", table_name="admin_tenants")
    op.drop_table("admin_tenants")