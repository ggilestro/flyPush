"""Add Paddle billing fields to tenants and 'free' to plan enum.

Revision ID: 015
Revises: 014
Create Date: 2026-02-17

Adds:
- paddle_customer_id String(50) indexed
- paddle_subscription_id String(50) indexed
- paddle_subscription_scheduled_change JSON
- 'free' value to plantier enum
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Paddle billing columns and extend plan enum."""
    # Extend the plantier enum to include 'free'
    op.execute(
        "ALTER TABLE tenants MODIFY COLUMN plan ENUM('free','light','pro','life') NOT NULL DEFAULT 'pro'"
    )

    op.add_column(
        "tenants",
        sa.Column("paddle_customer_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("paddle_subscription_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("paddle_subscription_scheduled_change", sa.JSON(), nullable=True),
    )
    op.create_index("ix_tenants_paddle_customer_id", "tenants", ["paddle_customer_id"])
    op.create_index("ix_tenants_paddle_subscription_id", "tenants", ["paddle_subscription_id"])


def downgrade() -> None:
    """Remove Paddle billing columns and revert plan enum."""
    op.drop_index("ix_tenants_paddle_subscription_id", table_name="tenants")
    op.drop_index("ix_tenants_paddle_customer_id", table_name="tenants")
    op.drop_column("tenants", "paddle_subscription_scheduled_change")
    op.drop_column("tenants", "paddle_subscription_id")
    op.drop_column("tenants", "paddle_customer_id")

    # Revert enum (any 'free' rows would need to be updated first)
    op.execute("UPDATE tenants SET plan = 'light' WHERE plan = 'free'")
    op.execute(
        "ALTER TABLE tenants MODIFY COLUMN plan ENUM('light','pro','life') NOT NULL DEFAULT 'pro'"
    )
