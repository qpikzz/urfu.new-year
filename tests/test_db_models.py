from __future__ import annotations

from datetime import UTC

import pytest
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.schema import CreateTable

from app.db import (
    Base,
    Circle,
    CircleStatus,
    Mailing,
    ParticipantStatus,
    RejectedBy,
    RejectionReason,
    Setting,
    User,
    utc_now,
)

TABLE_COLUMNS = {
    User: {
        "hid",
        "full_name",
        "username",
        "status",
        "institute",
        "timezone",
        "cir_id",
        "registered_at",
        "is_banned",
        "auto_attempts_used",
        "resubmissions_used",
        "greeting_received",
    },
    Circle: {
        "id",
        "owner_hid",
        "file_id",
        "sent_at",
        "duration",
        "status",
        "rejection_reason",
        "rejected_by",
        "is_buffered",
    },
    Mailing: {
        "id",
        "started_at",
        "finished_at",
        "sent_count",
        "received_count",
        "received_hids",
    },
    Setting: {"key", "value"},
}

PRIMARY_KEYS = {
    User: ("hid",),
    Circle: ("id",),
    Mailing: ("id",),
    Setting: ("key",),
}


def test_metadata_contains_exactly_the_spec_tables() -> None:
    assert set(Base.metadata.tables) == {"users", "circles", "mailing", "settings"}


@pytest.mark.parametrize("model", TABLE_COLUMNS)
def test_table_columns_match_data_spec(model) -> None:
    assert set(model.__table__.columns.keys()) == TABLE_COLUMNS[model]


@pytest.mark.parametrize(("model", "primary_key"), PRIMARY_KEYS.items())
def test_primary_keys(model, primary_key) -> None:
    assert tuple(model.__table__.primary_key.columns.keys()) == primary_key


def test_user_progressively_filled_fields_are_nullable() -> None:
    nullable = {
        column.name
        for column in User.__table__.columns
        if column.nullable
    }

    assert nullable == {
        "status",
        "institute",
        "timezone",
        "cir_id",
        "registered_at",
    }


def test_circle_rejection_fields_are_nullable() -> None:
    nullable = {
        column.name
        for column in Circle.__table__.columns
        if column.nullable
    }

    assert nullable == {"rejection_reason", "rejected_by"}


def test_mailing_finished_at_is_nullable() -> None:
    nullable = {
        column.name
        for column in Mailing.__table__.columns
        if column.nullable
    }

    assert nullable == {"finished_at"}


def test_user_defaults_match_data_spec() -> None:
    columns = User.__table__.c

    assert columns.username.default.arg == "0"
    assert columns.is_banned.default.arg is False
    assert columns.auto_attempts_used.default.arg == 0
    assert columns.resubmissions_used.default.arg == 0
    assert columns.greeting_received.default.arg is False
    assert columns.registered_at.default is None


def test_circle_defaults_match_data_spec() -> None:
    columns = Circle.__table__.c

    assert columns.status.default.arg == 0
    assert columns.is_buffered.default.arg is False
    assert columns.sent_at.default.is_callable
    assert columns.sent_at.default.arg.__name__ == "utc_now"


def test_mailing_defaults_match_data_spec() -> None:
    columns = Mailing.__table__.c

    assert columns.sent_count.default.arg == 0
    assert columns.received_count.default.arg == 0
    assert columns.received_hids.default.arg.__name__ == "list"
    assert columns.started_at.default.is_callable
    assert columns.started_at.default.arg.__name__ == "utc_now"


def test_user_cir_id_references_circles() -> None:
    foreign_key = next(iter(User.__table__.c.cir_id.foreign_keys))

    assert foreign_key.target_fullname == "circles.id"
    assert foreign_key.constraint.use_alter is True


def test_circle_owner_hid_references_users() -> None:
    foreign_key = next(iter(Circle.__table__.c.owner_hid.foreign_keys))

    assert foreign_key.target_fullname == "users.hid"


def test_participant_status_values() -> None:
    expected = [
        "applicant",
        "urfu_student",
        "other_university_student",
        "student_parent",
        "university_employee",
        "other",
    ]

    assert [item.value for item in ParticipantStatus] == expected
    assert User.__table__.c.status.type.enums == expected


def test_circle_status_values() -> None:
    assert [item.value for item in CircleStatus] == [0, 1, 2, 3]

    check = next(
        constraint
        for constraint in Circle.__table__.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_circles_status_valid"
    )
    assert "status IN (0, 1, 2, 3)" in str(check.sqltext)


def test_rejection_reason_values() -> None:
    expected = ["profanity", "shocking_content", "advertising", "other"]

    assert [item.value for item in RejectionReason] == expected
    assert Circle.__table__.c.rejection_reason.type.enums == expected


def test_rejected_by_values() -> None:
    expected = ["auto", "manual"]

    assert [item.value for item in RejectedBy] == expected
    assert Circle.__table__.c.rejected_by.type.enums == expected


def test_timezone_is_limited_to_the_spec_range() -> None:
    assert isinstance(User.__table__.c.timezone.type, SmallInteger)

    check = next(
        constraint
        for constraint in User.__table__.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_users_timezone_range"
    )
    assert "BETWEEN -12 AND 14" in str(check.sqltext)


def test_mailing_received_hids_is_a_string_array() -> None:
    column = Mailing.__table__.c.received_hids

    assert isinstance(column.type, ARRAY)
    assert isinstance(column.type.item_type, String)
    assert column.nullable is False


@pytest.mark.parametrize(
    "column",
    [
        User.__table__.c.registered_at,
        Circle.__table__.c.sent_at,
        Mailing.__table__.c.started_at,
        Mailing.__table__.c.finished_at,
    ],
)
def test_timestamps_are_timezone_aware(column) -> None:
    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True


def test_file_id_is_stored_as_text() -> None:
    assert isinstance(Circle.__table__.c.file_id.type, Text)
    assert isinstance(Setting.__table__.c.value.type, Text)


def test_counters_are_integers() -> None:
    assert isinstance(Circle.__table__.c.duration.type, Integer)
    assert isinstance(User.__table__.c.auto_attempts_used.type, Integer)
    assert isinstance(User.__table__.c.resubmissions_used.type, Integer)


def test_utc_now_returns_timezone_aware_utc() -> None:
    assert utc_now().tzinfo is UTC


def test_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()

    for table in Base.metadata.tables.values():
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl
