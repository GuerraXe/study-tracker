import csv
import json
import os
import tempfile
from datetime import date as Date
from pathlib import Path
from typing import Sequence

from .domain import (
    StudySession,
    ValidationError,
    session_from_dict,
    session_to_dict,
)


class StorageError(RuntimeError):
    pass


class DataFormatError(StorageError):
    pass


class ExportError(StorageError):
    pass


def load_sessions(
    path: Path,
    *,
    today: Date | None = None,
) -> list[StudySession]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DataFormatError(f"Could not read {path.name}: {error}") from error

    if not isinstance(data, list):
        raise DataFormatError(f"{path.name} must contain a JSON array.")

    try:
        return [
            session_from_dict(item, index, today=today)
            for index, item in enumerate(data, start=1)
        ]
    except ValidationError as error:
        raise DataFormatError(f"Invalid data in {path.name}: {error}") from error


def save_sessions(path: Path, sessions: Sequence[StudySession]) -> None:
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            text=True,
        )
        temporary_path = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            json.dump(
                [session_to_dict(session) for session in sessions],
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
        temporary_path = None
    except OSError as error:
        raise StorageError(f"Could not save {path.name}: {error}") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def export_sessions(
    destination: Path,
    sessions: Sequence[StudySession],
) -> None:
    created = False
    try:
        with destination.open(
            "x", encoding="utf-8", newline=""
        ) as file:
            created = True
            writer = csv.DictWriter(
                file,
                fieldnames=["class_name", "date", "hours", "notes"],
            )
            writer.writeheader()
            for session in sessions:
                writer.writerow(session_to_dict(session))
    except FileExistsError as error:
        raise ExportError(
            f"{destination.name} already exists; it was not overwritten."
        ) from error
    except OSError as error:
        if created:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise ExportError(
            f"Could not export {destination.name}: {error}"
        ) from error
