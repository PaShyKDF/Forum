"""content_acl_is_restricted

Revision ID: 327667fe705e
Revises: 7f0e62fca510
Create Date: 2026-10-12 16:54:18.515489
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '327667fe705e'
down_revision: Union[str, None] = '7f0e62fca510'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'category_user_access',
        sa.Column(
            'category_id',
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            'user_uid',
            sa.Uuid(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['category_id'],
            ['category.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_uid'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'category_id',
            'user_uid',
            name='pk_category_user_access',
        ),
    )
    op.create_index(
        op.f('ix_category_user_access_category_id'),
        'category_user_access',
        ['category_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_category_user_access_user_uid'),
        'category_user_access',
        ['user_uid'],
        unique=False,
    )
    op.create_table(
        'topic_user_access',
        sa.Column(
            'topic_id',
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            'user_uid',
            sa.Uuid(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['topic_id'],
            ['topic.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_uid'],
            ['user.uid'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'topic_id',
            'user_uid',
            name='pk_topic_user_access',
        ),
    )
    op.create_index(
        op.f('ix_topic_user_access_topic_id'),
        'topic_user_access',
        ['topic_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_topic_user_access_user_uid'),
        'topic_user_access',
        ['user_uid'],
        unique=False,
    )
    op.add_column(
        'category',
        sa.Column(
            'is_restricted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )
    op.add_column(
        'topic',
        sa.Column(
            'is_restricted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('topic', 'is_restricted')
    op.drop_column('category', 'is_restricted')
    op.drop_index(
        op.f('ix_topic_user_access_user_uid'),
        table_name='topic_user_access',
    )
    op.drop_index(
        op.f('ix_topic_user_access_topic_id'),
        table_name='topic_user_access',
    )
    op.drop_table('topic_user_access')
    op.drop_index(
        op.f('ix_category_user_access_user_uid'),
        table_name='category_user_access',
    )
    op.drop_index(
        op.f('ix_category_user_access_category_id'),
        table_name='category_user_access',
    )
    op.drop_table('category_user_access')
