"""add_user_mcp_servers

Revision ID: a3f1c8d92b4e
Revises: 2731cf82e217
Create Date: 2026-04-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c8d92b4e'
down_revision: Union[str, None] = '2731cf82e217'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_mcp_servers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('owner_user_id', sa.String(), nullable=False),
        sa.Column('server_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('transport', sa.String(), nullable=False, server_default='streamable-http'),
        sa.Column('auth_type', sa.String(), nullable=False, server_default='none'),
        sa.Column('headers_encrypted', sa.String(), nullable=True),
        sa.Column('oauth_config_encrypted', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_user_id', 'server_name', name='_user_mcp_server_name_uc'),
    )
    op.create_index(op.f('ix_user_mcp_servers_owner_user_id'), 'user_mcp_servers', ['owner_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_mcp_servers_owner_user_id'), table_name='user_mcp_servers')
    op.drop_table('user_mcp_servers')
