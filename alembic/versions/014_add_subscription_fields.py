"""Add subscription plan fields to tenants.

Revision ID: 014
Revises: 013
Create Date: 2026-02-17

Adds:
- plan enum column (light, pro, life) defaulting to pro
- subscription_status enum column (trialing, active, past_due, cancelled) defaulting to trialing
- trial_ends_at datetime column
- max_users_override integer column
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add subscription fields to tenants."""
    op.add_column(
        "tenants",
        sa.Column(
            "plan",
            sa.Enum("light", "pro", "life", name="plantier"),
            nullable=False,
            server_default="pro",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "subscription_status",
            sa.Enum("trialing", "active", "past_due", "cancelled", name="subscriptionstatus"),
            nullable=False,
            server_default="trialing",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("max_users_override", sa.Integer(), nullable=True),
    )

    # Give all existing tenants a 6-month trial from now
    op.execute(
        "UPDATE tenants SET trial_ends_at = DATE_ADD(NOW(), INTERVAL 6 MONTH) WHERE trial_ends_at IS NULL"
    )


def downgrade() -> None:
    """Remove subscription fields from tenants."""
    op.drop_column("tenants", "max_users_override")
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "plan")
