"""Value sets stored by the database models (DATA 6)."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class ParticipantStatus(StrEnum):
    APPLICANT = "applicant"
    URFU_STUDENT = "urfu_student"
    OTHER_UNIVERSITY_STUDENT = "other_university_student"
    STUDENT_PARENT = "student_parent"
    UNIVERSITY_EMPLOYEE = "university_employee"
    OTHER = "other"


class CircleStatus(IntEnum):
    PENDING_AUTO = 0
    PENDING_MANUAL = 1
    APPROVED = 2
    REJECTED = 3


class RejectionReason(StrEnum):
    PROFANITY = "profanity"
    SHOCKING_CONTENT = "shocking_content"
    ADVERTISING = "advertising"
    OTHER = "other"


class RejectedBy(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
