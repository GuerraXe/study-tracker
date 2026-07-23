# Forensic Case Report

## 1. Incident Overview

**Anomaly description:** The planted commit changes serialized `hours` from a
JSON number to a JSON string. The course predicts a summary such as `2.03.0`;
in this implementation, the summary remains numerically correct because the
loader normalizes persisted input back to `Decimal`. The interface and
persistence tests correctly fail.

**Blast radius:**

- JSON written by `save_sessions` violates `SessionRecord.hours: float`.
- CSV receives the same serializer output.
- Four tests fail because they verify numeric persistence.
- Loaded `StudySession` objects and summary arithmetic remain protected.

## 2. Exhibit Gallery (Evidence)

### Commit evidence

Commit `d091729` contains one functional change:

```diff
- "hours": float(session.hours),
+ "hours": str(session.hours),
```

File: `study_tracker/domain.py`, `session_to_dict`.

### Test evidence

The suite reports four failures and 39 passes. The repeated mismatch is:

```text
{"hours": "1.5"} != {"hours": 1.5}
```

Failing coverage includes:

- Exact serialized record shape
- Valid log persistence
- Persistence after negative-hours retry
- Persistence after nonnumeric-hours retry

### End-to-end trace

```text
CLI validates hours
  -> StudySession.hours: Decimal
  -> save_sessions
  -> session_to_dict
  -> str(session.hours)                 ROOT TYPE CHANGE
  -> JSON string
  -> load_sessions
  -> session_from_dict
  -> validate_hours(JSON string)
  -> StudySession.hours: Decimal         CONTAINMENT LAYER
  -> summarize_sessions
  -> Decimal addition
```

### Reproduction proof

The persisted-type failure is reproducible on every log command and directly in
`session_to_dict`. The claimed concatenated-summary symptom is not reproducible
in this codebase because the load boundary validates and normalizes the string
before summary calculation.

## 3. The Chain of Logic (Deduction)

### Hypothesis 1: Summary concatenates unvalidated raw JSON values

**Eliminated.** `summarize_sessions` accepts `StudySession` objects, whose
`hours` field is a validated `Decimal`. It never reads decoded JSON dictionaries.
Summary tests continue to pass.

### Hypothesis 2: The loader preserves JSON strings as strings

**Eliminated.** `load_sessions` calls `session_from_dict`, which calls
`validate_hours`. That validator converts numeric text through `Decimal`.

### Hypothesis 3: The save boundary emits the wrong type

**Confirmed.** The planted commit changes the only session serializer from
`float(session.hours)` to `str(session.hours)`. Both the commit diff and four
independent failing assertions identify this exact boundary.

### The “Ah-ha!” moment

The first corrupted representation exists before disk I/O, in
`session_to_dict`. Storage writes exactly what that function returns. Therefore,
the root cause is serializer type conversion—not summary arithmetic, display
formatting, JSON decoding, or addition.

### Watson self-critique

- Searched every `session_to_dict` call site: JSON save and CSV export.
- Searched every summary input path: all pass through `session_from_dict`.
- Verified the symptom discrepancy rather than forcing the course's assumed
  architecture onto the actual code.
- Confirmed no alternate serializer or raw-dictionary summary path exists.
- The deduction is supported by commit diff, call sites, and failing tests.

## 4. The Solution

### Actionable fix

Restore the serializer contract at the source:

```python
"hours": float(session.hours)
```

Do not add conversions to `summarize_sessions`; that would patch a symptom and
duplicate validation already enforced by `StudySession`.

### Prevention plan

1. Keep `SessionRecord.hours` typed as `float`.
2. Keep the exact serializer-shape test.
3. Keep end-to-end log persistence tests asserting JSON numbers.
4. Run the full pytest suite after serializer changes.
5. Preserve loader validation as defense in depth, even though writers should
   already honor the schema.

No implementation was changed during this Sherlock investigation.
