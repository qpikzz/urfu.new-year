"""Database request layer used by handlers and background workers."""

from app.db.requests.circles import (
    approve_circle,
    count_pending_circles,
    create_circle,
    get_circle,
    get_next_pending_circle,
    reject_circle,
    set_circle_status,
)
from app.db.requests.counters import (
    increment_auto_attempts,
    increment_resubmissions,
)
from app.db.requests.mailing import create_mailing, finish_mailing
from app.db.requests.settings import get_setting, set_setting
from app.db.requests.statistics import Statistics, get_statistics
from app.db.requests.users import (
    create_user,
    get_user,
    mark_user_registered,
    set_greeting_received,
    set_user_banned,
    set_user_circle,
    set_user_institute,
    set_user_status,
    set_user_timezone,
    update_user_identity,
)

__all__ = [
    "Statistics",
    "approve_circle",
    "count_pending_circles",
    "create_circle",
    "create_mailing",
    "create_user",
    "finish_mailing",
    "get_circle",
    "get_next_pending_circle",
    "get_setting",
    "get_statistics",
    "get_user",
    "increment_auto_attempts",
    "increment_resubmissions",
    "mark_user_registered",
    "reject_circle",
    "set_circle_status",
    "set_greeting_received",
    "set_setting",
    "set_user_banned",
    "set_user_circle",
    "set_user_institute",
    "set_user_status",
    "set_user_timezone",
    "update_user_identity",
]
