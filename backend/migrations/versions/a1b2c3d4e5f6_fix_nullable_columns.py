"""fix_nullable_columns

Revision ID: a1b2c3d4e5f6
Revises: f00f11f7c1a2
Create Date: 2026-02-10 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f00f11f7c1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make store_url and error_reason nullable."""
    # Alter store_url to be nullable
    op.alter_column('stores', 'store_url',
               existing_type=sa.Text(),
               nullable=True)
    
    # Alter error_reason to be nullable
    op.alter_column('stores', 'error_reason',
               existing_type=sa.Text(),
               nullable=True)
    
    # Also fix provisioning_steps.last_error to be nullable
    op.alter_column('provisioning_steps', 'last_error',
               existing_type=sa.Text(),
               nullable=True)


def downgrade() -> None:
    """Revert nullable columns."""
    # Note: This may fail if there are NULL values
    op.alter_column('stores', 'store_url',
               existing_type=sa.Text(),
               nullable=False)
    
    op.alter_column('stores', 'error_reason',
               existing_type=sa.Text(),
               nullable=False)
    
    op.alter_column('provisioning_steps', 'last_error',
               existing_type=sa.Text(),
               nullable=False)
