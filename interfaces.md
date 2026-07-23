# Study Tracker Interfaces

This document defines the public contracts between the Study Tracker modules.
Implementations may change internally, but these names, parameter names, types,
return types, and documented exceptions should remain stable unless this
document and the tests are deliberately updated first.

## Shared types

### `StudySession`

```python
StudySession(
    class_name: str,
    date: datetime.date,
    hours: Decimal,
    notes: str = "",
    validation_today: datetime.date | None = None,
)
```

An immutable, validated study-session record. Construction raises
`ValidationError` when any field violates the specification.
`validation_today` is used only to make future-date validation deterministic;
it is not stored as session data.

### `NumberedSession`

```python
@dataclass(frozen=True)
class NumberedSession:
    number: int
    original_index: int
    session: StudySession
```

Provides named access to the displayed number, original storage index, and
session so callers do not need to memorize tuple positions.

### `ClassTotal`

```python
@dataclass(frozen=True)
class ClassTotal:
    class_name: str
    hours: Decimal
```

Represents one case-insensitively grouped class total.

### `SessionSummary`

```python
@dataclass(frozen=True)
class SessionSummary:
    class_totals: tuple[ClassTotal, ...]
    overall_hours: Decimal
```

Provides named, immutable access to per-class and overall study totals.

### `SessionRecord`

```python
class SessionRecord(TypedDict):
    class_name: str
    date: str
    hours: float
    notes: str
```

Defines the exact serialized JSON and CSV record shape.

### `ValidationError`

```python
ValidationError(field: str, message: str) -> None
```

Raised when terminal input or persisted session data violates a domain rule.
`field` is a stable field identifier and `message` is safe to show to the user.

### `InvalidSessionNumber`

```python
InvalidSessionNumber(number: int) -> None
```

Raised when a requested displayed session number is outside the available
range.

## `study_tracker/domain.py`

### `validate_class_name`

```python
validate_class_name(value: str) -> str
```

Trims and returns a class name containing 1–100 characters. Raises
`ValidationError` for an invalid value.

### `validate_session_date`

```python
validate_session_date(
    value: str,
    *,
    today: datetime.date | None = None,
) -> datetime.date
```

Parses a real `YYYY-MM-DD` date and rejects future dates. `today` allows callers
and tests to supply the comparison date. Raises `ValidationError` for invalid
input.

### `validate_hours`

```python
validate_hours(
    value: str | int | float | Decimal,
) -> Decimal
```

Parses and returns finite study hours greater than 0 and no greater than 24,
with at most two decimal places. Raises `ValidationError` for invalid input.

### `validate_notes`

```python
validate_notes(value: str) -> str
```

Trims and returns optional notes containing no more than 500 characters. Raises
`ValidationError` for invalid input.

### `session_from_dict`

```python
session_from_dict(
    value: object,
    record_number: int,
    *,
    today: datetime.date | None = None,
) -> StudySession
```

Validates one decoded JSON record and returns a `StudySession`. A missing
`notes` field is normalized to an empty string for backward compatibility.
Raises `ValidationError` with the record number when data is malformed.

### `session_to_dict`

```python
session_to_dict(
    session: StudySession,
) -> SessionRecord
```

Converts a validated session into the exact JSON/CSV field shape:
`class_name`, `date`, `hours`, and `notes`.

### `number_sessions`

```python
number_sessions(
    sessions: Sequence[StudySession],
) -> list[NumberedSession]
```

Returns a new newest-first numbered view while retaining each session's original
storage index. It does not mutate the supplied sequence.

### `summarize_sessions`

```python
summarize_sessions(
    sessions: Sequence[StudySession],
) -> SessionSummary
```

Returns named, immutable access to alphabetized class totals and the overall
total. Class names are grouped case-insensitively.

### `delete_session_by_number`

```python
delete_session_by_number(
    sessions: Sequence[StudySession],
    number: int,
) -> list[StudySession]
```

Returns a new list without the record identified by the newest-first displayed
number. Raises `InvalidSessionNumber` when the number does not exist and never
mutates the supplied sequence.

## `study_tracker/storage.py`

### `load_sessions`

```python
load_sessions(
    path: pathlib.Path,
    *,
    today: datetime.date | None = None,
) -> list[StudySession]
```

Loads and validates every session from a UTF-8 JSON file. Returns an empty list
when the file does not exist. Raises `DataFormatError` when the file is
unreadable, invalid JSON, not an array, or contains a malformed record.

### `save_sessions`

```python
save_sessions(
    path: pathlib.Path,
    sessions: Sequence[StudySession],
) -> None
```

Atomically writes all sessions as UTF-8 JSON, creating the file or parent
directory when necessary. Raises `StorageError` when saving fails and preserves
the previous destination when replacement cannot complete.

### `export_sessions`

```python
export_sessions(
    destination: pathlib.Path,
    sessions: Sequence[StudySession],
) -> None
```

Creates a UTF-8 CSV with `class_name,date,hours,notes` headers and one row per
session. Raises `ExportError` when the destination already exists or cannot be
written; it never overwrites an existing file.

### Storage exceptions

```python
StorageError(message: str) -> None
DataFormatError(message: str) -> None
ExportError(message: str) -> None
```

`DataFormatError` and `ExportError` specialize `StorageError` so the CLI can
handle expected file failures without exposing tracebacks.

## `study_tracker/cli.py`

### Callback types

```python
InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
```

These callbacks isolate terminal input and output so commands can be tested
without using the real console.

### `run`

```python
run(
    sessions_path: pathlib.Path,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    today: datetime.date | None = None,
) -> int
```

Runs the interactive command loop against `sessions_path`. It accepts injectable
terminal callbacks and a reference date for deterministic tests. Returns process
exit code `0` after `quit`, end-of-input, or keyboard interruption. Expected
validation and storage failures are printed and return control to the prompt.

## `main.py`

### `main`

```python
main() -> int
```

Resolves `sessions.json` beside `main.py`, starts the CLI through `run`, and
returns its process exit code.

## Internal interfaces

Functions whose names begin with `_` in `cli.py` are private implementation
details. They may be refactored without changing this contract as long as the
public interfaces and observable behavior remain unchanged.
