"""add_origin_host_to_connection_oauth_states

Revision ID: d5e3f9a21b8c
Revises: c4d2e8f10a7b
Create Date: 2026-04-24 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e3f9a21b8c'
down_revision: Union[str, None] = 'c4d2e8f10a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('connection_oauth_states') as batch_op:
        batch_op.add_column(sa.Column('origin_host', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('connection_oauth_states') as batch_op:
        batch_op.drop_column('origin_host')
