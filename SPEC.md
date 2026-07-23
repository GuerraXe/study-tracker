# Study Tracker Specification

## What does this program do?

Study Tracker is a local command-line Python program for recording time spent
studying. A user can log a session, list saved sessions, see total study hours
grouped by class, delete an incorrect session, and export the data to CSV. The
program is designed for one person using one computer and must remain simple
enough to run with Python's standard library.

## Commands the user can run

- `log` — prompt for a class name, date, hours studied, and optional notes,
  validate the answers, and save one session.
- `list` — show all sessions in date order with a numbered row for each session.
- `summary` — show total hours per class and the total across all classes.
- `delete NUMBER` — delete the session with the number currently shown by
  `list`, but ask for confirmation before saving the deletion.
- `export [FILENAME]` — write all sessions to a CSV file. If no filename is
  supplied, use `study_sessions.csv`. Refuse to overwrite an existing file.
- `help` — show the available commands and examples.
- `quit` — exit the program.

Commands are entered through an interactive prompt after running `py main.py`.
Command names are case-insensitive. Extra arguments are rejected with a usage
message.

## What information does a study session contain?

- Class name — required, trimmed text from 1 to 100 characters.
- Date — required calendar date in `YYYY-MM-DD` format.
- Hours studied — required number greater than 0 and no greater than 24,
  stored as a number and displayed with two decimal places.
- Notes — optional trimmed text, up to 500 characters.

## How is data stored?

Sessions are stored as a JSON array in `sessions.json` beside `main.py`. Each
array item is an object with exactly `class_name`, `date`, `hours`, and `notes`.
The file uses UTF-8 and two-space indentation. The program creates the file
automatically on the first successful `log`. Each save writes a temporary file
first and then replaces `sessions.json` so an interrupted write is less likely
to corrupt existing data.

The `list` command sorts a copy of the sessions by date, newest first. The
display number refers to that sorted view; deleting a number removes the
corresponding stored record.

## What happens when things go wrong?

1. If hours contain letters or are otherwise not numeric, print
   `Please enter hours as a number.` and ask again.
2. If hours are 0, negative, or greater than 24, print
   `Hours must be greater than 0 and no more than 24.` and ask again.
3. If a date is not a real date in `YYYY-MM-DD` format, show the expected
   format and ask again.
4. If the class name is empty or longer than 100 characters, explain the limit
   and ask again.
5. If notes are longer than 500 characters, explain the limit and ask again.
6. If `sessions.json` does not exist, treat it as an empty list and create it
   after the first successful log.
7. If `sessions.json` is unreadable, invalid JSON, not a JSON array, or contains
   a malformed session, print an error naming the file, do not overwrite it,
   and return to the command prompt.
8. If `delete NUMBER` is missing a number, uses a non-integer, or refers to a
   session that does not exist, show the correct usage or valid range and do
   not change the file.
9. If deletion confirmation is anything other than `y` or `yes`
   (case-insensitive), cancel the deletion.
10. If there are no sessions, `list` and `summary` print
    `No study sessions found.` without crashing.
11. If the CSV export destination already exists or cannot be written, explain
    the problem and preserve both the JSON data and existing destination file.
12. If a command is unknown or has unexpected arguments, print a short error
    followed by the `help` guidance.

## What this program does NOT do

- No web or graphical interface.
- No accounts, login, or support for multiple users.
- No database, network requests, cloud storage, or synchronization.
- No grades, assignments, reminders, schedules, or calendar integration.
- No editing of existing sessions; users delete an incorrect entry and log a
  replacement.
- No importing CSV or JSON files.
- No reporting by week or date range in this version.
- No external Python packages.

## Acceptance criteria

1. The program runs on Python 3.10 or newer using `py main.py`.
2. A valid `log` command persists one session that remains available after the
   program restarts.
3. Invalid input follows the specific behavior above and does not terminate the
   program.
4. `list` displays every valid stored session newest-first with stable numbering
   for the duration of that command.
5. `summary` reports correct per-class and overall totals to two decimal places.
6. A confirmed valid `delete NUMBER` removes exactly the displayed session; a
   canceled or invalid deletion changes nothing.
7. `export` produces a UTF-8 CSV with headers `class_name,date,hours,notes` and
   one row per session without overwriting an existing file.
8. Automated tests cover storage, validation, each command, empty data, corrupt
   data, and failed writes without modifying the user's real `sessions.json`.
