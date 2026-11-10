"""login throttles

Revision ID: 7b3e9c41d2a6
Revises: 5d1c7e9a2b40
Create Date: 2026-11-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7b3e9c41d2a6"
down_revision: str | Sequence[str] | None = "5d1c7e9a2b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("failures", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_login_throttles")),
    )


def downgrade() -> None:
    op.drop_table("login_throttles")
