"""Add shortname column to stocks table.

Revision ID: 011
Revises: 010
Create Date: 2026-02-11

Adds:
- shortname column (String 255, nullable) for human-readable phenotype summary
- Index on shortname for search (prefix index like genotype)
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add shortname column to stocks table."""
    op.add_column("stocks", sa.Column("shortname", sa.String(255), nullable=True))
    op.create_index("ix_stocks_shortname", "stocks", ["shortname"], mysql_length=100)


def downgrade() -> None:
    """Remove shortname column from stocks table."""
    op.drop_index("ix_stocks_shortname", table_name="stocks")
    op.drop_column("stocks", "shortname")
