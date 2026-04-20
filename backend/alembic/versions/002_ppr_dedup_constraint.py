"""Add unique constraint on ppr_sales (address, date_of_sale, price_eur) to prevent duplicate ingestion.

Revision ID: 002
Revises: 001
Create Date: 2026-04-20
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_ppr_sales_dedup",
        "ppr_sales",
        ["address", "date_of_sale", "price_eur"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_ppr_sales_dedup", table_name="ppr_sales")
