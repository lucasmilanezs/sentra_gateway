"""add permissions column to admin_users

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-19

Adiciona coluna permissions (Text, comma-separated) à tabela admin_users.
Usuários existentes recebem string vazia — comportamento correto, pois
superuser e admin têm acesso total implícito independente deste campo.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column(
            "permissions",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "permissions")