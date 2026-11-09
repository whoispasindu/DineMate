"""hub devices

Revision ID: 5d1c7e9a2b40
Revises: 98ac04a4aaee
Create Date: 2026-11-11 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "5d1c7e9a2b40"
down_revision: str | Sequence[str] | None = "98ac04a4aaee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_devices_kind"), "devices", type_="check")
    op.create_check_constraint(op.f("ck_devices_kind"), "devices", "kind IN ('camera', 'simulator', 'hub')")


def downgrade() -> None:
    op.execute("DELETE FROM device_heartbeats WHERE device_id IN (SELECT id FROM devices WHERE kind = 'hub')")
    op.execute("DELETE FROM devices WHERE kind = 'hub'")
    op.drop_constraint(op.f("ck_devices_kind"), "devices", type_="check")
    op.create_check_constraint(op.f("ck_devices_kind"), "devices", "kind IN ('camera', 'simulator')")
