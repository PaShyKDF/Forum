"""user_guest_fields

Revision ID: 7f0e62fca510
Revises: 8e485f966a28
Create Date: 2026-10-12 10:46:31.824259
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f0e62fca510'
down_revision: Union[str, None] = '8e485f966a28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user',
        sa.Column(
            'anon_id',
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        'user',
        sa.Column(
            'is_guest',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )
    op.add_column(
        'user',
        sa.Column(
            'registered_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.create_index(
        op.f('ix_user_anon_id'),
        'user',
        ['anon_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_user_anon_id'),
        table_name='user',
    )
    op.drop_column('user', 'registered_at')
    op.drop_column('user', 'is_guest')
    op.drop_column('user', 'anon_id')
