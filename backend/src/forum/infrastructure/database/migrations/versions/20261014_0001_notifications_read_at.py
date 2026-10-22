"""notifications and directmessage read_at

Revision ID: 20261014_0001
Revises: 327667fe705e
Create Date: 2026-10-14 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20261014_0001'
down_revision: Union[str, None] = '327667fe705e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'directmessage',
        sa.Column('read_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f('ix_directmessage_read_at'),
        'directmessage',
        ['read_at'],
        unique=False,
    )

    op.create_table(
        'topicnotification',
        sa.Column(
            'id',
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column('recipient_id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('topic_id', sa.BigInteger(), nullable=False),
        sa.Column('post_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'source_post_id',
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
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
            ['actor_id'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['post_id'],
            ['post.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['recipient_id'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['source_post_id'],
            ['post.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['topic_id'],
            ['topic.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_topicnotification_id'),
        'topicnotification',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_recipient_id'),
        'topicnotification',
        ['recipient_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_actor_id'),
        'topicnotification',
        ['actor_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_topic_id'),
        'topicnotification',
        ['topic_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_post_id'),
        'topicnotification',
        ['post_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_source_post_id'),
        'topicnotification',
        ['source_post_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_kind'),
        'topicnotification',
        ['kind'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topicnotification_read_at'),
        'topicnotification',
        ['read_at'],
        unique=False,
    )
    op.create_index(
        'ix_topicnotification_recipient_unread',
        'topicnotification',
        ['recipient_id', 'is_active', 'read_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_topicnotification_recipient_unread',
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_read_at'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_kind'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_source_post_id'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_post_id'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_topic_id'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_actor_id'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_recipient_id'),
        table_name='topicnotification',
    )
    op.drop_index(
        op.f('ix_topicnotification_id'),
        table_name='topicnotification',
    )
    op.drop_table('topicnotification')

    op.drop_index(
        op.f('ix_directmessage_read_at'),
        table_name='directmessage',
    )
    op.drop_column('directmessage', 'read_at')
