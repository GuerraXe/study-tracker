# Architecture Review: Study Tracker Specification | Status: Revise, Then Implement

## Executive Summary

The specification is appropriately bounded for a single-user Python CLI and is
substantially more testable than the existing implementation. It defines the
core commands, validation behavior, storage format, failure cases, and explicit
non-goals. Before implementation, several data-compatibility and command-contract
details should be resolved. None requires expanding the product scope.

Pre-flight verification completed:

- Read `SPEC.md`, `main.py`, `study_tracker.py`, `README.md`, `sessions.json`,
  and `study_sessions.json`.
- Traced terminal input through validation, JSON loading/saving, and terminal
  output in the current clean implementation.
- Confirmed all current imports are Python standard-library symbols used at
  their call sites.
- No `.lockedfiles` file exists; no protected-file approval is required.
- The legacy `study_tracker.py` and `study_sessions.json` are comparison
  artifacts and must not become dependencies of the rebuilt application.

## Critical Issues (Must Fix)

1. **Existing data conflicts with the new schema**: Data Model | The current
   `sessions.json` record has no `notes` field, while the spec requires each
   object to have exactly four fields and says malformed records make the whole
   file unreadable. | The user's existing Biology record would become unusable.
   | Accept a missing `notes` field as an older valid record and normalize it to
   an empty string when loading; continue rejecting missing required fields or
   unexpected value types.
2. **Class grouping is ambiguous**: `summary` | The spec does not say whether
   `Biology`, `biology`, and ` Biology ` represent the same class. | Totals may
   be split unexpectedly. | Trim class names and group case-insensitively while
   preserving the first-entered display spelling.
3. **Deletion identity needs an explicit mapping**: `delete NUMBER` | Numbers
   come from a newest-first sorted view, but JSON storage order may differ. |
   A naive implementation can delete the wrong list element. | Build a sorted
   list of `(original_index, session)` pairs and delete by `original_index`.
4. **Atomic-save failure behavior is incomplete**: Storage | The spec requires
   temporary-file replacement but does not define cleanup or preservation on
   failure. | A failed save could leave debris or obscure the original error. |
   Write in the destination directory, flush and close before replacement,
   preserve the original file on failure, and best-effort remove only the
   temporary file created by that operation.

## Major/Minor Issues

1. **Major — Future dates**: Decide whether a session date may be later than
   today. Recommendation: reject future dates because the program logs completed
   study activity.
2. **Major — CSV destination boundary**: Decide whether `export` accepts paths or
   filenames only. Recommendation: accept a filename or path supplied by the
   user, resolve it relative to the project root, and never overwrite.
3. **Major — Corrupt-record granularity**: The spec implies one malformed record
   blocks all commands. Recommendation: fail the entire load with the record
   number in the error; do not silently drop data.
4. **Major — Save concurrency**: Atomic replacement does not prevent two running
   program instances from overwriting one another. Recommendation: document
   concurrent execution as unsupported for this single-user version.
5. **Minor — Notes and CSV newlines**: Optional notes may contain commas or
   newlines. Recommendation: use Python's `csv.DictWriter`, which quotes fields
   correctly; accept internal whitespace but trim leading/trailing whitespace.
6. **Minor — Summary ordering**: Output order is unspecified. Recommendation:
   sort classes case-insensitively and print the overall total last.
7. **Minor — Floating-point totals**: Binary floats can produce rounding
   surprises. Recommendation: parse and calculate hours with `Decimal`, serialize
   hours as a JSON number, and format to two decimal places.
8. **Minor — EOF and keyboard interruption**: `Ctrl+Z`, `Ctrl+C`, and closed
   input are unspecified. Recommendation: exit cleanly without modifying data.

## Questions & Risks

1. Should future dates be rejected? The plan assumes yes.
2. Should class summaries merge names that differ only by capitalization? The
   plan assumes yes.
3. Should concurrent program instances be supported? The plan assumes no.
4. Is backward compatibility with the current missing-`notes` record required?
   The plan assumes yes to preserve existing course data.
5. The greatest implementation risk is deleting the wrong underlying record
   after sorting the display.

---

# Study Tracker Architecture Plan

## 1. Executive Summary

**Purpose:** Rebuild the study tracker from `SPEC.md` as a reliable local Python
CLI with explicit validation, storage, reporting, deletion, and CSV export.

**In scope:** Interactive `log`, `list`, `summary`, `delete`, `export`, `help`,
and `quit` commands; JSON persistence; CSV export; automated unit tests.

**Out of scope:** Network services, authentication, databases, GUIs, cloud
sync, imports, editing, weekly reports, and third-party packages.

**Ownership:** Single-user course project maintained in this repository.

**Status:** Architecture proposed; resolve the review assumptions before coding.

**Constraints:** Python 3.10+, standard library only, Windows PowerShell-friendly,
and no changes to legacy comparison files.

## 2. Requirements

### Functional requirements

1. **FR-1 Log:** Accept and validate class name, date, hours, and optional notes,
   then atomically persist exactly one session.
2. **FR-2 List:** Display all sessions newest-first with a one-based number,
   date, class, hours to two decimals, and notes when present.
3. **FR-3 Summary:** Display totals grouped case-insensitively by class and an
   overall total, all to two decimal places.
4. **FR-4 Delete:** Parse `delete NUMBER`, show the selected session, require
   confirmation, and remove exactly that record.
5. **FR-5 Export:** Create a UTF-8 CSV with the specified header and refuse to
   overwrite an existing destination.
6. **FR-6 Help:** Display command syntax and examples for every command.
7. **FR-7 Quit:** Exit successfully without modifying data.
8. **FR-8 Recovery:** Treat a missing JSON file as empty; report corrupt or
   unreadable data without overwriting it.
9. **FR-9 Compatibility:** Load older clean-version records with a missing
   `notes` field as though `notes` were an empty string.

### Non-functional requirements

1. **NFR-1 Runtime:** Start and display the prompt within one second for up to
   10,000 local sessions on a typical student computer.
2. **NFR-2 Durability:** Never replace the existing JSON file until the complete
   new JSON document has been written and closed successfully.
3. **NFR-3 Test isolation:** Automated tests use temporary directories and never
   read or modify the project's real `sessions.json`.
4. **NFR-4 Compatibility:** Run on CPython 3.10 or newer with no external package.
5. **NFR-5 Diagnostics:** User-facing failures identify the operation and file
   involved without exposing a Python traceback during normal use.
6. **NFR-6 Coverage:** Tests exercise every command and every acceptance
   criterion; all tests must pass before implementation is accepted.

## 3. Visual Overviews

### Context

```text
┌───────────────┐       typed commands       ┌─────────────────────┐
│ Student       │ ─────────────────────────> │ Study Tracker CLI   │
│ (local user)  │ <───────────────────────── │ Python 3.10+        │
└───────────────┘       text results         └──────────┬──────────┘
                                                       │ local I/O
                                            ┌──────────▼──────────┐
                                            │ JSON / CSV files    │
                                            │ on local disk       │
                                            └─────────────────────┘
```

### Components

```text
┌──────────┐   parsed command   ┌──────────────┐   operations   ┌────────────┐
│ CLI      │ ─────────────────> │ Services     │ ─────────────> │ Storage    │
│ prompts  │ <───────────────── │ validation   │ <───────────── │ JSON / CSV │
└──────────┘   result/error     └──────┬───────┘   sessions     └────────────┘
                                      │
                               ┌──────▼───────┐
                               │ StudySession│
                               │ data model  │
                               └──────────────┘
```

### Data flow: log with failure path

```text
Student        CLI          Validation       Storage        sessions.json
   │            │               │               │                 │
   │ log        │               │               │                 │
   ├───────────>│ prompt fields │               │                 │
   │            ├──────────────>│               │                 │
   │            │ invalid       │               │                 │
   │            │<──────────────┤               │                 │
   │ retry      │               │               │                 │
   │<───────────┤               │               │                 │
   │ values     │ validate      │               │                 │
   ├───────────>├──────────────>│ valid session │                 │
   │            │               ├──────────────>│ temp + replace  │
   │            │               │               ├────────────────>│
   │            │ success/error │<──────────────┤                 │
   │ result     │<──────────────┤               │                 │
   │<───────────┤               │               │                 │
```

## 4. Component Specs

### `main.py`

- **Responsibility:** Minimal executable entry point.
- **Interface:** `main() -> int`; process exits with its return code.
- **Dependencies:** `study_tracker.cli.run`.
- **State:** None.

### `study_tracker/models.py`

- **Responsibility:** Define and validate the in-memory session model.
- **Interface:** `StudySession(class_name: str, date: date, hours: Decimal,
  notes: str)` using a frozen standard-library `dataclass`.
- **Dependencies:** `dataclasses`, `datetime`, `decimal`.
- **State:** Immutable session values.

### `study_tracker/storage.py`

- **Responsibility:** Load, validate, atomically save JSON, and export CSV.
- **Interfaces:**
  - `load_sessions(path: Path) -> list[StudySession]`
  - `save_sessions(path: Path, sessions: Sequence[StudySession]) -> None`
  - `export_csv(path: Path, sessions: Sequence[StudySession]) -> None`
- **Dependencies:** `json`, `csv`, `os`, `pathlib`, model serialization helpers.
- **State:** Files supplied explicitly by path; no hidden global test state.

### `study_tracker/services.py`

- **Responsibility:** Sort, summarize, and map displayed numbers back to stored
  records.
- **Interfaces:**
  - `numbered_sessions(sessions) -> list[NumberedSession]`
  - `summarize(sessions) -> Summary`
  - `delete_number(sessions, number) -> list[StudySession]`
- **Dependencies:** Models only.
- **State:** Pure transformations returning new collections.

### `study_tracker/cli.py`

- **Responsibility:** Interactive command loop, parsing, prompts, formatting,
  confirmations, and user-facing error translation.
- **Interface:** `run(input_fn=input, output_fn=print) -> int`.
- **Dependencies:** Models, services, and storage.
- **State:** Current loaded list refreshed before data-sensitive commands.

### `tests/`

- **Responsibility:** Unit and command-level behavioral verification.
- **Interface:** `py -m unittest discover -s tests -v`.
- **Dependencies:** `unittest`, `tempfile`, application components.
- **State:** Temporary directories only.

## 5. API Contracts

There is no network API, authentication, rate limit, or remote versioning.
The public boundary is the interactive CLI:

| Command | Arguments | Success | Failure |
|---------|-----------|---------|---------|
| `log` | none | Prompts, then `Study session saved.` | Field-specific retry or storage error |
| `list` | none | Numbered newest-first rows | Empty-data or load-error message |
| `summary` | none | Sorted class totals plus overall | Empty-data or load-error message |
| `delete` | one positive integer | Confirm, save, acknowledge | Usage, range, cancel, or storage error |
| `export` | zero or one path | Reports created path and row count | Usage, exists, load, or write error |
| `help` | none | Command table and examples | Extra arguments produce usage |
| `quit` | none | Exit code 0 | Extra arguments produce usage |

Command parsing splits once into command and remaining arguments. Command names
are normalized with `casefold()`. The CLI contract is versioned by `SPEC.md`;
breaking changes require a specification update before code changes.

## 6. Data Model

### `StudySession`

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `class_name` | string | yes | trimmed, 1–100 characters |
| `date` | ISO string in JSON / `date` in memory | yes | real `YYYY-MM-DD`, not future |
| `hours` | JSON number / `Decimal` in memory | yes | `0 < hours <= 24` |
| `notes` | string | yes in new writes | trimmed, 0–500 characters |

Cardinality is one JSON file to zero or more sessions. Lifecycle operations are
create, read, summarize, export, and hard delete. There is no update or archive.
Missing `notes` is the only legacy normalization. Unknown fields may be rejected
to expose schema drift; field type or constraint failures identify the record
number and block the load.

## 7. Security

- **Threat model:** Malformed local files, path mistakes during export,
  formula-like CSV cells, and accidental overwrite are the relevant local risks.
- **Authorization:** OS file permissions are the only access control; RBAC/ABAC
  is not applicable to a single local user.
- **Input controls:** Length/range/date checks; no `eval`, shell invocation, or
  dynamic imports. CSV is data, but values beginning with `=`, `+`, `-`, or `@`
  should be prefixed with an apostrophe on export to reduce spreadsheet formula
  injection risk.
- **Encryption:** No transit exists. At-rest encryption is delegated to the OS
  and is explicitly outside product scope.
- **Secrets:** The application uses no secrets or credentials.
- **Paths:** Never overwrite export destinations; temporary JSON files are
  created only beside the configured JSON file.

## 8. Resilience

- **JSON reads:** No retry; local parse or permission failures return immediately
  with an actionable error.
- **JSON writes:** One atomic write attempt. On failure, preserve the original
  and best-effort clean the operation's temporary file. No retry or backoff,
  because repeated local permission/disk failures are unlikely to self-heal.
- **CSV writes:** Exclusive creation mode; partial file is removed only if it was
  created by the failed operation.
- **Fallback:** Missing JSON maps to an empty collection. Corrupt JSON has no
  automatic fallback, repair, or overwrite.
- **Timeout/circuit breakers:** Not applicable; there are no remote calls.
- **Interrupts:** `KeyboardInterrupt` or `EOFError` exits cleanly. A save already
  in its atomic replacement stage completes or leaves the previous file intact.

## 9. Observability

- User messages report command success, validation failures, filenames, and
  record counts.
- Unexpected programmer errors are not swallowed in tests; expected storage and
  validation errors are translated to concise CLI messages.
- No telemetry, tracing, remote logging, or alerts are justified for a local
  course CLI.
- Test metrics:
  - 100% of acceptance criteria have at least one automated test.
  - Zero tests touch the real project data file.
  - Full suite target: under five seconds.

## 10. Plan

### Phase 1 — Resolve specification decisions

1. Update `SPEC.md` with the decisions on future dates, case-insensitive class
   grouping, missing-note compatibility, and unsupported concurrency.
2. Treat the updated spec as the implementation contract.

**Estimate:** 15–25 minutes; confidence 90%.

### Phase 2 — Model and storage

1. Add the package structure and `StudySession` model.
2. Implement strict load validation plus missing-note normalization.
3. Implement atomic JSON save and exclusive CSV export.
4. Add isolated storage/model tests.

**Estimate:** 60–90 minutes; confidence 75%.

### Phase 3 — Services and CLI

1. Implement sorted numbering, summary grouping, and exact deletion mapping.
2. Implement command parser, prompts, confirmation, formatting, and help.
3. Reduce `main.py` to the entry point.
4. Add command-level tests with injected input/output.

**Estimate:** 90–120 minutes; confidence 70%.

### Phase 4 — Verification and documentation

1. Run the complete test suite.
2. Manually exercise every command with temporary or backed-up course data.
3. Update `README.md` with commands and examples.
4. Compare implementation against every acceptance criterion.

**Estimate:** 30–45 minutes; confidence 85%.

### Technical risks

- Incorrect sorted-number deletion: medium likelihood, high impact.
- Accidentally rejecting the existing record: high likelihood without the
  compatibility rule, medium impact.
- Atomic file behavior differing on Windows: medium likelihood, medium impact;
  test in the project environment.
- CSV formula interpretation: low likelihood, medium impact.

## 11. Cross-Boundary Impact Analysis

The session schema changes from the current three-field clean record to a
four-field record with `notes`.

| Boundary/Consumer | Impact | Required update |
|-------------------|--------|-----------------|
| `sessions.json` | Existing record lacks `notes` | Normalize missing notes to `""` on load |
| `main.py` | Current direct functions and numeric menu do not implement commands | Replace with minimal package entry point |
| CLI display | Must show optional notes and sorted numbering | Add consistent formatter |
| Summary service | Consumes class names and hours | Case-insensitive grouping and `Decimal` totals |
| Delete service | Consumes displayed number | Preserve original storage index through sorting |
| CSV export | New external file representation | Emit fixed four-column header and escaped values |
| Automated tests | Must not touch real data | Inject paths and use temporary directories |
| Legacy `study_tracker.py` | Comparison artifact only | No change; do not import |
| Legacy `study_sessions.json` | Different schema and purpose | No migration; do not read |

There are no mobile, web, background-worker, network API, database, or message
bus consumers.
