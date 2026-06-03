"""add route display color

Revision ID: 0010_add_route_display_color
Revises: 0009
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_add_route_display_color"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("admin_routes", sa.Column("display_color", sa.String(length=7), nullable=False, server_default="#2dd4bf"))

def downgrade() -> None:
    op.drop_column("admin_routes", "display_color")
