"""add owner_id foreign key to farms table

Revision ID: 21ff1745e9fa
Revises: dddcbfadde78
Create Date: 2026-11-03 19:32:20.702627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21ff1745e9fa'
down_revision: Union[str, Sequence[str], None] = 'dddcbfadde78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('farms') as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_farms_owner_id', ['owner_id'], unique=False)
        batch_op.create_foreign_key('fk_farms_owner_id_users', 'users', ['owner_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('farms') as batch_op:
        batch_op.drop_constraint('fk_farms_owner_id_users', type_='foreignkey')
        batch_op.drop_index('ix_farms_owner_id')
        batch_op.drop_column('owner_id')
