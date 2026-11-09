from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps

CAMPUS_ORG = "campus"
ORG_KINDS = ("campus", "business")
DEFAULT_RETENTION_DAYS = 90
DEFAULT_STAFF_RETENTION_DAYS = 60


class Organization(Timestamps, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("kind IN ('campus', 'business')", name="kind"),
        CheckConstraint("retention_days BETWEEN 7 AND 730", name="retention_range"),
        CheckConstraint("staff_retention_days BETWEEN 7 AND 365", name="staff_retention_range"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    retention_days: Mapped[int] = mapped_column(Integer, server_default=str(DEFAULT_RETENTION_DAYS))
    staff_retention_days: Mapped[int] = mapped_column(Integer, server_default=str(DEFAULT_STAFF_RETENTION_DAYS))
    is_sample: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
