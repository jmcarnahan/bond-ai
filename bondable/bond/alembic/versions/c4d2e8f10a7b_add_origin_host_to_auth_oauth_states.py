"""add_origin_host_to_auth_oauth_states

Revision ID: c4d2e8f10a7b
Revises: b7e2d4f1a093
Create Date: 2026-04-24 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d2e8f10a7b'
down_revision: Union[str, None] = 'b7e2d4f1a093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('auth_oauth_states') as batch_op:
        batch_op.add_column(sa.Column('origin_host', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('auth_oauth_states') as batch_op:
        batch_op.drop_column('origin_host')
