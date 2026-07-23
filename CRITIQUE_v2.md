# Critique of Study Tracker Technical Plan v2

## Pre-Flight Verification

- Re-read `workflows/critique.md`, `PLAN_v2.md`, `SPEC.md`, `main.py`,
  `sessions.json`, and the current import call sites.
- Confirmed current data still contains one Biology record without `notes`.
- Traced each planned boundary:
  CLI input -> domain validators -> `StudySession` -> storage conversion -> JSON,
  and JSON -> storage -> domain validation -> list/summary/delete/export.
- Confirmed no `.lockedfiles` file exists.
- Proposed package imports cannot yet be verified because the package does not
  exist; `PLAN_v2.md` correctly requires an on-environment import check before
  replacing `main.py`.
- Confirmed every red and yellow v1 finding has a corresponding v2 change.
- Confirmed the two white/noise findings did not expand v2 scope.

## Executive Assessment

Version 2 resolves all immediate failures identified in version 1. In
particular, its JSON/`Decimal` boundary, field-oriented validation, deterministic
clock, deletion mapping, export boundary, CLI load order, test messages, and
simplified module layout are coherent.

One domain invariant remains internally inconsistent and should be fixed before
implementation. Three smaller behavior/test clarifications would improve the
plan but do not require architectural changes.

## Findings

### Finding 1 — Public construction bypasses all validation

**Label:** 🔴 Real problem  
**Severity:** Must fix  
**Area:** Domain invariant

**Problem:** The plan states, “Every constructed `StudySession` contains
validated, trimmed values,” but exposes the normal dataclass constructor:

```python
StudySession(class_name, date, hours, notes)
```

Nothing in the stated contract prevents callers from constructing an empty
class name, future date, negative hours, more than two decimal places, or
oversized notes. The field validators are separate and therefore optional.

**Impact:** `session_to_dict`, numbering, summary, and export all assume valid
instances. One direct construction in production or a future test can bypass
the rules and persist invalid data.

**Recommendation:** Choose one enforceable invariant:

1. Add `StudySession.__post_init__` validation for already typed values and use
   field validators for parsing/normalization, or
2. Make the dataclass private (`_StudySession`) and expose only validated factory
   functions.

For this beginner project, option 1 is clearer. Specify that `__post_init__`
rejects invalid typed values while CLI validators remain responsible for
field-specific parsing and retry messages.

### Finding 2 — The new decimal-place error has no message contract

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor  
**Area:** CLI behavior

**Problem:** Plan v2 introduces a new rule—at most two decimal places—but its
stable message table covers only non-numeric and out-of-range hours.

**Impact:** The implementation and tests must invent whether excessive decimal
places use the range message or a new message.

**Recommendation:** Add required content such as `Hours may have at most two
decimal places.` and test that the hours prompt retries.

### Finding 3 — Empty-data export behavior is unstated

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor  
**Area:** Export contract

**Problem:** `SPEC.md` defines empty behavior only for `list` and `summary`.
Plan v2 does not say whether exporting zero sessions creates a header-only CSV
or refuses.

**Impact:** Both choices are reasonable, so separate implementers could produce
different behavior and tests.

**Recommendation:** Create a header-only CSV and report `0` exported rows. This
keeps export deterministic and satisfies “one row per session.”

### Finding 4 — Startup acceptance lacks a concrete automated test step

**Label:** 🟡 Good idea, not critical  
**Severity:** Minor  
**Area:** Acceptance verification

**Problem:** The acceptance table names an import/startup smoke test, but the
test phases do not explicitly create one. The manual package import check only
proves package resolution, not that `py main.py` starts successfully.

**Impact:** A broken entry-point import or exit-code handoff could escape the
unit suite.

**Recommendation:** Add a subprocess smoke test or an explicit final manual
check that starts `py main.py`, sends `quit`, expects exit code 0, and confirms
no traceback. For this small Windows course project, the explicit manual check
is sufficient and less brittle than a subprocess unit test.

## Verified Improvements from v1

1. `Decimal` is converted before JSON serialization and reconstructed
   deterministically.
2. Individual validators support field-specific retries.
3. Date validation accepts an injected clock at both input and load boundaries.
4. Deletion numbering is recomputed from the exact supplied session collection.
5. Export is restricted to the project directory.
6. `log` checks storage health before collecting user input.
7. Message assertions are exact only where the spec requires them.
8. The package was simplified without coupling tests to real storage.

## Verdict

**One more focused revision is required.** Fix the `StudySession` construction
invariant and incorporate the three small clarifications. No architectural
redesign or new module is needed.
