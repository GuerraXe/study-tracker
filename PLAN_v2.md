# Revise Summary

## 1. Critique Reconciliation

| Finding | Label | Plan v2 change |
|---------|-------|----------------|
| 1. `Decimal` is not JSON serializable | 🔴 | Limit hours to two decimal places, keep `Decimal` in memory, serialize with `float`, and reconstruct with `Decimal(str(value))`. Add explicit round-trip tests. |
| 2. One validation error cannot drive field-specific retries | 🔴 | Replace the all-fields-at-once validation contract with four field validators. The CLI retries only the validator that failed. |
| 3. Future-date loading depends on the real clock | 🔴 | Thread an optional `today` value through record validation and JSON loading. Tests always provide a fixed date. |
| 4. Delete accepts potentially mismatched snapshots | 🔴 | Replace the two-collection deletion API with `delete_session_by_number(sessions, number)`, which calculates its own numbered view. |
| 5. Export paths exceed the `FILENAME` contract | 🔴 | Accept filenames only, reject absolute paths and directory separators, and export beside `main.py`. |
| 6. `log` prompts before detecting corrupt data | 🟡 | Load and validate existing sessions before asking for any new-session fields. |
| 7. Output assertions lack a message contract | 🟡 | Add a concise message table and distinguish exact-string assertions from content-based assertions. |
| 8. Four modules and result dataclasses may be excessive | 🟡 | Reduce the package to `domain.py`, `storage.py`, and `cli.py`; use tuples for numbered rows and summary results instead of one-use dataclasses. |

White/noise findings were intentionally excluded from the revision.

## 2. Architectural Deltas

- Three package modules instead of four.
- `domain.py` owns the session model, field validation, sorting, summaries, and
  safe deletion.
- Validation is field-oriented rather than one large constructor call.
- JSON numeric conversion is explicit and bounded to two decimal places.
- All date-sensitive loaders and validators accept an injected date.
- Export is restricted to a plain filename in the project directory.
- The `log` command loads existing data before prompting.
- CLI messages have defined stable content for meaningful tests.

## 3. Trade-off Analysis

### `Decimal` in memory, `float` in JSON

JSON has numbers but Python's standard encoder does not support `Decimal`.
Storing a string would violate `SPEC.md`. Restricting hours to two decimal
places and converting to `float` at the serialization boundary keeps the JSON
contract and prevents meaningful precision loss for this time-tracking use case.

### Three modules instead of one or four

A single file is simpler to navigate but couples real data access to tests.
Four modules isolate every concern but add teaching overhead. Three modules keep
storage injectable, preserve a domain boundary, and leave the CLI independently
testable without introducing one-use service objects.

### Filename-only export

Arbitrary paths provide flexibility but introduce unresolved path and permission
semantics. Filename-only export exactly matches the spec, keeps output
discoverable, and prevents accidental writes outside the project.

### Recompute deletion numbering

Passing a prepared numbered snapshot avoids repeated sorting but permits a stale
snapshot to be paired with different data. Recomputing for this small local
dataset costs negligible time and guarantees the number maps to the provided
session list.

---

# Study Tracker Technical Plan — Version 2

## 1. Objective and Scope

Rebuild the Study Tracker according to `SPEC.md` as an interactive Python 3.10+
CLI using only the standard library.

In scope:

- `log`, `list`, `summary`, `delete NUMBER`, `export [FILENAME]`, `help`, `quit`
- JSON persistence
- CSV export
- Validation and actionable failures
- Automated tests isolated from real course data

Out of scope remains unchanged:

- Web or graphical interfaces
- Accounts, databases, networking, or synchronization
- Editing, imports, reminders, grades, or weekly reports
- Third-party packages

Preserve without modification:

- `study_tracker.py`
- `study_sessions.json`

No `.lockedfiles` file exists. No protected-file approval is required.

## 2. Specification Amendments Required Before Coding

Add these accepted decisions to `SPEC.md`:

1. Hours may have at most two decimal places.
2. A missing `notes` key in an older otherwise-valid record is interpreted as
   an empty string.
3. Future session dates are rejected both during entry and file loading.
4. Class summaries merge names case-insensitively and preserve the earliest
   stored spelling for display.
5. `export` accepts a filename only, not an absolute or relative directory path,
   and writes beside `main.py`.
6. Simultaneous program instances are outside scope.
7. `Ctrl+C`, `Ctrl+Z`, or closed terminal input exits cleanly without saving
   partially entered data.

The specification remains authoritative. Tests and implementation must not
begin until these statements are present.

## 3. Target Project Structure

```text
study-tracker/
├── main.py
├── SPEC.md
├── README.md
├── sessions.json
├── study_tracker/
│   ├── __init__.py
│   ├── cli.py
│   ├── domain.py
│   └── storage.py
└── tests/
    ├── test_cli.py
    ├── test_domain.py
    └── test_storage.py
```

The project-root `study_tracker.py` file can coexist with the
`study_tracker/` package because imports resolve the package directory when
`study_tracker.cli` is requested. Pre-implementation verification must confirm
this import on the actual Windows environment before replacing `main.py`.

## 4. Domain Contracts

File: `study_tracker/domain.py`

### Session type

```python
@dataclass(frozen=True)
class StudySession:
    class_name: str
    date: date
    hours: Decimal
    notes: str = ""
```

Every constructed `StudySession` contains validated, trimmed values.

### Validation type

```python
class ValidationError(ValueError):
    field: str
    message: str
```

The error carries a stable field identifier and user-facing message. The CLI
does not inspect arbitrary exception strings to decide which prompt to retry.

### Field validators

```python
validate_class_name(value: str) -> str
validate_session_date(value: str, *, today: date | None = None) -> date
validate_hours(value: str | int | float) -> Decimal
validate_notes(value: str) -> str
```

Rules:

- Class name: trim; length 1–100.
- Date: strict `YYYY-MM-DD`; real calendar date; no later than `today`.
- Hours: reject booleans, NaN, infinity, non-numeric input, zero, negative,
  values over 24, and values with more than two decimal places.
- Notes: trim; length 0–500.

When `today` is omitted, use the current local date. Tests always supply it.

### JSON conversion

```python
session_from_dict(
    value: object,
    record_number: int,
    *,
    today: date | None = None,
) -> StudySession

session_to_dict(session: StudySession) -> dict[str, object]
```

`session_from_dict`:

- Requires an object with `class_name`, `date`, and `hours`.
- Accepts missing `notes` as `""`.
- Rejects unknown keys to enforce the four-field schema.
- Converts JSON numbers through `Decimal(str(value))`.
- Includes the one-based record number in data-format errors.

`session_to_dict`:

- Emits exactly `class_name`, `date`, `hours`, and `notes`.
- Emits date as ISO text.
- Converts the already bounded two-decimal `Decimal` hours to `float`.
- Never exposes a `Decimal` to `json.dump`.

### Numbering, summary, and deletion

```python
NumberedSession = tuple[int, int, StudySession]
# displayed_number, original_index, session

def number_sessions(
    sessions: Sequence[StudySession],
) -> list[NumberedSession]

def summarize_sessions(
    sessions: Sequence[StudySession],
) -> tuple[list[tuple[str, Decimal]], Decimal]

def delete_session_by_number(
    sessions: Sequence[StudySession],
    number: int,
) -> list[StudySession]
```

Rules:

- Sort newest date first.
- Preserve original storage order for equal dates.
- Number from one.
- `delete_session_by_number` computes numbering internally.
- Invalid numbers raise a specific domain error and never mutate the input.
- Class grouping uses `casefold()`.
- Display spelling comes from the earliest stored session in that group.
- Summary rows sort case-insensitively; overall total appears last in the CLI.

## 5. Storage Contracts

File: `study_tracker/storage.py`

```python
class StorageError(RuntimeError): ...
class DataFormatError(StorageError): ...
class ExportError(StorageError): ...

def load_sessions(
    path: Path,
    *,
    today: date | None = None,
) -> list[StudySession]

def save_sessions(
    path: Path,
    sessions: Sequence[StudySession],
) -> None

def export_sessions(
    destination: Path,
    sessions: Sequence[StudySession],
) -> None
```

### Loading

1. Missing file returns `[]`.
2. Read UTF-8.
3. Decode JSON.
4. Require an array root.
5. Validate every record through `session_from_dict(..., today=today)`.
6. On any error, report the path and record number where applicable.
7. Never return a partial collection.

### Atomic JSON saving

1. Convert every session through `session_to_dict`.
2. Create a uniquely named temporary file in the target directory.
3. Write UTF-8 JSON with two-space indentation and a final newline.
4. Flush and close the temporary file.
5. Replace the target using `Path.replace`.
6. If writing or replacement fails, preserve the existing target.
7. Best-effort remove only the temporary file created by this operation.
8. Raise `StorageError` containing the operation and target path.

No retry is performed for deterministic local parse, permission, or disk errors.

### CSV export

1. The CLI supplies a destination beside `main.py`.
2. Open with exclusive creation mode, UTF-8, and `newline=""`.
3. Use `csv.DictWriter` with headers:
   `class_name,date,hours,notes`.
4. Export hours formatted with at most two decimal places.
5. Preserve commas, quotes, and newlines using standard CSV quoting.
6. On a failed new-file write, close and remove only the partial file.
7. Never overwrite a file that existed before the command.

## 6. CLI Contract

File: `study_tracker/cli.py`

```python
InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

def run(
    sessions_path: Path,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    today: date | None = None,
) -> int
```

`today` is fixed for a run when supplied by tests; otherwise field validation
and loading use the current local date.

### Parsing

- Show `Type 'help' for commands.` at startup.
- Prompt with `study-tracker> `.
- Split once into command and remaining argument text.
- Normalize command with `casefold()`.
- Reject arguments for `log`, `list`, `summary`, `help`, and `quit`.
- Require exactly one positive integer token for `delete`.
- Allow zero or one plain filename token for `export`.
- Reject export values that are absolute, contain `/` or `\`, or equal `.`/`..`.

### Command flows

#### `log`

1. Load and validate existing sessions before prompting.
2. If loading fails, print the storage error and return to the command prompt.
3. Prompt each field and pass it to its dedicated validator.
4. On `ValidationError`, print its message and repeat only that field.
5. Append one validated session to a copied list.
6. Save atomically.
7. Print success only after the save completes.

#### `list`

1. Load.
2. For empty data, print `No study sessions found.`
3. Number sessions newest-first.
4. Display number, date, class, and two-decimal hours.
5. Display notes only when non-empty.

#### `summary`

1. Load.
2. For empty data, print `No study sessions found.`
3. Print case-insensitively sorted class totals.
4. Print the overall total last.

#### `delete NUMBER`

1. Load.
2. Number sessions and validate the number.
3. Display the exact selected row.
4. Prompt `Delete this session? [y/N]: `.
5. Only `y` and `yes`, case-insensitively, confirm.
6. Compute deletion from the same loaded collection by calling
   `delete_session_by_number(sessions, number)`.
7. Save and report success.
8. Cancellation and errors do not save.

#### `export [FILENAME]`

1. Use `study_sessions.csv` when omitted.
2. Reject paths and invalid filename tokens.
3. Resolve the filename against `sessions_path.parent`.
4. Load sessions.
5. Export exclusively and report row count and filename.

#### `help` and `quit`

- `help` displays every command with one example.
- `quit` returns 0.
- `EOFError` and `KeyboardInterrupt` print a short goodbye and return 0.

## 7. Stable Message Contract

Exact messages required by `SPEC.md`:

| Condition | Exact text |
|-----------|------------|
| Non-numeric hours | `Please enter hours as a number.` |
| Hours outside range | `Hours must be greater than 0 and no more than 24.` |
| Empty list/summary | `No study sessions found.` |

Plan-defined stable messages:

| Condition | Required content |
|-----------|------------------|
| Invalid date | Contains `YYYY-MM-DD` |
| Invalid class | Contains `class name` and `1 to 100` |
| Oversized notes | Contains `notes` and `500` |
| Corrupt/unreadable JSON | Contains operation, `sessions.json`, and no traceback |
| Invalid delete | Contains `delete NUMBER` or valid numeric range |
| Existing export | Contains filename and `already exists` |
| Unknown command | Contains command and `help` |
| Successful log | Contains `saved` |
| Successful delete | Contains `deleted` |
| Successful export | Contains filename and exported row count |

Tests assert exact strings only where the specification mandates them.
Elsewhere, tests assert the required content case-insensitively.

## 8. Test-First Implementation Sequence

### Phase 1 — Amend the spec

Update `SPEC.md` with Section 2 decisions. Review for contradictions before any
runtime edit.

### Phase 2 — Domain tests and implementation

Create `tests/test_domain.py` first.

Required cases:

- Valid boundaries and trimming.
- Empty/oversized class and notes.
- Impossible, malformed, and future dates with fixed `today`.
- Numeric strings, JSON integers/floats, and two-decimal hours.
- Letters, booleans, NaN, infinity, zero, negative, over-24, and more than two
  decimal places.
- Missing-notes compatibility.
- Unknown/missing fields and wrong types with record number.
- Decimal-to-float-to-Decimal round trips for `0.1`, `1.25`, and `24`.
- Newest-first numbering and stable equal-date ordering.
- Case-insensitive summary spelling and totals.
- Exact deletion for storage order different from display order.
- Invalid deletion leaves input unchanged.

Implement `domain.py` until these tests pass.

### Phase 3 — Storage tests and implementation

Create `tests/test_storage.py` using `TemporaryDirectory`.

Required cases:

- Missing, valid, invalid UTF-8, invalid JSON, non-array, and malformed record.
- Persisted future dates using fixed `today`.
- Existing Biology record shape loads with empty notes.
- Successful four-field save and reload.
- Replacement failure preserves original bytes and removes the temporary file.
- CSV header, order, decimal formatting, commas, quotes, and newlines.
- Existing CSV is preserved.
- Failed new CSV write removes only its partial output.

Implement `storage.py` until these tests pass.

### Phase 4 — CLI tests and implementation

Create `tests/test_cli.py` with injected input/output and temporary paths.

Required cases:

- All commands and command case-insensitivity.
- Argument validation.
- Corrupt file followed by `log` produces no field prompts and no file change.
- Each field retries independently with the defined message behavior.
- Empty list and summary.
- List ordering and optional notes display.
- Summary grouping and total formatting.
- Confirmed, canceled, and invalid deletion.
- The second displayed row deletes the correct original record.
- Default/custom filename export.
- Absolute and directory-containing export names are rejected.
- Existing and failed export behavior.
- Unknown command, `EOFError`, and `KeyboardInterrupt`.
- No expected user or storage error prints a traceback.

Implement `cli.py` until these tests pass.

### Phase 5 — Entry point and import verification

Before replacing `main.py`, verify that the new package wins over the legacy
`study_tracker.py` module:

```powershell
py -c "import study_tracker; print(study_tracker.__file__)"
```

The printed path must end in `study_tracker\__init__.py`.

Then reduce `main.py` to:

- Resolve `sessions.json` beside itself.
- Delegate to `cli.run`.
- Return/raise the CLI exit code.

Do not modify or import the legacy comparison files.

### Phase 6 — Documentation and acceptance

Update `README.md` with:

- Python requirement and run command.
- Command table and examples.
- JSON and CSV locations.
- Filename-only export rule.
- Test command.

Run:

```powershell
py -m unittest discover -s tests -v
```

Verify:

- All acceptance criteria have tests.
- Tests do not alter real `sessions.json`.
- Existing Biology session remains readable.
- `git diff` contains no legacy comparison-file changes.

## 9. Acceptance Traceability

| Acceptance criterion | Implementation boundary | Primary tests |
|----------------------|-------------------------|---------------|
| Runs on Python 3.10+ | `main.py`, `cli.py` | Import/startup smoke test |
| Persists valid log | CLI -> domain -> storage | CLI log and storage reload |
| Invalid input does not exit | Validators and CLI retry loops | Field-specific retry tests |
| Lists newest-first | `number_sessions` | Stable ordering and CLI output |
| Correct summaries | `summarize_sessions` | Casefold and Decimal total tests |
| Deletes exact row | `delete_session_by_number` | Non-storage-order deletion test |
| Safe four-column CSV | `export_sessions` | Export content/failure tests |
| Tests protect real data | Injected paths | Temporary-path audit |

## 10. Security and Resilience Boundaries

- No shell execution, dynamic code evaluation, networking, or secrets.
- All terminal and persisted values pass through the same field validators.
- A load error blocks all mutation.
- A temporary JSON file never becomes authoritative until replacement succeeds.
- CSV export never overwrites.
- Expected errors are specific; unexpected programmer errors remain visible
  during tests.
- No retries for local permission, parse, replacement, or disk failures.

## 11. Exit Criteria

Plan v2 is ready for a second critique when:

1. Every red and yellow finding maps to the modifications above.
2. No white/noise finding expanded the design.
3. The plan contains no implementation code body or unresolved placeholder.

Implementation may begin only after:

1. The second critique finds no unresolved real problem, or any real finding is
   addressed in another revision.
2. `SPEC.md` contains the accepted amendments.
3. The final approved plan is committed with the critique artifacts.
