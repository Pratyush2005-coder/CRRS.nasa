"""add_session_fields_to_refresh_tokens

Revision ID: 846343d05df3
Revises: a29c5da3e7fb
Create Date: 2026-11-05 12:02:32.669355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '846343d05df3'
down_revision: Union[str, Sequence[str], None] = 'a29c5da3e7fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add session metadata fields to refresh_tokens table."""
    # Add session_id field for stable session identification across token rotations
    op.add_column(
        'refresh_tokens',
        sa.Column('session_id', sa.String(36), nullable=True, index=True)
    )

    # Add device/browser information
    op.add_column(
        'refresh_tokens',
        sa.Column('device_info', sa.String(512), nullable=True)
    )

    # Add client IP address
    op.add_column(
        'refresh_tokens',
        sa.Column('ip_address', sa.String(45), nullable=True)  # IPv6 max length is 45
    )

    # Add last_used_at timestamp for session activity tracking
    op.add_column(
        'refresh_tokens',
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema - remove session metadata fields from refresh_tokens table."""
    # Drop index first (required for SQLite)
    op.drop_index('ix_refresh_tokens_session_id', table_name='refresh_tokens')
    op.drop_column('refresh_tokens', 'last_used_at')
    op.drop_column('refresh_tokens', 'ip_address')
    op.drop_column('refresh_tokens', 'device_info')
    op.drop_column('refresh_tokens', 'session_id')