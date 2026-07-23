import json
from datetime import date

import pytest

from study_tracker.cli import run
from study_tracker.domain import (
    ValidationError,
    validate_class_name,
    validate_hours,
    validate_notes,
    validate_session_date,
)


TODAY = date(2026, 7, 23)


@pytest.mark.parametrize("value", ["", "   ", "x" * 101, 123])
def test_rejects_invalid_class_names(value):
    with pytest.raises(ValidationError):
        validate_class_name(value)


@pytest.mark.parametrize(
    "value",
    ["0", "-5", "25", "abc", "!@#", "1.234", True, float("nan"), float("inf")],
)
def test_rejects_invalid_hours(value):
    with pytest.raises(ValidationError):
        validate_hours(value)


@pytest.mark.parametrize(
    "value",
    ["", "07/23/2026", "2026-02-30", "2026-07-24"],
)
def test_rejects_invalid_dates(value):
    with pytest.raises(ValidationError):
        validate_session_date(value, today=TODAY)


@pytest.mark.parametrize("value", ["x" * 501, 123])
def test_rejects_invalid_notes(value):
    with pytest.raises(ValidationError):
        validate_notes(value)


@pytest.mark.parametrize("command", ["delete", "delete abc", "delete 0", "delete -1", "delete 2"])
def test_invalid_delete_never_changes_data(tmp_path, command):
    sessions_path = tmp_path / "sessions.json"
    original = [
        {
            "class_name": "Math",
            "date": "2026-07-20",
            "hours": 1.0,
            "notes": "",
        }
    ]
    sessions_path.write_text(json.dumps(original), encoding="utf-8")
    answers = iter([command, "quit"])
    output = []

    run(
        sessions_path,
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
        today=TODAY,
    )

    assert json.loads(sessions_path.read_text(encoding="utf-8")) == original
    assert any("usage" in line.lower() or "valid" in line.lower() for line in output)


def test_corrupt_json_is_reported_and_preserved(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    corrupt = "{invalid json"
    sessions_path.write_text(corrupt, encoding="utf-8")
    answers = iter(["list", "quit"])
    output = []

    run(
        sessions_path,
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
        today=TODAY,
    )

    assert sessions_path.read_text(encoding="utf-8") == corrupt
    assert any("sessions.json" in line for line in output)
    assert not any("traceback" in line.lower() for line in output)


def test_missing_file_between_commands_is_handled(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    sessions_path.write_text(
        json.dumps(
            [
                {
                    "class_name": "Math",
                    "date": "2026-07-20",
                    "hours": 1.0,
                    "notes": "",
                }
            ]
        ),
        encoding="utf-8",
    )
    commands = iter(["list", "list", "quit"])
    command_count = 0
    output = []

    def input_fn(prompt):
        nonlocal command_count
        value = next(commands)
        command_count += 1
        if command_count == 2:
            sessions_path.unlink()
        return value

    run(
        sessions_path,
        input_fn=input_fn,
        output_fn=output.append,
        today=TODAY,
    )

    assert any("Math" in line for line in output)
    assert "No study sessions found." in output


def test_extremely_long_class_is_rejected_then_valid_value_saves(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    answers = iter(
        [
            "log",
            "x" * 10_000,
            "Math",
            "2026-07-20",
            "1",
            "",
            "quit",
        ]
    )
    output = []

    run(
        sessions_path,
        input_fn=lambda prompt: next(answers),
        output_fn=output.append,
        today=TODAY,
    )

    saved = json.loads(sessions_path.read_text(encoding="utf-8"))
    assert saved[0]["class_name"] == "Math"
    assert any("1 to 100" in line for line in output)


def test_sql_like_text_is_stored_as_plain_class_name(tmp_path):
    sessions_path = tmp_path / "sessions.json"
    special_text = '"; DROP TABLE sessions; --'
    answers = iter(
        ["log", special_text, "2026-07-20", "1", "", "quit"]
    )

    run(
        sessions_path,
        input_fn=lambda prompt: next(answers),
        output_fn=lambda line: None,
        today=TODAY,
    )

    saved = json.loads(sessions_path.read_text(encoding="utf-8"))
    assert saved[0]["class_name"] == special_text


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt()])
def test_interruption_during_log_prompt_exits_cleanly(tmp_path, interruption):
    sessions_path = tmp_path / "sessions.json"
    call_count = 0
    output = []

    def input_fn(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "log"
        raise interruption

    result = run(
        sessions_path,
        input_fn=input_fn,
        output_fn=output.append,
        today=TODAY,
    )

    assert result == 0
    assert not sessions_path.exists()
    assert "Goodbye!" in output


@pytest.mark.parametrize("interruption", [EOFError(), KeyboardInterrupt()])
def test_interruption_during_delete_confirmation_exits_cleanly(
    tmp_path, interruption
):
    sessions_path = tmp_path / "sessions.json"
    original = [
        {
            "class_name": "Math",
            "date": "2026-07-20",
            "hours": 1.0,
            "notes": "",
        }
    ]
    sessions_path.write_text(json.dumps(original), encoding="utf-8")
    call_count = 0
    output = []

    def input_fn(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "delete 1"
        raise interruption

    result = run(
        sessions_path,
        input_fn=input_fn,
        output_fn=output.append,
        today=TODAY,
    )

    assert result == 0
    assert json.loads(sessions_path.read_text(encoding="utf-8")) == original
    assert "Goodbye!" in output
