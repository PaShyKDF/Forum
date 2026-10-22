"""direct chats and messages

Revision ID: 20260407_0001
Revises:
Create Date: 2026-04-07 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260407_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'directchat',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_low_id', sa.Uuid(), nullable=False),
        sa.Column('user_high_id', sa.Uuid(), nullable=False),
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_high_id'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_low_id'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_low_id',
            'user_high_id',
            name='uq_directchat_pair',
        ),
    )
    op.create_index(
        op.f('ix_directchat_id'),
        'directchat',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_directchat_user_high_id'),
        'directchat',
        ['user_high_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_directchat_user_low_id'),
        'directchat',
        ['user_low_id'],
        unique=False,
    )

    op.create_table(
        'directmessage',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=False),
        sa.Column(
            'kind',
            sa.String(length=32),
            server_default='text',
            nullable=False,
        ),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['chat_id'],
            ['directchat.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['sender_id'],
            ['user.uid'],
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_directmessage_chat_id'),
        'directmessage',
        ['chat_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_directmessage_id'),
        'directmessage',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_directmessage_sender_id'),
        'directmessage',
        ['sender_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_directmessage_sender_id'),
        table_name='directmessage',
    )
    op.drop_index(
        op.f('ix_directmessage_id'),
        table_name='directmessage',
    )
    op.drop_index(
        op.f('ix_directmessage_chat_id'),
        table_name='directmessage',
    )
    op.drop_table('directmessage')
    op.drop_index(
        op.f('ix_directchat_user_low_id'),
        table_name='directchat',
    )
    op.drop_index(
        op.f('ix_directchat_user_high_id'),
        table_name='directchat',
    )
    op.drop_index(
        op.f('ix_directchat_id'),
        table_name='directchat',
    )
    op.drop_table('directchat')
