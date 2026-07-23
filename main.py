from pathlib import Path

from study_tracker.cli import run


def main() -> int:
    sessions_path = Path(__file__).with_name("sessions.json")
    return run(sessions_path)


if __name__ == "__main__":
    raise SystemExit(main())
