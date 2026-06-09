"""policy auth modes and encrypted signing material

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _add_policy_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("auth_mode", sa.String(length=32), nullable=False, server_default="none"))
    op.add_column(table_name, sa.Column("jwt_signing_algorithm", sa.String(length=32), nullable=True))
    op.add_column(table_name, sa.Column("jwt_signing_key_encrypted", sa.Text(), nullable=True))
    op.add_column(table_name, sa.Column("jwt_signing_key_hint", sa.String(length=32), nullable=True))


def _drop_policy_columns(table_name: str) -> None:
    op.drop_column(table_name, "jwt_signing_key_hint")
    op.drop_column(table_name, "jwt_signing_key_encrypted")
    op.drop_column(table_name, "jwt_signing_algorithm")
    op.drop_column(table_name, "auth_mode")


def upgrade() -> None:
    _add_policy_columns("admin_policies")
    _add_policy_columns("admin_domain_policies")

    # Preserve previous behavior as a pre-validation mode, without assuming the
    # gateway is responsible for contractor-side session/role authorization.
    op.execute("""
        UPDATE admin_policies
        SET auth_mode = CASE
            WHEN requires_auth = FALSE THEN 'none'
            WHEN jwt_validate_exp = TRUE THEN 'jwt_claims'
            ELSE 'jwt_structural'
        END
    """)
    op.execute("""
        UPDATE admin_domain_policies
        SET auth_mode = CASE
            WHEN requires_auth = FALSE THEN 'none'
            WHEN jwt_validate_exp = TRUE THEN 'jwt_claims'
            ELSE 'jwt_structural'
        END
    """)


def downgrade() -> None:
    _drop_policy_columns("admin_domain_policies")
    _drop_policy_columns("admin_policies")
