"""SQLAlchemy models for the bot database (DATA 2-6)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    false,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now
from app.db.enums import (
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
)

PARTICIPANT_STATUS_TYPE = Enum(
    ParticipantStatus,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=32,
    name="participant_status",
)

REJECTION_REASON_TYPE = Enum(
    RejectionReason,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=16,
    name="rejection_reason",
)

REJECTED_BY_TYPE = Enum(
    RejectedBy,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=6,
    name="rejected_by",
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("timezone BETWEEN -12 AND 14", name="timezone_range"),
    )

    hid: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="0",
        server_default="0",
    )
    status: Mapped[ParticipantStatus | None] = mapped_column(
        PARTICIPANT_STATUS_TYPE,
        nullable=True,
    )
    institute: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cir_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "circles.id",
            name="fk_users_cir_id_circles",
            use_alter=True,
        ),
        nullable=True,
    )
    registered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_banned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    auto_attempts_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    resubmissions_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    greeting_received: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )


class Circle(Base):
    __tablename__ = "circles"
    __table_args__ = (
        CheckConstraint("status IN (0, 1, 2, 3)", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    owner_hid: Mapped[str] = mapped_column(
        ForeignKey(
            "users.hid",
            name="fk_circles_owner_hid_users",
        ),
        nullable=False,
    )
    file_id: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    rejection_reason: Mapped[RejectionReason | None] = mapped_column(
        REJECTION_REASON_TYPE,
        nullable=True,
    )
    rejected_by: Mapped[RejectedBy | None] = mapped_column(
        REJECTED_BY_TYPE,
        nullable=True,
    )
    is_buffered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )


class Mailing(Base):
    __tablename__ = "mailing"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    received_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    received_hids: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
