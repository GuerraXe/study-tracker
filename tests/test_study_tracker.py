import json
from datetime import date


TODAY = date(2026, 7, 23)


def run_cli(sessions_path, responses):
    """Run the planned CLI with scripted input and captured output."""
    from study_tracker.cli import run

    answers = iter(responses)
    output = []

    def input_fn(prompt):
        output.append(prompt)
        return next(answers)

    run(
        sessions_path,
        input_fn=input_fn,
        output_fn=output.append,
        today=TODAY,
    )
    return output


def write_sessions(path, sessions):
    path.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


def read_sessions(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_logging_valid_session_saves_it(tmp_path):
    sessions_path = tmp_path / "sessions.json"

    run_cli(
        sessions_path,
        [
            "log",
            "Biology",
            "2026-07-23",
            "1.5",
            "Reviewed chapter 4",
            "quit",
        ],
    )

    assert read_sessions(sessions_path) == [
        {
            "class_name": "Biology",
            "date": "2026-07-23",
            "hours": 1.5,
            "notes": "Reviewed chapter 4",
        }
    ]


def test_logging_empty_class_name_is_rejected(tmp_path):
    sessions_path = tmp_path / "sessions.json"

    output = run_cli(
        sessions_path,
        [
            "log",
            "",
            "Biology",
            "2026-07-23",
            "1",
            "",
            "quit",
        ],
    )

    assert any("class name" in line.lower() for line in output)
    assert read_sessions(sessions_path)[0]["class_name"] == "Biology"


def test_logging_negative_hours_is_rejected(tmp_path):
    sessions_path = tmp_path / "sessions.json"

    output = run_cli(
        sessions_path,
        [
            "log",
            "Chemistry",
            "2026-07-22",
            "-2",
            "2",
            "",
            "quit",
        ],
    )

    assert "Hours must be greater than 0 and no more than 24." in output
    assert read_sessions(sessions_path)[0]["hours"] == 2.0


def test_logging_non_numeric_hours_is_rejected(tmp_path):
    sessions_path = tmp_path / "sessions.json"

    output = run_cli(
        sessions_path,
        [
            "log",
            "History",
            "2026-07-21",
            "abc",
            "0.75",
            "",
            "quit",
        ],
    )

    assert "Please enter hours as a number." in output
    assert read_sessions(sessions_path)[0]["hours"] == 0.75


def test_listing_with_no_sessions_shows_empty_message(tmp_path):
    sessions_path = tmp_path / "sessions.json"

    output = run_cli(sessions_path, ["list", "quit"])

    assert "No study sessions found." in output


def test_deleting_existing_session_removes_it(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    write_sessions(
        sessions_path,
        [
            {
                "class_name": "Math",
                "date": "2026-07-20",
                "hours": 1.25,
                "notes": "",
            }
        ],
    )

    run_cli(sessions_path, ["delete 1", "yes", "quit"])

    assert read_sessions(sessions_path) == []


def test_deleting_missing_session_shows_error(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    original = [
        {
            "class_name": "Math",
            "date": "2026-07-20",
            "hours": 1.25,
            "notes": "",
        }
    ]
    write_sessions(sessions_path, original)

    output = run_cli(sessions_path, ["delete 2", "quit"])

    assert any("1" in line and "valid" in line.lower() for line in output)
    assert read_sessions(sessions_path) == original


def test_summary_shows_total_hours_per_class(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    write_sessions(
        sessions_path,
        [
            {
                "class_name": "Biology",
                "date": "2026-07-23",
                "hours": 1.5,
                "notes": "",
            },
            {
                "class_name": "biology",
                "date": "2026-07-22",
                "hours": 0.5,
                "notes": "",
            },
            {
                "class_name": "Math",
                "date": "2026-07-21",
                "hours": 2,
                "notes": "",
            },
        ],
    )

    output = run_cli(sessions_path, ["summary", "quit"])

    assert any("Biology" in line and "2.00" in line for line in output)
    assert any("Math" in line and "2.00" in line for line in output)
