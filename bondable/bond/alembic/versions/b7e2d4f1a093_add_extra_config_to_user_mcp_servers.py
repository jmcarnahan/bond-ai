"""add_extra_config_to_user_mcp_servers

Revision ID: b7e2d4f1a093
Revises: a3f1c8d92b4e
Create Date: 2026-04-08 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2d4f1a093'
down_revision: Union[str, None] = 'a3f1c8d92b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_mcp_servers') as batch_op:
        batch_op.add_column(sa.Column('extra_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user_mcp_servers') as batch_op:
        batch_op.drop_column('extra_config')
