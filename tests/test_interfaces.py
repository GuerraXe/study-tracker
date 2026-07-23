from datetime import date
from decimal import Decimal

from study_tracker.domain import (
    ClassTotal,
    NumberedSession,
    SessionSummary,
    StudySession,
    number_sessions,
    session_to_dict,
    summarize_sessions,
)


TODAY = date(2026, 7, 23)


def make_session(class_name, session_date, hours):
    return StudySession(
        class_name=class_name,
        date=date.fromisoformat(session_date),
        hours=Decimal(hours),
        validation_today=TODAY,
    )


def test_numbered_sessions_have_named_fields():
    older = make_session("Math", "2026-07-20", "1")
    newer = make_session("Biology", "2026-07-23", "2")

    rows = number_sessions([older, newer])

    assert rows == [
        NumberedSession(number=1, original_index=1, session=newer),
        NumberedSession(number=2, original_index=0, session=older),
    ]
    assert rows[0].session.class_name == "Biology"


def test_summary_has_named_immutable_results():
    sessions = [
        make_session("Biology", "2026-07-23", "1.5"),
        make_session("biology", "2026-07-22", "0.5"),
        make_session("Math", "2026-07-21", "2"),
    ]

    result = summarize_sessions(sessions)

    assert result == SessionSummary(
        class_totals=(
            ClassTotal(class_name="Biology", hours=Decimal("2.0")),
            ClassTotal(class_name="Math", hours=Decimal("2")),
        ),
        overall_hours=Decimal("4.0"),
    )


def test_serialized_record_has_exact_typed_shape():
    session = make_session("Biology", "2026-07-23", "1.5")

    assert session_to_dict(session) == {
        "class_name": "Biology",
        "date": "2026-07-23",
        "hours": 1.5,
        "notes": "",
    }
