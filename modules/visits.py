"""
Visit Records Module

Handles saving patient doctor visits, viewing visit history,
and checking clinical notes.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List

from utils.display import (
    print_subheader,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_table,
    confirm_action,
    pause
)
from utils.validators import (
    validate_non_empty,
    validate_date,
    validate_menu_choice
)
from config import DEPARTMENTS, DATETIME_FORMAT


# ==========================================
# Database Operations
# ==========================================

def generate_visit_id(conn: sqlite3.Connection) -> str:
    """Generate the next visit ID like VST-1001, VST-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT visit_id FROM visits WHERE visit_id LIKE 'VST-%' ORDER BY visit_id DESC")
    rows = cursor.fetchall()

    # Find the highest existing visit number and add 1
    max_id_num = 1000
    for row in rows:
        vid = row["visit_id"]
        parts = vid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"VST-{next_id_num}"


def record_visit(
    conn: sqlite3.Connection,
    patient_id: str,
    visit_date: str,
    department: str,
    attending_provider: str,
    notes: str
) -> str:
    """Save a new visit record into the database."""
    visit_id = generate_visit_id(conn)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO visits (
            visit_id, patient_id, visit_date, department,
            attending_provider, notes
        ) VALUES (?, ?, ?, ?, ?, ?);
    """, (visit_id, patient_id, visit_date, department, attending_provider, notes))
    conn.commit()
    return visit_id


def get_visit_by_id(conn: sqlite3.Connection, visit_id: str) -> Optional[sqlite3.Row]:
    """Get full visit details joined with the patient's basic info."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name, p.dob, p.contact_number
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE UPPER(v.visit_id) = UPPER(?)
    """, (visit_id.strip(),))
    return cursor.fetchone()


def get_visits_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get all past visits for one patient, sorted by newest first."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE UPPER(v.patient_id) = UPPER(?)
        ORDER BY v.visit_date DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def get_all_visits(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all recorded visits across the hospital."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, p.full_name as patient_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_date DESC
    """)
    return cursor.fetchall()


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_record_visit(conn: sqlite3.Connection) -> None:
    """Ask for visit details from the user and save them."""
    from modules.patients import get_patient_by_id

    print_subheader("Record Patient Visit")
    try:
        pid_input = input("Enter Patient ID: ").strip()
        if not pid_input:
            print_warning("Operation cancelled.")
            pause()
            return

        patient = get_patient_by_id(conn, pid_input)
        if not patient:
            print_error(f"Patient with ID '{pid_input}' not found.")
            pause()
            return

        # Warn if the patient is archived before continuing
        if patient["status"] == "Archived":
            print_warning("This patient record is currently ARCHIVED.")
            if not confirm_action("Do you still want to record a visit for this archived patient?", default_no=True):
                print_info("Visit entry cancelled.")
                pause()
                return

        print_info(f"Recording visit for: {patient['full_name']} ({patient['patient_id']})")

        # Use current date and time as default if user just hits enter
        default_now = datetime.now().strftime(DATETIME_FORMAT)
        date_prompt = input(f"Enter Visit Date & Time (YYYY-MM-DD HH:MM) [{default_now}]: ").strip()
        if not date_prompt:
            visit_date = default_now
        else:
            try:
                parsed = datetime.strptime(date_prompt, DATETIME_FORMAT)
                visit_date = parsed.strftime(DATETIME_FORMAT)
            except ValueError:
                print_error("Invalid format. Expected YYYY-MM-DD HH:MM (e.g., 2024-05-18 14:30).")
                pause()
                return

        # Select department from the list
        print("\nSelect Department:")
        for idx, dept in enumerate(DEPARTMENTS, 1):
            print(f"  {idx}. {dept}")

        dept_choice = input(f"Enter choice (1-{len(DEPARTMENTS)}): ").strip()
        valid, idx_num, _ = validate_menu_choice(dept_choice, 1, len(DEPARTMENTS))
        if not valid or idx_num is None:
            print_error("Invalid department selection.")
            pause()
            return
        department = DEPARTMENTS[idx_num - 1]

        # Enter attending doctor or nurse
        while True:
            provider_input = input("Enter Attending Provider (e.g. Dr. Jane Smith): ").strip()
            if not provider_input:
                print_warning("Operation cancelled.")
                pause()
                return
            valid, res = validate_non_empty(provider_input, "Attending Provider", min_length=2)
            if valid:
                attending_provider = res
                break
            print_error(res)

        # Enter clinical notes or findings
        while True:
            notes_input = input("Enter Clinical Notes / Diagnosis / Observations: ").strip()
            if not notes_input:
                print_warning("Operation cancelled.")
                pause()
                return
            valid, res = validate_non_empty(notes_input, "Visit Notes", min_length=3)
            if valid:
                notes = res
                break
            print_error(res)

        # Show summary before saving
        print("\nVisit Record Summary:")
        print(f"  Patient:    {patient['full_name']} ({patient['patient_id']})")
        print(f"  Timestamp:  {visit_date}")
        print(f"  Department: {department}")
        print(f"  Provider:   {attending_provider}")
        print(f"  Notes:      {notes}")

        if confirm_action("\nSave this visit record?", default_no=False):
            vid = record_visit(conn, patient["patient_id"], visit_date, department, attending_provider, notes)
            print_success(f"Visit record logged successfully! Visit ID: {vid}")
        else:
            print_info("Visit entry cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled by user.")
    pause()


def handle_view_patient_visits(conn: sqlite3.Connection) -> None:
    """View all visits made by one patient."""
    from modules.patients import get_patient_by_id

    print_subheader("View Patient Visit History")
    pid_input = input("Enter Patient ID: ").strip()
    if not pid_input:
        print_error("Patient ID is required.")
        pause()
        return

    patient = get_patient_by_id(conn, pid_input)
    if not patient:
        print_error(f"Patient with ID '{pid_input}' not found.")
        pause()
        return

    visits = get_visits_by_patient(conn, patient["patient_id"])
    print_info(f"Visit history for {patient['full_name']} ({patient['patient_id']}):")

    # Shorten long notes so the table stays neat on screen
    headers = ["Visit ID", "Date & Time", "Department", "Provider", "Notes"]
    rows = [
        [
            v["visit_id"],
            v["visit_date"],
            v["department"],
            v["attending_provider"],
            (v["notes"][:35] + "...") if len(v["notes"]) > 35 else v["notes"]
        ]
        for v in visits
    ]
    print_table(headers, rows, empty_message=f"No visit records found for patient {patient['patient_id']}.")
    pause()


def handle_view_all_visits(conn: sqlite3.Connection) -> None:
    """Show every visit recorded in the hospital."""
    print_subheader("All Hospital Visit Records")
    visits = get_all_visits(conn)

    headers = ["Visit ID", "Patient ID", "Patient Name", "Date & Time", "Department", "Provider"]
    rows = [
        [
            v["visit_id"],
            v["patient_id"],
            v["patient_name"],
            v["visit_date"],
            v["department"],
            v["attending_provider"]
        ]
        for v in visits
    ]
    print_table(headers, rows, empty_message="No hospital visits recorded yet.")
    pause()


def handle_view_visit_details(conn: sqlite3.Connection) -> None:
    """Show the complete details and full notes of a single visit."""
    print_subheader("Visit Record Details")
    vid_input = input("Enter Visit ID: ").strip()
    if not vid_input:
        print_error("Visit ID is required.")
        pause()
        return

    visit = get_visit_by_id(conn, vid_input)
    if not visit:
        print_error(f"Visit with ID '{vid_input}' not found.")
        pause()
        return

    print()
    print("=" * 65)
    print(f"  CLINICAL VISIT RECORD: {visit['visit_id']}")
    print("=" * 65)
    print(f"  Patient:            {visit['patient_name']} ({visit['patient_id']})")
    print(f"  Date of Birth:      {visit['dob']}")
    print(f"  Contact:            {visit['contact_number']}")
    print(f"  Visit Date & Time:  {visit['visit_date']}")
    print(f"  Department:         {visit['department']}")
    print(f"  Attending Provider: {visit['attending_provider']}")
    print(f"  Clinical Notes:     {visit['notes']}")
    print("=" * 65)
    pause()


def visit_menu(conn: sqlite3.Connection) -> None:
    """Submenu for handling patient visits."""
    while True:
        print_subheader("Visit Records Menu")
        print("  1. Record New Patient Visit")
        print("  2. View Patient Visit History")
        print("  3. View All Hospital Visits")
        print("  4. View Specific Visit Details")
        print("  5. Return to Main Menu")
        print("-" * 75)

        try:
            choice = input("Enter your choice (1-5): ")
        except (KeyboardInterrupt, EOFError):
            print()
            break

        valid, choice_num, err_msg = validate_menu_choice(choice, 1, 5)
        if not valid:
            print_error(err_msg)
            pause()
            continue

        if choice_num == 1:
            handle_record_visit(conn)
        elif choice_num == 2:
            handle_view_patient_visits(conn)
        elif choice_num == 3:
            handle_view_all_visits(conn)
        elif choice_num == 4:
            handle_view_visit_details(conn)
        elif choice_num == 5:
            break
