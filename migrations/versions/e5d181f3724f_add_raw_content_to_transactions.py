"""add raw_content to transactions

Revision ID: e5d181f3724f
Revises: 50847ff1dcd5
Create Date: 2026-01-10 23:48:52.905028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5d181f3724f'
down_revision: Union[str, Sequence[str], None] = '50847ff1dcd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'transactions',
        sa.Column('raw_content', sa.Text(), nullable=True)
    )

def downgrade():
    op.drop_column('transactions', 'raw_content')

