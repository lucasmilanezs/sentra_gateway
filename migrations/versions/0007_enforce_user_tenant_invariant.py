"""enforce user-tenant invariant

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19

Adiciona CHECK constraint em admin_users para garantir a invariante:
  (role = 'superuser' AND tenant_id IS NULL)
  OR
  (role <> 'superuser' AND tenant_id IS NOT NULL)

Antes de criar a constraint, faz limpeza de dados inconsistentes —
admins/members existentes sem tenant_id são removidos, pois violam
a invariante e não há tenant ao qual associá-los retroativamente.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Limpeza preventiva: remove usuários inconsistentes que violariam a
    # constraint. Em projeto acadêmico isso é seguro; em produção real
    # seria necessário backfill associativo.
    op.execute(
        """
        DELETE FROM admin_users
        WHERE role <> 'superuser' AND tenant_id IS NULL
        """
    )

    # Adiciona a CHECK constraint
    op.create_check_constraint(
        constraint_name="ck_users_role_tenant_consistency",
        table_name="admin_users",
        condition=(
            "(role = 'superuser' AND tenant_id IS NULL) "
            "OR (role <> 'superuser' AND tenant_id IS NOT NULL)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        constraint_name="ck_users_role_tenant_consistency",
        table_name="admin_users",
        type_="check",
    )