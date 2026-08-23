"""add hidden_from_patient to workflow_runs

Revision ID: a1b2c3d4e5f6
Revises: 77dfebdfb8fb
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '77dfebdfb8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workflow_runs', sa.Column('hidden_from_patient', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('workflow_runs', 'hidden_from_patient')
