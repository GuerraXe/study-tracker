import json
from datetime import datetime
from pathlib import Path


SESSIONS_FILE = Path(__file__).with_name("sessions.json")


def load_sessions() -> list[dict]:
    if not SESSIONS_FILE.exists():
        return []

    with SESSIONS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_sessions(sessions: list[dict]) -> None:
    with SESSIONS_FILE.open("w", encoding="utf-8") as file:
        json.dump(sessions, file, indent=2)


def prompt_for_date() -> str:
    while True:
        value = input("Date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            print("Enter the date in YYYY-MM-DD format.")


def prompt_for_hours() -> float:
    while True:
        try:
            hours = float(input("Hours studied: "))
            if hours <= 0:
                raise ValueError
            return hours
        except ValueError:
            print("Enter a number greater than zero.")


def log_study_session() -> None:
    class_name = input("Class name: ").strip()
    while not class_name:
        print("Class name cannot be empty.")
        class_name = input("Class name: ").strip()

    session = {
        "class_name": class_name,
        "date": prompt_for_date(),
        "hours": prompt_for_hours(),
    }

    sessions = load_sessions()
    sessions.append(session)
    save_sessions(sessions)
    print("Study session saved.")


def view_study_sessions() -> None:
    sessions = load_sessions()
    if not sessions:
        print("No study sessions have been logged yet.")
        return

    print("\nSaved Study Sessions")
    for number, session in enumerate(sessions, start=1):
        print(
            f"{number}. {session['date']} | "
            f"{session['class_name']} | {session['hours']:.2f} hours"
        )


def main() -> None:
    while True:
        print("\nStudy Tracker")
        print("1. Log a study session")
        print("2. View study sessions")
        print("3. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            log_study_session()
        elif choice == "2":
            view_study_sessions()
        elif choice == "3":
            print("Goodbye!")
            return
        else:
            print("Choose 1, 2, or 3.")


if __name__ == "__main__":
    main()
