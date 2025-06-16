"""merge heads

Revision ID: f3006b1e58db
Revises: abaf549f61fb, 1a2b3c4d5e6f
Create Date: 2025-06-11 14:38:44.326155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3006b1e58db'
down_revision: Union[str, None] = ('abaf549f61fb', '1a2b3c4d5e6f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
