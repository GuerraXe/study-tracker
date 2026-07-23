# Study Tracker Input Validation Catalog

## Command prompt

| Valid | Invalid or unusual | Expected behavior |
|-------|--------------------|-------------------|
| `log`, `list`, `summary`, `delete NUMBER`, `export [FILENAME]`, `help`, `quit` | Empty input | Ignore it and show the prompt again |
| Commands in any letter case | Unknown command | Explain that it is unknown and point to `help` |
| Only the documented arguments | Missing or extra arguments | Show command usage without crashing |
| Normal terminal input | End-of-input or `Ctrl+C` at any prompt | Exit cleanly without saving partial work |

## Class name

| Valid | Invalid or unusual | Expected behavior |
|-------|--------------------|-------------------|
| Trimmed text containing 1–100 characters | Empty or whitespace-only | Explain the 1–100 character requirement and retry |
| Letters, numbers, punctuation, and Unicode | More than 100 characters | Explain the limit and retry |
| Special text such as `"; DROP TABLE sessions; --` | Non-string persisted value | Treat it as plain text; never execute it |

## Hours

| Valid | Invalid | Expected behavior |
|-------|---------|-------------------|
| Numeric value greater than 0 and no greater than 24 | Letters or symbols | Print `Please enter hours as a number.` and retry |
| Up to two decimal places | Zero, negative, or over 24 | Print the range error and retry |
| Finite number | More than two decimal places | Explain the precision limit and retry |
| | Boolean, NaN, or infinity in persisted data | Reject the record without crashing or overwriting it |

## Date

| Valid | Invalid | Expected behavior |
|-------|---------|-------------------|
| Real date in `YYYY-MM-DD` format, today or earlier | Empty or wrong format | Show the required format and retry |
| | Impossible date such as `2026-02-30` | Show the required format and retry |
| | Future date | Explain that future dates are not allowed and retry |

## Notes

| Valid | Invalid | Expected behavior |
|-------|---------|-------------------|
| Empty text or trimmed text up to 500 characters | More than 500 characters | Explain the limit and retry |
| Punctuation, commas, quotes, and newlines | Non-string persisted value | Reject malformed persisted data |

## Session number

| Valid | Invalid | Expected behavior |
|-------|---------|-------------------|
| Existing positive displayed number | Missing, letters, zero, or negative | Show usage or valid range |
| | Number larger than the session list | Show valid range and do not modify data |

## Export filename

| Valid | Invalid | Expected behavior |
|-------|---------|-------------------|
| Plain filename beside the project | Absolute path or directory separators | Reject it without writing |
| Filename that does not exist | Existing destination | Explain that it exists and never overwrite |

## Storage failures

| Condition | Expected behavior |
|-----------|-------------------|
| `sessions.json` is missing | Treat it as an empty session list |
| File disappears between commands | Reload and show an empty result |
| Invalid JSON, invalid UTF-8, wrong root type, or malformed record | Name the file, show a plain-language error, preserve its bytes, and return to the prompt |
| JSON save fails | Preserve the last valid file and clean the temporary file when possible |
