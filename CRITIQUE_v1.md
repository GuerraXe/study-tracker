# Critique of Study Tracker Technical Plan v1

## Pre-Flight Verification

- Read `PLAN_v1.md`, `SPEC.md`, `ARCHITECTURE.md`, `main.py`, `README.md`,
  `sessions.json`, `study_tracker.py`, and `study_sessions.json`.
- Confirmed the current runtime data flow:
  terminal input -> validation in `main.py` -> dictionaries -> direct JSON write.
- Confirmed the current clean data has three keys and no `notes`.
- Confirmed current imports and call sites with `rg`.
- Confirmed no `.lockedfiles` file exists, so the plan proposes no unauthorized
  protected-file modification.
- Proposed package functions do not exist yet; their signatures were evaluated
  as contracts rather than falsely treated as verified implementation.
- No framework mechanics are involved; the plan uses the Python standard library.

## Executive Assessment

The plan is substantially implementable and directly addresses the largest
risks: preserving existing data, preventing wrong-record deletion after sorting,
isolating tests, and protecting JSON during failed saves. Its phased
test-first sequence is strong.

However, two core type/error contracts are incomplete, and several plan choices
silently extend or reinterpret `SPEC.md`. Those issues should be resolved before
implementation. A few proposed abstractions may also be heavier than this small
CLI needs.

## Findings

### Finding 1 — `Decimal` cannot be serialized by `json` as planned

**Label:** 🔴 Real problem  
**Severity:** Must fix  
**Area:** Model/storage boundary

**Problem:** `StudySession.hours` is a `Decimal`, while `session_to_dict` returns
a dictionary intended for `json.dump`. Python's standard JSON encoder does not
serialize `Decimal` values by default. The plan says hours will remain a JSON
number and says conversion will be centralized, but never defines the actual
conversion or precision rule.

**Impact:** A direct implementation of the proposed types will raise
`TypeError: Object of type Decimal is not JSON serializable` during every save.
Converting to `float` fixes serialization but may introduce precision artifacts.
Converting to `str` violates the spec's JSON-number requirement.

**Recommendation:** Add an explicit contract:

- Limit input to at most two decimal places.
- Keep `Decimal` in memory for validation and totals.
- Convert to `float` only inside `session_to_dict`.
- Parse JSON `int`/`float` through `Decimal(str(value))`.
- Add round-trip tests for `0.1`, `1.25`, and `24`.

### Finding 2 — Validation errors cannot support field-specific retries

**Label:** 🔴 Real problem  
**Severity:** Must fix  
**Area:** Model/CLI boundary

**Problem:** `create_session` accepts all four raw fields at once and raises one
undifferentiated `SessionValidationError`. The CLI requirement says to retry only
the invalid field with its exact message, but the exception contract has no
`field` or error code.

**Impact:** The CLI must either inspect error text, repeat all prompts, duplicate
validation outside the model, or violate the field-specific retry behavior.
Each option is brittle.

**Recommendation:** Define focused validators such as:

```python
validate_class_name(value: str) -> str
validate_date(value: str, *, today: date | None = None) -> date
validate_hours(value: str) -> Decimal
validate_notes(value: str) -> str
```

Have the CLI retry each validator independently. `create_session` can accept
already validated typed values.

### Finding 3 — Future-date validation is nondeterministic when loading JSON

**Label:** 🔴 Real problem  
**Severity:** Major  
**Area:** Model/storage tests

**Problem:** `create_session` accepts an injectable `today`, but
`session_from_dict(value, record_number)` does not. If persisted sessions are
also checked for future dates, storage tests depend on the actual clock. If
persisted sessions are not checked, the plan's promise to validate every record
is incomplete.

**Impact:** Tests may begin failing as dates change, and interactive validation
may disagree with persisted-data validation.

**Recommendation:** Decide that the future-date rule applies both to new input
and loaded records, then pass `today` through `session_from_dict` and
`load_sessions`, or inject a small `today_fn`. Prefer the explicit `today`
parameter to avoid an abstraction used only once.

### Finding 4 — `delete_numbered_session` accepts mismatched snapshots

**Label:** 🔴 Real problem  
**Severity:** Major  
**Area:** Service interface

**Problem:** The proposed delete function accepts both `sessions` and a separate
`numbered` collection. Nothing in its type contract guarantees that the numbered
rows were created from that exact sessions snapshot.

**Impact:** A caller can pass stale or unrelated numbering and delete the wrong
record—the exact failure this design is meant to prevent.

**Recommendation:** Use one of these contracts:

```python
delete_session_by_number(sessions, number) -> list[StudySession]
```

and compute numbering internally, or accept one selected `NumberedSession` and
verify its original index and session still match before deletion. The first is
simpler for this CLI.

### Finding 5 — Export path behavior expands the written specification

**Label:** 🔴 Real problem  
**Severity:** Major  
**Area:** Scope/API contract

**Problem:** `SPEC.md` names the argument `FILENAME`. The plan expands that into
relative and absolute paths without recording directory-creation, missing-parent,
or out-of-project behavior.

**Impact:** Implementers and tests must invent path semantics, and a user can
write outside the project even though the spec only promises a filename.

**Recommendation:** Keep the first version narrow: accept a filename only,
reject directory components, and save beside `main.py`. If arbitrary paths are
desired, amend `SPEC.md` with the exact resolution and failure behavior.

### Finding 6 — The `log` flow validates input before discovering corrupt data

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor  
**Area:** CLI data flow

**Problem:** The planned log flow prompts for and validates a complete session
before loading `sessions.json`.

**Impact:** If the JSON file is corrupt or unreadable, the user completes every
prompt only to learn that nothing can be saved.

**Recommendation:** Load and validate existing sessions immediately after the
`log` command and before prompting. On load failure, return to the command prompt
without collecting input.

### Finding 7 — Exact output contracts remain underspecified

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor  
**Area:** CLI tests

**Problem:** The spec gives exact text for only some errors. The plan promises
"exact messages" and detailed CLI assertions without providing a message table
for corrupt files, invalid command arguments, confirmation, export success, and
interrupt exits.

**Impact:** CLI tests may lock in whichever wording the first implementation
chooses, making later review appear to detect behavior changes that were never
specified.

**Recommendation:** Add a compact command/error message table to `PLAN_v2.md`.
Test exact wording only where `SPEC.md` requires it; elsewhere test essential
content such as command, filename, valid range, and absence of a traceback.

### Finding 8 — Four production modules may be excessive for this course CLI

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor / design judgment  
**Area:** Complexity

**Problem:** The plan replaces one small script with models, storage, services,
and CLI modules plus multiple result dataclasses. This is defensible for
testability, but `ClassTotal` and `NumberedSession` may be abstractions for one
call site.

**Impact:** More files and types increase the amount a beginner must understand
and can obscure the core SOLO lesson.

**Recommendation:** Keep model, storage, and CLI boundaries, but consider putting
the two short pure transformations in `models.py` or `cli.py` unless
`services.py` remains independently useful after implementation. Do not merge
storage into the CLI; path injection is necessary for safe tests.

### Finding 9 — CSV formula hardening would be gold-plating here

**Label:** ⚪ Noise  
**Severity:** Noise check  
**Area:** Security scope

**Problem:** `ARCHITECTURE.md` mentioned modifying values that start with
spreadsheet formula characters, while `PLAN_v1.md` correctly omitted it.
Reintroducing that behavior would mutate user-authored notes and is not required
by `SPEC.md`.

**Impact:** A well-intended security feature could make exported data differ
from stored data and expand test scope.

**Recommendation:** Keep it out of this version. `csv.DictWriter` quoting is
required for valid CSV; spreadsheet-specific formula neutralization is not.

### Finding 10 — Performance and concurrency statements add little value

**Label:** ⚪ Noise  
**Severity:** Noise check  
**Area:** Non-functional scope

**Problem:** The surrounding architecture introduces a 10,000-session performance
target and explicitly documents unsupported simultaneous instances. Neither is
central to the course specification.

**Impact:** These statements invite additional benchmarking and concurrency
design that does not improve the required program.

**Recommendation:** Do not add performance benchmarks, file locking, or
concurrency machinery. A short README note about single-process use is harmless
but not an implementation milestone.

## Missing Test Cases

1. Two sessions on the same date with different storage positions, followed by
   deletion of the second displayed row.
2. Multiple differently cased versions of a class name with a defined display
   spelling.
3. Decimal JSON round trips for values that commonly expose binary-float
   representation issues.
4. Corrupt `sessions.json` followed by `log`, verifying no prompts occur and the
   file remains byte-for-byte unchanged.
5. Export filenames containing directory separators, once the filename/path
   contract is resolved.
6. Persisted future dates with an injected clock.
7. A replacement failure after a temporary file is fully written, verifying the
   original content and temporary-file cleanup.

## Recommended Revision Priorities

1. Resolve Findings 1 and 2 before any implementation.
2. Resolve Findings 3–5 in the spec and typed interfaces.
3. Incorporate Findings 6 and 7 into CLI flow and tests.
4. Make an explicit simplicity decision on Finding 8.
5. Ignore Findings 9 and 10 unless project scope changes.

## Verdict

**Revise before implementation.** The plan has a sound overall direction, but
the `Decimal` serialization contract and field-specific validation interface
would otherwise cause immediate implementation failures. The remaining major
findings are contained and should require a focused `PLAN_v2.md`, not a redesign.
