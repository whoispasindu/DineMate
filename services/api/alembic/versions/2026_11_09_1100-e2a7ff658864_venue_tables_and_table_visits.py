"""venue tables and table visits

Revision ID: e2a7ff658864
Revises: 8c3f2a71d0b4
Create Date: 2026-11-09 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2a7ff658864"
down_revision: str | Sequence[str] | None = "8c3f2a71d0b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "venue_tables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.String(length=40), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("shape", sa.Text(), server_default="rect", nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("w", sa.Float(), nullable=False),
        sa.Column("h", sa.Float(), nullable=False),
        sa.Column("seat_ids", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("shape IN ('round', 'rect')", name=op.f("ck_venue_tables_shape")),
        sa.CheckConstraint("cardinality(seat_ids) BETWEEN 1 AND 20", name=op.f("ck_venue_tables_seat_count")),
        sa.CheckConstraint(
            "x >= 0 AND y >= 0 AND w > 0 AND h > 0 AND x + w <= 1 AND y + h <= 1",
            name=op.f("ck_venue_tables_inside_floor"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["canteens.id"], name=op.f("fk_venue_tables_venue_id_canteens"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["seating_zones.id"], name=op.f("fk_venue_tables_zone_id_seating_zones"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venue_tables")),
        sa.UniqueConstraint("venue_id", "name", name="uq_venue_tables_venue_name"),
    )
    op.create_index(op.f("ix_venue_tables_venue_id"), "venue_tables", ["venue_id"], unique=False)
    op.create_table(
        "table_visits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name=op.f("ck_table_visits_ends_after_start")),
        sa.CheckConstraint("party_size > 0", name=op.f("ck_table_visits_party_size")),
        sa.ForeignKeyConstraint(
            ["table_id"], ["venue_tables.id"], name=op.f("fk_table_visits_table_id_venue_tables"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_table_visits")),
    )
    op.create_index("ix_table_visits_table_started", "table_visits", ["table_id", "started_at"], unique=False)
    op.create_index(
        "one_open_visit_per_table",
        "table_visits",
        ["table_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("one_open_visit_per_table", table_name="table_visits", postgresql_where=sa.text("ended_at IS NULL"))
    op.drop_index("ix_table_visits_table_started", table_name="table_visits")
    op.drop_table("table_visits")
    op.drop_index(op.f("ix_venue_tables_venue_id"), table_name="venue_tables")
    op.drop_table("venue_tables")
