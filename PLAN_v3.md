# Revise Summary

## 1. Critique Reconciliation

| Second-pass finding | Label | Plan v3 change |
|---------------------|-------|----------------|
| Public construction bypasses validation | 🔴 | `StudySession.__post_init__` enforces every typed invariant. A `validation_today` `InitVar` makes future-date enforcement deterministic in factories and tests. |
| Decimal-place error has no message | 🟡 | Define `Hours may have at most two decimal places.` and require a field retry. |
| Empty export behavior is unstated | 🟡 | Export creates a header-only CSV and reports zero rows. |
| Startup acceptance has no concrete step | 🟡 | Add a final PowerShell smoke test that sends `quit`, requires exit code 0, and rejects tracebacks. |

No module, feature, or external dependency was added.

## 2. Architectural Deltas

- `StudySession` now defends its own invariant instead of trusting callers.
- Parsed field validators remain separate so the CLI can retry one prompt.
- The export contract explicitly covers an empty session collection.
- The acceptance phase now verifies the real entry point, not only imports.

## 3. Trade-off Analysis

### Dataclass `InitVar` instead of a private model

A private model plus factory would rely on naming convention rather than enforce
validity. A custom class would require more code. A dataclass `InitVar` lets
`__post_init__` validate all construction paths while accepting a fixed
reference date for deterministic tests. The reference date is not stored,
serialized, compared, or displayed.

### Duplicate checks at parsing and construction boundaries

Field validators provide precise CLI messages and normalization.
`__post_init__` repeats the final typed invariant checks to protect storage,
summary, deletion, and export from invalid direct construction. The small amount
of repeated checking is intentional defense in depth, not duplicated business
logic: both layers use shared private predicate helpers.

---

# Study Tracker Technical Plan — Version 3

## 1. Objective and Scope

Build the local, interactive Python Study Tracker specified by `SPEC.md`.

Commands:

- `log`
- `list`
- `summary`
- `delete NUMBER`
- `export [FILENAME]`
- `help`
- `quit`

Constraints:

- Python 3.10 or newer
- Standard library only
- JSON storage beside `main.py`
- CSV exports beside `main.py`
- Tests never touch real course data

Preserve unchanged:

- `study_tracker.py`
- `study_sessions.json`

No `.lockedfiles` file exists.

## 2. Specification Amendments Before Implementation

Update `SPEC.md` with these accepted decisions:

1. Hours may contain no more than two decimal places.
2. Excess precision prints `Hours may have at most two decimal places.` and
   repeats the hours prompt.
3. Older records missing `notes` load with an empty note.
4. Future dates are rejected during both entry and file loading.
5. Class summaries group names case-insensitively and use the earliest stored
   spelling for display.
6. Export accepts a plain filename only and writes beside `main.py`.
7. Exporting no sessions creates a CSV containing only
   `class_name,date,hours,notes` and reports zero exported rows.
8. Simultaneous application instances are outside scope.
9. End-of-input and keyboard interruption exit without saving partial input.

Review the amended spec for contradictions before writing tests or runtime code.

## 3. Target Structure

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

The legacy `study_tracker.py` remains a comparison artifact. Before replacing
`main.py`, verify that importing `study_tracker.cli` resolves to the package.

## 4. Domain Design

File: `study_tracker/domain.py`

### Validated model

```python
@dataclass(frozen=True)
class StudySession:
    class_name: str
    date: date
    hours: Decimal
    notes: str = ""
    validation_today: InitVar[date | None] = None
```

`validation_today` is used only during `__post_init__`. When omitted, it resolves
to the current local date.

`__post_init__` enforces:

- `class_name` is a string already trimmed, length 1–100.
- `date` is a `datetime.date` and is not later than the reference date.
- `hours` is a finite `Decimal`, greater than 0, no greater than 24, and has no
  more than two decimal places.
- `notes` is a string already trimmed, length 0–500.
- Booleans and other type substitutions are rejected.

Direct construction and factory construction therefore share the same final
invariants. Invalid typed construction raises `ValidationError`; it cannot reach
storage or reporting.

### Validation error

```python
class ValidationError(ValueError):
    field: str
    message: str
```

Constructor contract:

```text
ValidationError(field=<stable identifier>, message=<user-facing text>)
```

Stable field identifiers:

- `class_name`
- `date`
- `hours`
- `notes`

### Field parsing and normalization

```python
validate_class_name(value: str) -> str
validate_session_date(value: str, *, today: date | None = None) -> date
validate_hours(value: str | int | float) -> Decimal
validate_notes(value: str) -> str
```

Each returns a normalized typed value or raises `ValidationError`.

Hours parsing rules:

- Letters or non-numeric input:
  `Please enter hours as a number.`
- Zero, negative, or over 24:
  `Hours must be greater than 0 and no more than 24.`
- More than two decimal places:
  `Hours may have at most two decimal places.`
- Reject booleans, NaN, and infinity.

After all fields parse, the CLI constructs `StudySession` using the same
reference date so `__post_init__` performs the final invariant check.

### Persistence conversion

```python
session_from_dict(
    value: object,
    record_number: int,
    *,
    today: date | None = None,
) -> StudySession

session_to_dict(session: StudySession) -> dict[str, object]
```

Loading:

- Require `class_name`, `date`, and `hours`.
- Normalize missing `notes` to `""`.
- Reject unknown fields and wrong types.
- Convert JSON numbers using `Decimal(str(value))`.
- Pass `today` into both date parsing and `StudySession` construction.
- Include the record number in malformed-data errors.

Saving:

- Emit exactly `class_name`, `date`, `hours`, and `notes`.
- Emit ISO date text.
- Convert validated `Decimal` hours to `float`.
- Never send a `Decimal` directly to `json.dump`.

Round-trip tests cover `0.1`, `1.25`, `2.30`, and `24`. Scale differences such
as `2.30` becoming `2.3` are acceptable because output is displayed to two
decimal places and numeric value is preserved.

### Pure collection behavior

```python
NumberedSession = tuple[int, int, StudySession]

number_sessions(
    sessions: Sequence[StudySession],
) -> list[NumberedSession]

summarize_sessions(
    sessions: Sequence[StudySession],
) -> tuple[list[tuple[str, Decimal]], Decimal]

delete_session_by_number(
    sessions: Sequence[StudySession],
    number: int,
) -> list[StudySession]
```

Rules:

- List newest dates first.
- Keep original storage order for equal dates.
- Number from one.
- A numbered tuple contains displayed number, original index, and session.
- Delete recomputes numbering from its supplied collection.
- Invalid deletion does not mutate input.
- Summary groups with `casefold()`, preserves earliest stored spelling, sorts
  classes case-insensitively, and returns an overall `Decimal` total.

## 5. Storage Design

File: `study_tracker/storage.py`

### Interfaces

```python
load_sessions(
    path: Path,
    *,
    today: date | None = None,
) -> list[StudySession]

save_sessions(
    path: Path,
    sessions: Sequence[StudySession],
) -> None

export_sessions(
    destination: Path,
    sessions: Sequence[StudySession],
) -> None
```

Expected exceptions:

- `StorageError`
- `DataFormatError`
- `ExportError`

### Load behavior

1. Missing JSON returns an empty list.
2. Decode UTF-8 and require an array root.
3. Validate every record with `session_from_dict`.
4. Pass the same `today` reference through the entire load.
5. Never return partial data.
6. Errors name the file and record number when applicable.

### Atomic save behavior

1. Serialize every validated session.
2. Create a unique temporary file in the target directory.
3. Write UTF-8 JSON with two-space indentation and final newline.
4. Flush and close.
5. Replace the destination with `Path.replace`.
6. On failure, preserve the original destination.
7. Best-effort remove only this operation's temporary file.
8. Raise an actionable `StorageError`; do not retry deterministic local errors.

### CSV behavior

1. Open destination in exclusive creation mode.
2. Use UTF-8, `newline=""`, and `csv.DictWriter`.
3. Always write `class_name,date,hours,notes` headers.
4. Write one row per session with hours formatted to at most two decimals.
5. For zero sessions, close the header-only file successfully and report zero.
6. Preserve commas, quotes, and internal newlines through CSV quoting.
7. On a failed new-file write, remove only the partial file.
8. Never overwrite a pre-existing destination.

## 6. CLI Design

File: `study_tracker/cli.py`

```python
run(
    sessions_path: Path,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    today: date | None = None,
) -> int
```

### Parsing

- Print `Type 'help' for commands.` once.
- Prompt with `study-tracker> `.
- Commands are case-insensitive.
- Reject arguments for `log`, `list`, `summary`, `help`, and `quit`.
- Require one positive integer for `delete`.
- Allow zero or one filename for `export`.
- Reject absolute export names, `/`, `\`, `.`, and `..`.
- Resolve accepted export names against `sessions_path.parent`.

### Command flows

`log`:

1. Load existing data before prompting.
2. Return to prompt on load failure.
3. Validate one field at a time.
4. Retry only the failed field.
5. Construct a self-validating `StudySession`.
6. Append to a copy and save atomically.
7. Print success only after saving.

`list`:

1. Load.
2. Print `No study sessions found.` when empty.
3. Display newest-first numbered rows with two-decimal hours.
4. Display notes only when non-empty.

`summary`:

1. Load.
2. Print `No study sessions found.` when empty.
3. Print sorted class totals and overall total to two decimals.

`delete NUMBER`:

1. Load and number the same collection.
2. Validate and display the selected row.
3. Prompt `Delete this session? [y/N]: `.
4. Confirm only `y` or `yes`.
5. Delete by recomputed number and atomically save.
6. Cancellation or error never saves.

`export [FILENAME]`:

1. Default to `study_sessions.csv`.
2. Validate filename-only input.
3. Load.
4. Export header plus all rows, including header-only output for zero sessions.
5. Report filename and row count.

`help` and `quit`:

- Help shows syntax and one example for every command.
- Quit returns 0.
- `EOFError` and `KeyboardInterrupt` print a brief goodbye and return 0.

## 7. Message Contract

Exact:

| Condition | Text |
|-----------|------|
| Non-numeric hours | `Please enter hours as a number.` |
| Hours out of range | `Hours must be greater than 0 and no more than 24.` |
| Excess decimal places | `Hours may have at most two decimal places.` |
| Empty list/summary | `No study sessions found.` |

Content-based:

| Condition | Required content |
|-----------|------------------|
| Invalid date | `YYYY-MM-DD` |
| Invalid class | `class name`, `1 to 100` |
| Oversized notes | `notes`, `500` |
| Corrupt data | operation, filename, no traceback |
| Invalid delete | usage or valid range |
| Existing export | filename, `already exists` |
| Unknown command | command, `help` |
| Successful log/delete | `saved` or `deleted` |
| Successful export | filename and row count, including `0` |

Tests use exact matching only for the exact table.

## 8. Test-First Sequence

### Phase 1 — Update `SPEC.md`

Record all Section 2 amendments and verify no contradiction remains.

### Phase 2 — Domain tests, then `domain.py`

Test:

- Direct `StudySession` construction with every invalid typed value.
- Fixed `validation_today` behavior.
- Every field validator and exact hours messages.
- Missing-note loading.
- Unknown/missing fields and record diagnostics.
- Decimal JSON round trips.
- Stable numbering.
- Case-insensitive summary.
- Exact deletion when storage and display orders differ.
- No mutation after invalid deletion.

### Phase 3 — Storage tests, then `storage.py`

Use temporary directories for:

- Missing and valid files.
- Invalid encoding, JSON, root, and records.
- Future persisted dates with fixed `today`.
- Existing Biology record without notes.
- Successful save/reload.
- Replace failure preserving original bytes and cleaning temporary output.
- CSV quoting and numeric formatting.
- Header-only zero-session export.
- Existing/failed export preservation.

### Phase 4 — CLI tests, then `cli.py`

Inject input, output, date, and temporary paths.

Test:

- Every command and case-insensitive parsing.
- Argument validation.
- Load failure before log prompts.
- Independent field retries, including excess decimal places.
- Empty list and summary.
- List and summary formatting.
- Correct confirmed deletion and canceled deletion.
- Filename-only export and zero-row success.
- Existing and failed export.
- Unknown command, EOF, and interrupt.
- No traceback for expected failures.

### Phase 5 — Package and entry point

After creating the package, verify resolution:

```powershell
py -c "import study_tracker; print(study_tracker.__file__)"
```

The path must end in `study_tracker\__init__.py`.

Then make `main.py` resolve project-local `sessions.json`, call `cli.run`, and
propagate exit code 0.

### Phase 6 — Full verification

Run unit tests:

```powershell
py -m unittest discover -s tests -v
```

Run the real entry-point smoke test:

```powershell
"quit" | py .\main.py
```

Smoke-test acceptance:

- Process exit code is 0.
- Startup prompt/help hint appears.
- Goodbye output appears.
- No traceback appears.
- `sessions.json` is byte-for-byte unchanged.

Update `README.md`, then confirm:

- Existing Biology data still loads.
- Tests never changed real course data.
- Legacy comparison files have no diff.
- Every `SPEC.md` acceptance criterion maps to a passing test or smoke check.

## 9. Acceptance Traceability

| Criterion | Boundary | Verification |
|-----------|----------|--------------|
| Python 3.10+ startup | `main.py`, package import | Real entry-point smoke test |
| Persistent log | CLI/domain/storage | CLI test plus reload |
| Invalid input survives | Validators/CLI | Field retry tests |
| Newest-first list | Domain/CLI | Ordering and display tests |
| Correct totals | Domain/CLI | Decimal grouping tests |
| Exact deletion | Domain/storage | Display-vs-storage-order test |
| Safe CSV | Storage/CLI | Normal, empty, existing, and failed export tests |
| Real-data isolation | All tests | Temporary paths plus final byte comparison |

## 10. Risks and Controls

| Risk | Control |
|------|---------|
| Invalid direct model construction | `__post_init__` invariant |
| Decimal JSON failure | Boundary conversion plus round-trip tests |
| Clock-dependent tests | `validation_today`/`today` injection |
| Wrong sorted deletion | Recompute mapping internally |
| Corrupt file overwritten | Load before mutation and atomic save |
| Export outside project | Filename-only validation |
| Empty export ambiguity | Header-only contract |
| Broken real entry point | PowerShell smoke test |

## 11. Exit Criteria

Plan v3 is approved for the planning-loop checkpoint when:

1. A final critique finds no unresolved real problem.
2. `SPEC.md` receives the accepted amendments before implementation.
3. `PLAN_v1.md`, `CRITIQUE_v1.md`, `PLAN_v2.md`, `CRITIQUE_v2.md`, and
   `PLAN_v3.md` are committed as planning artifacts.

No implementation begins during Module 5.
