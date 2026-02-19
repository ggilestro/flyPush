"""Add collaborator to invitation_type enum.

Revision ID: 017
Revises: 016
Create Date: 2026-02-18

Adds 'collaborator' value to the invitation_type ENUM column on the
invitations table so labs can invite external users as collaborators.
"""

from alembic import op

# revision identifiers
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE invitations MODIFY COLUMN invitation_type "
        "ENUM('lab_member', 'new_tenant', 'collaborator') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE invitations MODIFY COLUMN invitation_type "
        "ENUM('lab_member', 'new_tenant') NOT NULL"
    )
