"""add tenant_domains table and migrate routes.method to methods

Revision ID: 0004
Revises: 0003
Create Date: 2026-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Tabela de domains do tenant (1-N com admin_tenants)
    op.create_table(
        "admin_tenant_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("admin_tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Política global vinculada ao domain (não mais ao tenant diretamente)
    op.create_table(
        "admin_domain_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "domain_id",
            sa.String(36),
            sa.ForeignKey("admin_tenant_domains.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("requires_auth", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("rate_limit_per_minute", sa.Integer, nullable=True),
        sa.Column("allowed_roles", sa.Text, nullable=False, server_default=""),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # 3. Renomeia method → methods em admin_routes e migra dados existentes
    op.add_column(
        "admin_routes",
        sa.Column("methods", sa.Text, nullable=True),
    )
    # Migra dados existentes: copia valor de method para methods
    op.execute("UPDATE admin_routes SET methods = method WHERE methods IS NULL")
    op.alter_column("admin_routes", "methods", nullable=False)
    op.drop_column("admin_routes", "method")

    # 4. Migra Tenant.domain existente para admin_tenant_domains
    # (preserva dados de quem já tinha domain cadastrado)
    op.execute("""
        INSERT INTO admin_tenant_domains (id, tenant_id, domain, created_at, updated_at)
        SELECT
            concat('migrated-', id),
            id,
            domain,
            created_at,
            updated_at
        FROM admin_tenants
        WHERE domain IS NOT NULL AND domain != ''
    """)

    # 5. Remove coluna domain do tenant (agora gerenciada via admin_tenant_domains)
    op.drop_column("admin_tenants", "domain")


def downgrade() -> None:
    op.add_column(
        "admin_tenants",
        sa.Column("domain", sa.String(255), nullable=True),
    )
    op.execute("""
        UPDATE admin_tenants t
        SET domain = (
            SELECT domain FROM admin_tenant_domains d
            WHERE d.tenant_id = t.id
            LIMIT 1
        )
    """)
    op.add_column(
        "admin_routes",
        sa.Column("method", sa.String(16), nullable=True),
    )
    op.execute("UPDATE admin_routes SET method = split_part(methods, ',', 1)")
    op.alter_column("admin_routes", "method", nullable=False)
    op.drop_column("admin_routes", "methods")
    op.drop_table("admin_domain_policies")
    op.drop_table("admin_tenant_domains")
