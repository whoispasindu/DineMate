"""anonymous counter count

Revision ID: c41f8a2d6e93
Revises: 7b3e9c41d2a6
Create Date: 2026-11-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c41f8a2d6e93"
down_revision: str | Sequence[str] | None = "7b3e9c41d2a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("queue_readings", sa.Column("counter_people", sa.Integer(), nullable=True))
    op.alter_column("queue_readings", "people", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM queue_readings WHERE people IS NULL")
    op.alter_column("queue_readings", "people", existing_type=sa.Integer(), nullable=False)
    op.drop_column("queue_readings", "counter_people")
