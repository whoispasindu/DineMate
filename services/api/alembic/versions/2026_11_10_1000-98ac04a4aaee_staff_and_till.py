"""staff and till

Revision ID: 98ac04a4aaee
Revises: e2a7ff658864
Create Date: 2026-11-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "98ac04a4aaee"
down_revision: str | Sequence[str] | None = "e2a7ff658864"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "queue_readings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("venue_id", sa.String(length=40), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("people", sa.Integer(), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("people >= 0", name=op.f("ck_queue_readings_non_negative")),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["canteens.id"], name=op.f("fk_queue_readings_venue_id_canteens"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_readings")),
    )
    op.create_index("ix_queue_readings_venue_at", "queue_readings", ["venue_id", "at"], unique=False)
    op.create_table(
        "staff_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role_label", sa.Text(), server_default="", nullable=False),
        sa.Column("method", sa.Text(), server_default="badge", nullable=False),
        sa.Column("badge_code", sa.Integer(), nullable=True),
        sa.Column("till_code", sa.Text(), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_version", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("method IN ('face', 'badge')", name=op.f("ck_staff_members_method")),
        sa.CheckConstraint(
            "badge_code IS NULL OR badge_code BETWEEN 0 AND 249", name=op.f("ck_staff_members_badge_range")
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["canteens.id"], name=op.f("fk_staff_members_venue_id_canteens"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_members")),
        sa.UniqueConstraint("venue_id", "display_name", name="uq_staff_members_venue_name"),
    )
    op.create_index(op.f("ix_staff_members_venue_id"), "staff_members", ["venue_id"], unique=False)
    op.create_index(
        "uq_staff_members_badge",
        "staff_members",
        ["venue_id", "badge_code"],
        unique=True,
        postgresql_where=sa.text("badge_code IS NOT NULL"),
    )
    op.create_index(
        "uq_staff_members_till",
        "staff_members",
        ["venue_id", "till_code"],
        unique=True,
        postgresql_where=sa.text("till_code IS NOT NULL"),
    )
    op.create_table(
        "face_templates",
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("sealed", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["staff_members.id"],
            name=op.f("fk_face_templates_staff_id_staff_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("staff_id", name=op.f("pk_face_templates")),
    )
    op.create_table(
        "staff_presence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("area IN ('counter', 'kitchen', 'floor')", name=op.f("ck_staff_presence_area")),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name=op.f("ck_staff_presence_ends_after_start")
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["staff_members.id"],
            name=op.f("fk_staff_presence_staff_id_staff_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_presence")),
    )
    op.create_index("ix_staff_presence_staff_started", "staff_presence", ["staff_id", "started_at"], unique=False)
    op.create_index(
        "one_open_presence",
        "staff_presence",
        ["staff_id", "area"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "till_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("venue_id", sa.String(length=40), nullable=False),
        sa.Column("order_ref", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cashier_code", sa.Text(), nullable=True),
        sa.Column("staff_id", sa.Uuid(), nullable=True),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint("total >= 0", name=op.f("ck_till_orders_non_negative_total")),
        sa.ForeignKeyConstraint(
            ["staff_id"], ["staff_members.id"], name=op.f("fk_till_orders_staff_id_staff_members"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["canteens.id"], name=op.f("fk_till_orders_venue_id_canteens"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_orders")),
        sa.UniqueConstraint("venue_id", "order_ref", name="uq_till_orders_venue_ref"),
    )
    op.create_index(op.f("ix_till_orders_staff_id"), "till_orders", ["staff_id"], unique=False)
    op.create_index("ix_till_orders_venue_at", "till_orders", ["venue_id", "at"], unique=False)
    op.create_table(
        "till_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.CheckConstraint("qty > 0", name=op.f("ck_till_items_positive_qty")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_till_items_non_negative_price")),
        sa.ForeignKeyConstraint(
            ["order_id"], ["till_orders.id"], name=op.f("fk_till_items_order_id_till_orders"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_till_items")),
    )
    op.create_index(op.f("ix_till_items_order_id"), "till_items", ["order_id"], unique=False)
    op.add_column("organizations", sa.Column("staff_retention_days", sa.Integer(), server_default="60", nullable=False))
    op.create_check_constraint(
        op.f("ck_organizations_staff_retention_range"), "organizations", "staff_retention_days BETWEEN 7 AND 365"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_organizations_staff_retention_range"), "organizations", type_="check")
    op.drop_column("organizations", "staff_retention_days")
    op.drop_index(op.f("ix_till_items_order_id"), table_name="till_items")
    op.drop_table("till_items")
    op.drop_index("ix_till_orders_venue_at", table_name="till_orders")
    op.drop_index(op.f("ix_till_orders_staff_id"), table_name="till_orders")
    op.drop_table("till_orders")
    op.drop_index("one_open_presence", table_name="staff_presence", postgresql_where=sa.text("ended_at IS NULL"))
    op.drop_index("ix_staff_presence_staff_started", table_name="staff_presence")
    op.drop_table("staff_presence")
    op.drop_table("face_templates")
    op.drop_index(
        "uq_staff_members_till", table_name="staff_members", postgresql_where=sa.text("till_code IS NOT NULL")
    )
    op.drop_index(
        "uq_staff_members_badge", table_name="staff_members", postgresql_where=sa.text("badge_code IS NOT NULL")
    )
    op.drop_index(op.f("ix_staff_members_venue_id"), table_name="staff_members")
    op.drop_table("staff_members")
    op.drop_index("ix_queue_readings_venue_at", table_name="queue_readings")
    op.drop_table("queue_readings")
