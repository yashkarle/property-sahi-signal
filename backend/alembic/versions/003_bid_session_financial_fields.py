"""Add user_aip, user_savings, actual_sale_price to bid_sessions.

Revision ID: 003
Revises: 002
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bid_sessions", sa.Column("user_aip", sa.Integer(), nullable=True))
    op.add_column("bid_sessions", sa.Column("user_savings", sa.Integer(), nullable=True))
    op.add_column("bid_sessions", sa.Column("actual_sale_price", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("bid_sessions", "actual_sale_price")
    op.drop_column("bid_sessions", "user_savings")
    op.drop_column("bid_sessions", "user_aip")
