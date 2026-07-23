from dataclasses import InitVar, dataclass
from datetime import date as Date
from decimal import Decimal, InvalidOperation
from typing import Sequence, TypedDict


class ValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class InvalidSessionNumber(ValueError):
    pass


class SessionRecord(TypedDict):
    class_name: str
    date: str
    hours: float
    notes: str


def _decimal_places(value: Decimal) -> int:
    normalized = value.normalize()
    return max(0, -normalized.as_tuple().exponent)


def validate_class_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("class_name", "Class name must be text.")
    result = value.strip()
    if not 1 <= len(result) <= 100:
        raise ValidationError(
            "class_name", "Class name must contain 1 to 100 characters."
        )
    return result


def validate_session_date(value: str, *, today: Date | None = None) -> Date:
    if not isinstance(value, str):
        raise ValidationError("date", "Enter the date in YYYY-MM-DD format.")
    try:
        result = Date.fromisoformat(value.strip())
    except ValueError as error:
        raise ValidationError(
            "date", "Enter the date in YYYY-MM-DD format."
        ) from error
    if result > (today or Date.today()):
        raise ValidationError("date", "Study session date cannot be in the future.")
    return result


def validate_hours(value: str | int | float | Decimal) -> Decimal:
    if isinstance(value, bool):
        raise ValidationError("hours", "Please enter hours as a number.")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise ValidationError(
            "hours", "Please enter hours as a number."
        ) from error
    if not result.is_finite():
        raise ValidationError("hours", "Please enter hours as a number.")
    if result <= 0 or result > 24:
        raise ValidationError(
            "hours", "Hours must be greater than 0 and no more than 24."
        )
    if _decimal_places(result) > 2:
        raise ValidationError(
            "hours", "Hours may have at most two decimal places."
        )
    return result


def validate_notes(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("notes", "Notes must be text.")
    result = value.strip()
    if len(result) > 500:
        raise ValidationError("notes", "Notes must contain no more than 500 characters.")
    return result


@dataclass(frozen=True)
class StudySession:
    class_name: str
    date: Date
    hours: Decimal
    notes: str = ""
    validation_today: InitVar[Date | None] = None

    def __post_init__(self, validation_today: Date | None) -> None:
        if validate_class_name(self.class_name) != self.class_name:
            raise ValidationError("class_name", "Class name must already be trimmed.")
        if not isinstance(self.date, Date):
            raise ValidationError("date", "Session date must be a date.")
        if self.date > (validation_today or Date.today()):
            raise ValidationError("date", "Study session date cannot be in the future.")
        if validate_hours(self.hours) != self.hours:
            raise ValidationError("hours", "Hours are invalid.")
        if validate_notes(self.notes) != self.notes:
            raise ValidationError("notes", "Notes must already be trimmed.")


def session_from_dict(
    value: object,
    record_number: int,
    *,
    today: Date | None = None,
) -> StudySession:
    if not isinstance(value, dict):
        raise ValidationError(
            "session", f"Record {record_number} must be a JSON object."
        )

    required = {"class_name", "date", "hours"}
    allowed = required | {"notes"}
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        names = ", ".join(sorted(missing))
        raise ValidationError(
            "session", f"Record {record_number} is missing: {names}."
        )
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValidationError(
            "session", f"Record {record_number} has unknown fields: {names}."
        )

    try:
        return StudySession(
            class_name=validate_class_name(value["class_name"]),
            date=validate_session_date(value["date"], today=today),
            hours=validate_hours(value["hours"]),
            notes=validate_notes(value.get("notes", "")),
            validation_today=today,
        )
    except ValidationError as error:
        raise ValidationError(
            error.field, f"Record {record_number}: {error.message}"
        ) from error


def session_to_dict(session: StudySession) -> SessionRecord:
    return {
        "class_name": session.class_name,
        "date": session.date.isoformat(),
        "hours": float(session.hours),
        "notes": session.notes,
    }


@dataclass(frozen=True)
class NumberedSession:
    number: int
    original_index: int
    session: StudySession


@dataclass(frozen=True)
class ClassTotal:
    class_name: str
    hours: Decimal


@dataclass(frozen=True)
class SessionSummary:
    class_totals: tuple[ClassTotal, ...]
    overall_hours: Decimal


def number_sessions(sessions: Sequence[StudySession]) -> list[NumberedSession]:
    indexed = list(enumerate(sessions))
    indexed.sort(key=lambda item: item[1].date, reverse=True)
    return [
        NumberedSession(number, original_index, session)
        for number, (original_index, session) in enumerate(indexed, start=1)
    ]


def summarize_sessions(
    sessions: Sequence[StudySession],
) -> SessionSummary:
    totals: dict[str, tuple[str, Decimal]] = {}
    overall = Decimal("0")
    for session in sessions:
        key = session.class_name.casefold()
        display_name, current = totals.get(
            key, (session.class_name, Decimal("0"))
        )
        totals[key] = (display_name, current + session.hours)
        overall += session.hours
    rows = tuple(
        ClassTotal(class_name, hours)
        for class_name, hours in sorted(
            totals.values(), key=lambda row: row[0].casefold()
        )
    )
    return SessionSummary(rows, overall)


def delete_session_by_number(
    sessions: Sequence[StudySession],
    number: int,
) -> list[StudySession]:
    numbered = number_sessions(sessions)
    if number < 1 or number > len(numbered):
        raise InvalidSessionNumber(number)
    original_index = numbered[number - 1].original_index
    return [
        session
        for index, session in enumerate(sessions)
        if index != original_index
    ]
