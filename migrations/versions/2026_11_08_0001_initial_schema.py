"""Initial database schema.

Revision ID: 20261108_0001
Revises:
Create Date: 2026-11-08

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261108_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("hid", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "username",
            sa.String(length=32),
            server_default="0",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("institute", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.SmallInteger(), nullable=True),
        sa.Column("cir_id", sa.BigInteger(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_banned",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "auto_attempts_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "resubmissions_used",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "greeting_received",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "timezone BETWEEN -12 AND 14",
            name="ck_users_timezone_range",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'applicant', "
            "'urfu_student', "
            "'other_university_student', "
            "'student_parent', "
            "'university_employee', "
            "'other'"
            ")",
            name="ck_users_participant_status",
        ),
        sa.PrimaryKeyConstraint("hid", name="pk_users"),
    )

    op.create_table(
        "circles",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("owner_hid", sa.String(length=64), nullable=False),
        sa.Column("file_id", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.String(length=16), nullable=True),
        sa.Column("rejected_by", sa.String(length=6), nullable=True),
        sa.Column(
            "is_buffered",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN (0, 1, 2, 3)",
            name="ck_circles_status_valid",
        ),
        sa.CheckConstraint(
            "rejection_reason IN ("
            "'profanity', "
            "'shocking_content', "
            "'advertising', "
            "'other'"
            ")",
            name="ck_circles_rejection_reason",
        ),
        sa.CheckConstraint(
            "rejected_by IN ('auto', 'manual')",
            name="ck_circles_rejected_by",
        ),
        sa.ForeignKeyConstraint(
            ["owner_hid"],
            ["users.hid"],
            name="fk_circles_owner_hid_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_circles"),
    )

    op.create_table(
        "mailing",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sent_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "received_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "received_hids",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mailing"),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
    )

    op.create_foreign_key(
        "fk_users_cir_id_circles",
        "users",
        "circles",
        ["cir_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_cir_id_circles",
        "users",
        type_="foreignkey",
    )
    op.drop_table("settings")
    op.drop_table("mailing")
    op.drop_table("circles")
    op.drop_table("users")
