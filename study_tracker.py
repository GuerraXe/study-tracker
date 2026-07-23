import json
from datetime import date, datetime, timedelta
from pathlib import Path


DATA_FILE = Path("study_sessions.json")


def load_sessions():
    if DATA_FILE.exists():
        with DATA_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    return []


def save_sessions(sessions):
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(sessions, file, indent=2)


def log_session(sessions):
    subject = input("What did you study? ")
    class_name = input("Which class was this for? ")
    hours = float(input("How many hours did you study? "))
    sessions.append(
        {
            "subject": subject,
            "class": class_name,
            "hours": hours,
            "date": date.today().isoformat(),
        }
    )
    save_sessions(sessions)
    print("Study session saved!")


def show_total(sessions):
    total = sum(session["hours"] for session in sessions)
    print(f"You have studied for {total:.2f} total hours.")


def show_weekly_summary(sessions):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    totals = {}

    for session in sessions:
        session_date = datetime.fromisoformat(
            session.get("date", today.isoformat())
        ).date()
        if start_of_week <= session_date <= today:
            class_name = session.get("class", "Uncategorized")
            totals[class_name] = totals.get(class_name, 0) + session["hours"]

    print("\nWeekly Summary")
    if not totals:
        print("No study sessions this week.")
    for class_name, hours in totals.items():
        print(f"{class_name}: {hours:.2f} hours")


def delete_session(sessions):
    if not sessions:
        print("There are no sessions to delete.")
        return

    for index, session in enumerate(sessions, start=1):
        print(
            f"{index}. {session.get('class', 'Uncategorized')} - "
            f"{session['subject']} ({session['hours']:.2f} hours)"
        )

    session_number = int(input("Enter the number of the session to delete: "))
    if 1 <= session_number <= len(sessions):
        deleted = sessions.pop(session_number - 1)
        save_sessions(sessions)
        print(f"Deleted the {deleted['subject']} session.")
    else:
        print("That session number does not exist.")


def main():
    sessions = load_sessions()

    while True:
        print("\nStudy Tracker")
        print("1. Log a study session")
        print("2. See total study hours")
        print("3. See weekly summary by class")
        print("4. Delete a study session")
        print("5. Exit")
        choice = input("Choose an option: ")

        if choice == "1":
            log_session(sessions)
        elif choice == "2":
            show_total(sessions)
        elif choice == "3":
            show_weekly_summary(sessions)
        elif choice == "4":
            delete_session(sessions)
        elif choice == "5":
            print("Goodbye!")
            break
        else:
            print("Please choose 1, 2, 3, 4, or 5.")


if __name__ == "__main__":
    main()
