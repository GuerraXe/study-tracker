# Study Tracker Technical Plan — Version 1

## 1. Executive Summary

Rebuild the current course project into the specification-driven Study Tracker
defined by `SPEC.md`. The finished program remains an interactive, single-user
Python CLI using only the standard library. It will support `log`, `list`,
`summary`, `delete NUMBER`, `export [FILENAME]`, `help`, and `quit`.

The implementation will replace the runtime behavior in `main.py` but preserve
`study_tracker.py` and `study_sessions.json` as untouched comparison artifacts.
The current `sessions.json` record will remain readable even though it predates
the new optional `notes` field.

**Status:** First-pass plan, ready for critique; not approved for implementation.

**Ownership:** User-owned course project on branch `main`.

**Protected files:** No `.lockedfiles` file exists. No protected-file approval
is required.

## 2. Pre-Flight Findings

1. `main.py` currently combines storage, validation, prompting, and display.
2. Current `sessions.json` contains:
   - `class_name: "Biology"`
   - `date: "2026-07-23"`
   - `hours: 1.5`
   - no `notes` key
3. The new spec requires four fields, including `notes`; strict enforcement
   without compatibility handling would reject existing data.
4. Current saving writes directly to `sessions.json`, while the spec requires a
   temporary-file write followed by replacement.
5. Current listing preserves JSON order, while the spec requires newest-first
   sorting and uses displayed numbers for deletion.
6. Current hours validation accepts values over 24; the spec caps hours at 24.
7. Current code has no summary, delete, export, help-command, corrupt-file
   handling, notes input, or automated tests.
8. All existing runtime imports are valid Python standard-library imports.
9. `study_tracker.py` uses a different data file and schema and must not be
   imported by the new application.

## 3. Requirements and Decisions

### Functional requirements

1. **FR-1:** `log` validates and saves class name, date, hours, and notes.
2. **FR-2:** `list` displays all sessions newest-first with numbered rows.
3. **FR-3:** `summary` prints totals by class and an overall total.
4. **FR-4:** `delete NUMBER` confirms and deletes exactly the displayed record.
5. **FR-5:** `export [FILENAME]` creates a four-column UTF-8 CSV without
   overwriting an existing file.
6. **FR-6:** `help` documents all commands and examples.
7. **FR-7:** `quit` exits without changing stored data.
8. **FR-8:** Missing data is treated as empty; malformed or unreadable data is
   reported and preserved.

### Non-functional requirements

1. Python 3.10+ and standard library only.
2. Existing valid data must survive the rebuild.
3. A failed save must not replace the last valid JSON file.
4. Tests must use temporary directories and never touch real course data.
5. User-caused validation and file errors must not display tracebacks.
6. The full test suite should run in under five seconds.

### Planning decisions

These decisions resolve gaps identified during the architecture review:

1. Treat a missing `notes` key as `""` when loading older clean-version data.
2. Reject dates later than the current local date.
3. Group class names case-insensitively while preserving the first spelling
   used for display.
4. Use `Decimal` for validation and totals; serialize hours as JSON numbers.
5. Concurrent program instances are unsupported.
6. Use paths relative to the project directory unless the user supplies an
   absolute CSV path.
7. Sort summary rows by class name, case-insensitively.
8. Exit cleanly on `EOFError` and `KeyboardInterrupt`.

Before implementation, add these decisions to `SPEC.md` so the spec remains the
source of truth.

## 4. Target Structure and Component Interfaces

```text
study-tracker/
├── main.py
├── SPEC.md
├── README.md
├── sessions.json
├── study_tracker/
│   ├── __init__.py
│   ├── cli.py
│   ├── models.py
│   ├── services.py
│   └── storage.py
└── tests/
    ├── test_cli.py
    ├── test_models.py
    ├── test_services.py
    └── test_storage.py
```

### `main.py`

```python
def main() -> int
```

Resolve the project-local `sessions.json` path and delegate to
`study_tracker.cli.run`. Convert the return value into the process exit code.

### `study_tracker/models.py`

```python
@dataclass(frozen=True)
class StudySession:
    class_name: str
    date: date
    hours: Decimal
    notes: str = ""

class SessionValidationError(ValueError): ...

def create_session(
    class_name: str,
    date_text: str,
    hours_text: str,
    notes: str,
    *,
    today: date | None = None,
) -> StudySession

def session_from_dict(value: object, record_number: int) -> StudySession
def session_to_dict(session: StudySession) -> dict[str, object]
```

Responsibilities:

- Trim class name and notes.
- Enforce class length 1–100 and notes length 0–500.
- Parse a real ISO date and reject future dates.
- Parse finite decimal hours with `0 < hours <= 24`.
- Normalize a missing JSON `notes` key to an empty string.
- Reject wrong root types, required-field omissions, booleans used as hours,
  non-finite hours, and unexpected field types.

### `study_tracker/storage.py`

```python
class StorageError(RuntimeError): ...
class DataFormatError(StorageError): ...
class ExportError(StorageError): ...

def load_sessions(path: Path) -> list[StudySession]
def save_sessions(path: Path, sessions: Sequence[StudySession]) -> None
def export_sessions(path: Path, sessions: Sequence[StudySession]) -> None
```

Responsibilities:

- Return `[]` when the JSON path does not exist.
- Decode UTF-8 JSON and require an array root.
- Validate every record with its one-based record number.
- Serialize with two-space indentation and a final newline.
- Create a uniquely named temporary file in the destination directory.
- Flush, close, and replace the JSON file using `Path.replace`.
- Remove only the operation's temporary file after failed writes.
- Open CSV with exclusive creation mode, `newline=""`, and UTF-8 encoding.
- Write headers `class_name,date,hours,notes` using `csv.DictWriter`.
- Remove a partially created CSV when its write fails.
- Wrap expected OS/JSON errors with actionable filenames.

### `study_tracker/services.py`

```python
@dataclass(frozen=True)
class NumberedSession:
    number: int
    original_index: int
    session: StudySession

@dataclass(frozen=True)
class ClassTotal:
    class_name: str
    hours: Decimal

def number_sessions(
    sessions: Sequence[StudySession],
) -> list[NumberedSession]

def summarize_sessions(
    sessions: Sequence[StudySession],
) -> tuple[list[ClassTotal], Decimal]

def delete_numbered_session(
    sessions: Sequence[StudySession],
    numbered: Sequence[NumberedSession],
    number: int,
) -> list[StudySession]
```

Responsibilities:

- Produce newest-first rows without mutating storage order.
- Keep the original index attached to each displayed row.
- Use original input order as the tie-breaker for identical dates.
- Merge class totals using `casefold()`.
- Preserve the first encountered spelling for summary display.
- Return a new list after deletion.
- Reject out-of-range deletion numbers.

### `study_tracker/cli.py`

```python
InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

def run(
    sessions_path: Path,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> int
```

Responsibilities:

- Display an initial help hint and a `study-tracker> ` prompt.
- Split input into a case-insensitive command and arguments.
- Reject unexpected arguments with command-specific usage.
- Reload JSON before every command that reads or changes sessions.
- Translate validation and storage exceptions to concise messages.
- Never save after a load failure.
- Handle `EOFError` and `KeyboardInterrupt` as clean exits.

Command handlers:

- `log`: loop on individual invalid fields, construct one session, append, save.
- `list`: load, number, and display rows; show notes only when non-empty.
- `summary`: load, group, sort, and display class totals plus overall total.
- `delete NUMBER`: load, number, validate range, display selected row, prompt
  `Delete this session? [y/N]:`, and save only after `y` or `yes`.
- `export [FILENAME]`: load, resolve destination, refuse overwrite, and report
  row count and resulting path.
- `help`: print syntax and one example per command.
- `quit`: return exit code 0.

## 5. Data Flow and Failure Paths

### Log and save

```text
User input
  -> CLI field prompts
  -> models.create_session
      -> validation failure: print exact message and retry that field
      -> valid StudySession
  -> storage.load_sessions
      -> load failure: print error, do not save
  -> append in memory
  -> storage.save_sessions
      -> write temp
      -> flush and close
      -> replace sessions.json
      -> failure: preserve original, clean temp, print error
  -> success message
```

### List and delete

```text
sessions.json
  -> load and validate every record
  -> services.number_sessions
      -> sorted display rows retain original indexes
  -> user chooses displayed NUMBER
  -> confirmation
      -> no: no mutation
      -> yes: remove original index from a copied list
  -> atomic save
```

### Summary

```text
sessions.json
  -> validated StudySession objects
  -> casefolded class grouping
  -> Decimal addition
  -> alphabetical class totals
  -> overall total
  -> two-decimal terminal output
```

### Export

```text
sessions.json
  -> validated StudySession objects
  -> resolve CSV destination
  -> exclusive create
      -> exists/unwritable: report, preserve existing files
  -> DictWriter header and rows
  -> success path and row count
```

## 6. Implementation Sequence

### Step 1 — Align the specification

Modify `SPEC.md` to record the eight planning decisions above. Do not change
runtime code in this step.

Verification:

- No placeholders or contradictory rules remain.
- Existing missing-notes compatibility is explicit.
- Future-date and class-grouping behavior is testable.

### Step 2 — Add model tests, then model

Create `tests/test_models.py` first with cases for:

- Valid minimum and maximum values.
- Trimming.
- Empty and oversized class names.
- Empty and oversized notes.
- Invalid, impossible, and future dates.
- Non-numeric, zero, negative, over-24, boolean, NaN, and infinite hours.
- Dict serialization round-trip.
- Missing notes compatibility.
- Wrong fields and types with record-number diagnostics.

Implement `models.py` until these tests pass.

### Step 3 — Add storage tests, then storage

Create `tests/test_storage.py` using `TemporaryDirectory`:

- Missing file returns empty.
- Valid file loads.
- Current three-field Biology record loads with empty notes.
- Invalid UTF-8, invalid JSON, non-array root, and malformed record fail.
- Successful save produces valid four-field JSON.
- Simulated write/replace failure preserves the original.
- Temporary files are cleaned after failure.
- CSV header/order/quoting are correct.
- Existing CSV and failed CSV writes preserve destination state.

Implement `storage.py` until these tests pass.

### Step 4 — Add service tests, then services

Create `tests/test_services.py`:

- Newest-first order.
- Stable tie ordering.
- Original-index mapping.
- Deleting first, middle, and last displayed items.
- Invalid numbers do not mutate input.
- Case-insensitive summary grouping.
- Correct `Decimal` totals and alphabetical output.

Implement `services.py` until these tests pass.

### Step 5 — Add CLI tests, then CLI

Create `tests/test_cli.py` with injected input and output:

- Every valid command.
- Command case-insensitivity.
- Missing and extra arguments.
- Field retry behavior and exact messages.
- Empty list and summary behavior.
- Delete confirm, cancel, invalid number, and exact-record deletion.
- Default and custom export names.
- Unknown command help.
- Corrupt/load/write/export errors without tracebacks.
- EOF and keyboard interruption.

Implement `cli.py` until these tests pass.

### Step 6 — Replace the entry point

Reduce `main.py` to path resolution and `cli.run` delegation. Do not import or
modify the vibe-coded files.

Verification:

```powershell
py main.py
py -m unittest discover -s tests -v
```

### Step 7 — Documentation and acceptance verification

Update `README.md` with:

- Python prerequisite.
- Run command.
- Command table and examples.
- Storage and export locations.
- Statement that simultaneous instances are unsupported.
- Test command.

Manually verify every acceptance criterion using a copied or temporary JSON
file. Do not delete the existing Biology record during manual testing.

## 7. Test and Acceptance Matrix

| Criterion | Primary tests |
|-----------|---------------|
| AC-1 Python 3.10+ startup | Entry-point smoke test/manual run |
| AC-2 persistence after restart | Storage round-trip + CLI log/reload |
| AC-3 invalid input does not exit | Model and CLI retry tests |
| AC-4 newest-first stable list | Service numbering + CLI display |
| AC-5 class and overall totals | Service summary + CLI formatting |
| AC-6 exact confirmed deletion | Service index mapping + CLI confirmation |
| AC-7 safe four-column CSV | Storage export + CLI destination tests |
| AC-8 isolated automated tests | Temporary-directory audit |

Required final command:

```powershell
py -m unittest discover -s tests -v
```

Expected result: all tests pass, no test changes `sessions.json`, and
`git status --short` shows only intended source/documentation changes.

## 8. Security, Resilience, and Observability

- Do not evaluate input, invoke shells, or load executable configuration.
- Validate all persisted data again on every load.
- Use OS permissions; no application authentication is in scope.
- Do not log or transmit session data.
- Do not overwrite CSV destinations.
- Preserve valid JSON through atomic replacement.
- Report the operation and filename for expected file errors.
- Avoid retries for deterministic local permission, parse, and disk errors.
- No circuit breakers, tracing, metrics service, or remote alerts are warranted.

## 9. Cross-Boundary Impact

| Consumer | Change |
|----------|--------|
| Existing `sessions.json` | Missing `notes` normalized to empty text |
| New JSON writes | Always emit four fields |
| `main.py` | Becomes a minimal entry point |
| Terminal user | Numeric menu replaced by named commands |
| List/delete | Share one numbered-session mapping |
| Summary | Uses case-insensitive class grouping |
| CSV consumers | Receive fixed header and escaped UTF-8 rows |
| Tests | Use injected paths/input/output |
| `study_tracker.py` | No change; comparison artifact |
| `study_sessions.json` | No change; never loaded by new app |

No network API, database, mobile app, web app, worker, or message payload exists.

## 10. Risks and Mitigations

1. **Wrong record deleted after sorting — high impact.**
   Keep `original_index` in numbered rows and test non-storage order.
2. **Existing data rejected — medium impact.**
   Normalize only missing `notes`; test the current record shape explicitly.
3. **Original JSON lost during save — high impact.**
   Replace only after complete temp write; inject failures in tests.
4. **Tests alter real data — high impact.**
   Require explicit paths and temporary directories; no global test path.
5. **Decimal/JSON mismatch — medium impact.**
   Centralize conversion in model serialization and round-trip test it.
6. **Plan over-engineers a small CLI — medium likelihood.**
   Use four focused modules, standard library only, and no abstraction without a
   direct requirement or test-isolation purpose.

## 11. Milestones and Estimates

1. Spec alignment: 15–25 minutes, 90% confidence.
2. Models plus tests: 30–45 minutes, 85% confidence.
3. Storage/export plus tests: 60–90 minutes, 70% confidence.
4. Services plus tests: 30–45 minutes, 85% confidence.
5. CLI plus tests: 60–90 minutes, 70% confidence.
6. Documentation and acceptance pass: 30–45 minutes, 85% confidence.

Estimated total: 3.75–5.5 focused hours. The Windows atomic-replacement failure
tests and interactive CLI test harness are the main uncertainty.

## Plan Exit Criteria

The plan may proceed to implementation only after:

1. A critique has labeled findings as real problems, useful improvements, or
   noise.
2. Real and useful findings have been incorporated into `PLAN_v2.md`.
3. A second critique finds no unresolved real problem.
4. `SPEC.md` contains the accepted behavior decisions.
