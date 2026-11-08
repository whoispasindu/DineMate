"""organizations above canteens and users, business roles, venues

Revision ID: 8c3f2a71d0b4
Revises: 5b1e0c7d9a24
Create Date: 2026-11-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c3f2a71d0b4"
down_revision: str | Sequence[str] | None = "5b1e0c7d9a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = "role IN ('shop_manager', 'canteen_manager', 'campus_admin', 'safety_officer')"
NEW_ROLES = "role IN ('shop_manager', 'canteen_manager', 'campus_admin', 'safety_officer', 'owner', 'venue_manager')"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('campus', 'business')", name=op.f("ck_organizations_kind")),
        sa.CheckConstraint("retention_days BETWEEN 7 AND 730", name=op.f("ck_organizations_retention_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.execute("INSERT INTO organizations (id, name, kind, is_sample) VALUES ('campus', 'Campus', 'campus', true)")

    op.add_column(
        "canteens", sa.Column("organization_id", sa.String(length=40), server_default="campus", nullable=False)
    )
    op.add_column("canteens", sa.Column("kind", sa.Text(), server_default="canteen", nullable=False))
    op.create_foreign_key(
        op.f("fk_canteens_organization_id_organizations"), "canteens", "organizations", ["organization_id"], ["id"]
    )
    op.create_index(op.f("ix_canteens_organization_id"), "canteens", ["organization_id"])
    op.create_check_constraint(op.f("ck_canteens_kind"), "canteens", "kind IN ('canteen', 'venue')")
    op.create_check_constraint(op.f("ck_canteens_venue_id_prefix"), "canteens", "(kind = 'venue') = (id LIKE 'v-%')")

    op.add_column("users", sa.Column("organization_id", sa.String(length=40), server_default="campus", nullable=False))
    op.create_foreign_key(
        op.f("fk_users_organization_id_organizations"), "users", "organizations", ["organization_id"], ["id"]
    )
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"])
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role"), "users", NEW_ROLES)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM users WHERE role IN ('owner', 'venue_manager')")
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role"), "users", OLD_ROLES)
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_constraint(op.f("fk_users_organization_id_organizations"), "users", type_="foreignkey")
    op.drop_column("users", "organization_id")
    op.execute("DELETE FROM canteens WHERE kind = 'venue'")
    op.drop_constraint(op.f("ck_canteens_venue_id_prefix"), "canteens", type_="check")
    op.drop_constraint(op.f("ck_canteens_kind"), "canteens", type_="check")
    op.drop_index(op.f("ix_canteens_organization_id"), table_name="canteens")
    op.drop_constraint(op.f("fk_canteens_organization_id_organizations"), "canteens", type_="foreignkey")
    op.drop_column("canteens", "kind")
    op.drop_column("canteens", "organization_id")
    op.drop_table("organizations")
