"""baseline: create farms and users tables

Revision ID: 63e13e54603a
Revises:
Create Date: 2026-11-03 18:40:37.150391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63e13e54603a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create tables matching current database state."""
    # Create farms table
    op.create_table(
        'farms',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('farmer_name', sa.String(100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('elevation_m', sa.Float(), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('total_area_hectares', sa.Float(), nullable=False),
        sa.Column('soil_type', sa.String(50), nullable=False),
        sa.Column('soil_ph', sa.Float(), nullable=True),
        sa.Column('organic_matter_pct', sa.Float(), nullable=True),
        sa.Column('primary_irrigation', sa.String(50), nullable=False, server_default='rainfed'),
        sa.Column('current_crop', sa.String(100), nullable=True),
        sa.Column('current_crop_planting_date', sa.Date(), nullable=True),
        sa.Column('previous_crops', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_farms_name', 'farms', ['name'], unique=False)
    op.create_index('ix_farms_farmer_name', 'farms', ['farmer_name'], unique=False)
    op.create_index('ix_farms_region', 'farms', ['region'], unique=False)
    op.create_index('ix_farms_id', 'farms', ['id'], unique=False)

    # Create users table (matching current schema with VARCHAR(5) for is_active)
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active', sa.String(5), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_id', 'users', ['id'], unique=False)

    # Create alembic_version table (will be managed by Alembic)
    # Note: This is created automatically by Alembic on first migration


def downgrade() -> None:
    """Downgrade schema - drop tables."""
    op.drop_index('ix_users_id', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_farms_id', table_name='farms')
    op.drop_index('ix_farms_region', table_name='farms')
    op.drop_index('ix_farms_farmer_name', table_name='farms')
    op.drop_index('ix_farms_name', table_name='farms')
    op.drop_table('farms')