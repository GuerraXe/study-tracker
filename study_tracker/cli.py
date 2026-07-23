from datetime import date as Date
from pathlib import Path
from typing import Callable

from .domain import (
    InvalidSessionNumber,
    StudySession,
    ValidationError,
    delete_session_by_number,
    number_sessions,
    summarize_sessions,
    validate_class_name,
    validate_hours,
    validate_notes,
    validate_session_date,
)
from .storage import (
    ExportError,
    StorageError,
    export_sessions,
    load_sessions,
    save_sessions,
)


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


HELP_TEXT = (
    "Commands: log, list, summary, delete NUMBER, "
    "export [FILENAME], help, quit"
)


def _load(
    sessions_path: Path,
    today: Date,
    output_fn: OutputFn,
) -> list[StudySession] | None:
    try:
        return load_sessions(sessions_path, today=today)
    except StorageError as error:
        output_fn(str(error))
        return None


def _prompt_until_valid(
    prompt: str,
    validator,
    input_fn: InputFn,
    output_fn: OutputFn,
):
    while True:
        value = input_fn(prompt)
        try:
            return validator(value)
        except ValidationError as error:
            output_fn(error.message)


def _format_session(
    number: int,
    session: StudySession,
) -> str:
    line = (
        f"{number}. {session.date.isoformat()} | "
        f"{session.class_name} | {session.hours:.2f} hours"
    )
    if session.notes:
        line += f" | {session.notes}"
    return line


def run(
    sessions_path: Path,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    today: Date | None = None,
) -> int:
    reference_date = today or Date.today()
    output_fn("Type 'help' for commands.")

    while True:
        try:
            raw = input_fn("study-tracker> ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Goodbye!")
            return 0

        if not raw:
            continue
        command, _, argument = raw.partition(" ")
        command = command.casefold()
        argument = argument.strip()

        try:
            if command == "quit":
                if argument:
                    output_fn("Usage: quit")
                    continue
                output_fn("Goodbye!")
                return 0

            if command == "help":
                if argument:
                    output_fn("Usage: help")
                else:
                    output_fn(HELP_TEXT)
                continue

            if command == "log":
                if argument:
                    output_fn("Usage: log")
                    continue
                sessions = _load(sessions_path, reference_date, output_fn)
                if sessions is None:
                    continue
                class_name = _prompt_until_valid(
                    "Class name: ",
                    validate_class_name,
                    input_fn,
                    output_fn,
                )
                session_date = _prompt_until_valid(
                    "Date (YYYY-MM-DD): ",
                    lambda value: validate_session_date(
                        value, today=reference_date
                    ),
                    input_fn,
                    output_fn,
                )
                hours = _prompt_until_valid(
                    "Hours studied: ",
                    validate_hours,
                    input_fn,
                    output_fn,
                )
                notes = _prompt_until_valid(
                    "Notes (optional): ",
                    validate_notes,
                    input_fn,
                    output_fn,
                )
                session = StudySession(
                    class_name=class_name,
                    date=session_date,
                    hours=hours,
                    notes=notes,
                    validation_today=reference_date,
                )
                save_sessions(sessions_path, [*sessions, session])
                output_fn("Study session saved.")
                continue

            if command == "list":
                if argument:
                    output_fn("Usage: list")
                    continue
                sessions = _load(sessions_path, reference_date, output_fn)
                if sessions is None:
                    continue
                numbered = number_sessions(sessions)
                if not numbered:
                    output_fn("No study sessions found.")
                    continue
                for number, _, session in numbered:
                    output_fn(_format_session(number, session))
                continue

            if command == "summary":
                if argument:
                    output_fn("Usage: summary")
                    continue
                sessions = _load(sessions_path, reference_date, output_fn)
                if sessions is None:
                    continue
                if not sessions:
                    output_fn("No study sessions found.")
                    continue
                totals, overall = summarize_sessions(sessions)
                for class_name, hours in totals:
                    output_fn(f"{class_name}: {hours:.2f} hours")
                output_fn(f"Overall: {overall:.2f} hours")
                continue

            if command == "delete":
                sessions = _load(sessions_path, reference_date, output_fn)
                if sessions is None:
                    continue
                try:
                    number = int(argument)
                except ValueError:
                    output_fn("Usage: delete NUMBER")
                    continue
                numbered = number_sessions(sessions)
                if not numbered:
                    output_fn("No study sessions found.")
                    continue
                if number < 1 or number > len(numbered):
                    output_fn(
                        f"Valid session numbers are 1 through {len(numbered)}."
                    )
                    continue
                output_fn(_format_session(number, numbered[number - 1][2]))
                confirmation = input_fn("Delete this session? [y/N]: ")
                if confirmation.strip().casefold() not in {"y", "yes"}:
                    output_fn("Deletion canceled.")
                    continue
                try:
                    remaining = delete_session_by_number(sessions, number)
                except InvalidSessionNumber:
                    output_fn(
                        f"Valid session numbers are 1 through {len(numbered)}."
                    )
                    continue
                save_sessions(sessions_path, remaining)
                output_fn("Study session deleted.")
                continue

            if command == "export":
                filename = argument or "study_sessions.csv"
                candidate = Path(filename)
                if (
                    candidate.is_absolute()
                    or filename in {".", ".."}
                    or "/" in filename
                    or "\\" in filename
                ):
                    output_fn("Export requires a filename without a directory.")
                    continue
                sessions = _load(sessions_path, reference_date, output_fn)
                if sessions is None:
                    continue
                destination = sessions_path.parent / filename
                try:
                    export_sessions(destination, sessions)
                except ExportError as error:
                    output_fn(str(error))
                    continue
                output_fn(
                    f"Exported {len(sessions)} sessions to {destination.name}."
                )
                continue

            output_fn(f"Unknown command '{command}'. Type 'help' for commands.")
        except StorageError as error:
            output_fn(str(error))
