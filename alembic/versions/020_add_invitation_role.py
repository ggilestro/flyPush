"""Add role column to invitations table.

Revision ID: 020
Revises: 019
Create Date: 2026-02-19

Adds an optional 'role' column to the invitations table so admins can
specify the invitee's role (user or lab_manager) at invitation time.
"""

from alembic import op

# revision identifiers
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE invitations ADD COLUMN role VARCHAR(20) NULL AFTER organization_id")


def downgrade() -> None:
    op.execute("ALTER TABLE invitations DROP COLUMN role")
