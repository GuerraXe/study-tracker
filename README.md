# Study Tracker

A command-line Python application for logging study sessions and reviewing
study activity.

## Commands

- `log` — record a study session.
- `list` — view sessions newest-first.
- `summary` — show total hours by class.
- `delete NUMBER` — remove a numbered session after confirmation.
- `export [FILENAME]` — create a CSV without overwriting existing files.
- `help` — show command help.
- `quit` — exit.

Sessions are stored locally in `sessions.json`.

## Run

```powershell
py main.py
```

Run tests with:

```powershell
py -m pytest -v
```

The earlier `study_tracker.py` file is the vibe-coded version retained for
comparison during the SOLO Protocol course.
