"""seat states, seat sessions and zone seat status

Revision ID: 5b1e0c7d9a24
Revises: 119a6cbf1762
Create Date: 2026-11-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b1e0c7d9a24"
down_revision: str | Sequence[str] | None = "119a6cbf1762"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEAT_STATES = "state IN ('free', 'occupied', 'held', 'unknown')"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "seat_states",
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("free_soon", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(SEAT_STATES, name=op.f("ck_seat_states_state")),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["seating_zones.id"], name=op.f("fk_seat_states_zone_id_seating_zones"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("zone_id", "seat_id", name=op.f("pk_seat_states")),
    )
    op.create_table(
        "seat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(SEAT_STATES, name=op.f("ck_seat_sessions_state")),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["seating_zones.id"], name=op.f("fk_seat_sessions_zone_id_seating_zones"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seat_sessions")),
    )
    op.create_index("ix_seat_sessions_zone_started", "seat_sessions", ["zone_id", "started_at"], unique=False)
    op.create_index(
        "ix_seat_sessions_open",
        "seat_sessions",
        ["zone_id", "seat_id"],
        unique=False,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "zone_seat_status",
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("free", sa.Integer(), nullable=False),
        sa.Column("occupied", sa.Integer(), nullable=False),
        sa.Column("held", sa.Integer(), nullable=False),
        sa.Column("unknown", sa.Integer(), nullable=False),
        sa.Column("free_soon", sa.Integer(), server_default="0", nullable=False),
        sa.Column("standing", sa.Integer(), server_default="0", nullable=False),
        sa.Column("crowded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "free >= 0 AND occupied >= 0 AND held >= 0 AND unknown >= 0",
            name=op.f("ck_zone_seat_status_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"], ["devices.id"], name=op.f("fk_zone_seat_status_device_id_devices"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["seating_zones.id"],
            name=op.f("fk_zone_seat_status_zone_id_seating_zones"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("zone_id", name=op.f("pk_zone_seat_status")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("zone_seat_status")
    op.drop_index("ix_seat_sessions_open", table_name="seat_sessions", postgresql_where=sa.text("ended_at IS NULL"))
    op.drop_index("ix_seat_sessions_zone_started", table_name="seat_sessions")
    op.drop_table("seat_sessions")
    op.drop_table("seat_states")
