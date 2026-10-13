"""
Appointment Management module.
Handles booking, double-booking prevention, rescheduling, and cancelling appointments.
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Tuple

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
    validate_time,
    validate_menu_choice
)
from config import DEPARTMENTS, DATE_FORMAT, TIME_FORMAT


# ==========================================
# Database Operations
# ==========================================

def generate_appointment_id(conn: sqlite3.Connection) -> str:
    """Generate the next appointment ID like APT-1001, APT-1002, etc."""
    cursor = conn.cursor()
    cursor.execute("SELECT appointment_id FROM appointments WHERE appointment_id LIKE 'APT-%' ORDER BY appointment_id DESC")
    rows = cursor.fetchall()

    max_id_num = 1000
    for row in rows:
        aid = row["appointment_id"]
        parts = aid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"APT-{next_id_num}"


def check_appointment_conflict(
    conn: sqlite3.Connection,
    appointment_date: str,
    appointment_time: str,
    department: str,
    patient_id: str,
    exclude_appointment_id: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Make sure neither the patient nor the department is double-booked at the same time.
    Returns (True, error_message) if there is a conflict.
    """
    cursor = conn.cursor()

    # Check 1: Make sure this patient doesn't already have an appointment at this exact time
    query_patient = """
        SELECT appointment_id FROM appointments
        WHERE patient_id = ? 
          AND appointment_date = ? 
          AND appointment_time = ?
          AND status IN ('Scheduled', 'Rescheduled')
    """
    params_patient = [patient_id, appointment_date, appointment_time]
    # If we are rescheduling, don't count the appointment itself as a conflict
    if exclude_appointment_id:
        query_patient += " AND appointment_id != ?"
        params_patient.append(exclude_appointment_id)

    cursor.execute(query_patient, tuple(params_patient))
    patient_conflict = cursor.fetchone()
    if patient_conflict:
        return True, f"Patient already has an active appointment ({patient_conflict['appointment_id']}) at {appointment_date} {appointment_time}."

    # Check 2: Make sure the department slot isn't already taken by someone else
    query_dept = """
        SELECT appointment_id FROM appointments
        WHERE department = ? 
          AND appointment_date = ? 
          AND appointment_time = ?
          AND status IN ('Scheduled', 'Rescheduled')
    """
    params_dept = [department, appointment_date, appointment_time]
    if exclude_appointment_id:
        query_dept += " AND appointment_id != ?"
        params_dept.append(exclude_appointment_id)

    cursor.execute(query_dept, tuple(params_dept))
    dept_conflict = cursor.fetchone()
    if dept_conflict:
        return True, f"The {department} department already has an appointment booked at {appointment_date} {appointment_time}."

    return False, ""


def schedule_appointment(
    conn: sqlite3.Connection,
    patient_id: str,
    appointment_date: str,
    appointment_time: str,
    department: str,
    reason: str
) -> str:
    """Book an appointment in the database and return its new ID."""
    appointment_id = generate_appointment_id(conn)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (
            appointment_id, patient_id, appointment_date,
            appointment_time, department, reason, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled');
    """, (appointment_id, patient_id, appointment_date, appointment_time, department, reason))
    conn.commit()
    return appointment_id


def get_appointment_by_id(conn: sqlite3.Connection, appointment_id: str) -> Optional[sqlite3.Row]:
    """Find an appointment by ID and join with patient name."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name, p.status as patient_status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE UPPER(a.appointment_id) = UPPER(?)
    """, (appointment_id.strip(),))
    return cursor.fetchone()


def get_upcoming_appointments(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all future appointments that are scheduled or rescheduled."""
    today_str = date.today().strftime(DATE_FORMAT)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.appointment_date >= ?
          AND a.status IN ('Scheduled', 'Rescheduled')
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    """, (today_str,))
    return cursor.fetchall()


def get_appointments_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get the appointment history of a specific patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE UPPER(a.patient_id) = UPPER(?)
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def search_appointments(conn: sqlite3.Connection, query: str) -> List[sqlite3.Row]:
    """Find appointments by searching patient ID, appointment ID, or patient name."""
    search_term = f"%{query.strip()}%"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, p.full_name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.appointment_id LIKE ? 
           OR a.patient_id LIKE ? 
           OR p.full_name LIKE ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (search_term, search_term, search_term))
    return cursor.fetchall()


def reschedule_appointment(
    conn: sqlite3.Connection,
    appointment_id: str,
    new_date: str,
    new_time: str
) -> Tuple[bool, str]:
    """Move an appointment to a new date and time after checking for conflicts."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found."

    # Cannot reschedule appointments that are already cancelled or completed
    if apt["status"] == "Cancelled":
        return False, "Cannot reschedule a cancelled appointment."
    if apt["status"] == "Completed":
        return False, "Cannot reschedule an already completed appointment."

    # Make sure the new slot is free
    conflict, msg = check_appointment_conflict(
        conn, new_date, new_time, apt["department"], apt["patient_id"], exclude_appointment_id=appointment_id
    )
    if conflict:
        return False, msg

    cursor.execute("""
        UPDATE appointments 
        SET appointment_date = ?, appointment_time = ?, status = 'Rescheduled'
        WHERE appointment_id = ?
    """, (new_date, new_time, appointment_id))
    conn.commit()
    return True, "Appointment rescheduled successfully."


def cancel_appointment(conn: sqlite3.Connection, appointment_id: str) -> Tuple[bool, str]:
    """Mark an appointment as Cancelled."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (appointment_id,))
    apt = cursor.fetchone()

    if not apt:
        return False, f"Appointment '{appointment_id}' not found."

    if apt["status"] == "Cancelled":
        return False, "Appointment is already cancelled."
    if apt["status"] == "Completed":
        return False, "Cannot cancel an appointment that has already been completed."

    cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE appointment_id = ?", (appointment_id,))
    conn.commit()
    return True, "Appointment has been cancelled."


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_schedule_appointment(conn: sqlite3.Connection) -> None:
    """Guide the user through booking an appointment with conflict checking."""
    from modules.patients import get_patient_by_id

    print_subheader("Schedule New Appointment")
    try:
        # Check if the patient exists first
        pid_input = input("Enter Patient ID: ").strip()
        if not pid_input:
            print_warning("Scheduling cancelled.")
            pause()
            return

        patient = get_patient_by_id(conn, pid_input)
        if not patient:
            print_error(f"Patient ID '{pid_input}' not found. Please register the patient first.")
            pause()
            return

        # Do not allow archived patients to schedule new appointments
        if patient["status"] == "Archived":
            print_error("Cannot schedule an appointment for an ARCHIVED patient. Please reactivate the record first.")
            pause()
            return

        print_info(f"Booking for: {patient['full_name']} (ID: {patient['patient_id']})")

        # Date of appointment (cannot be in the past)
        while True:
            date_input = input("Enter Appointment Date (YYYY-MM-DD): ").strip()
            if not date_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_date(date_input, allow_future=True, allow_past=False, field_name="Appointment Date")
            if valid:
                appointment_date = res
                break
            print_error(res)

        # Time of appointment
        while True:
            time_input = input("Enter Appointment Time (HH:MM in 24hr format, e.g., 09:30): ").strip()
            if not time_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_time(time_input, field_name="Appointment Time")
            if valid:
                appointment_time = res
                break
            print_error(res)

        # Department selection
        print("\nSelect Hospital Department:")
        for idx, dept in enumerate(DEPARTMENTS, 1):
            print(f"  {idx}. {dept}")

        dept_choice = input(f"Enter choice (1-{len(DEPARTMENTS)}): ").strip()
        valid, idx_num, err_msg = validate_menu_choice(dept_choice, 1, len(DEPARTMENTS))
        if not valid or idx_num is None:
            print_error("Invalid department selection.")
            pause()
            return
        department = DEPARTMENTS[idx_num - 1]

        # Reason for consultation
        while True:
            reason_input = input("Enter Reason for Appointment: ").strip()
            if not reason_input:
                print_warning("Scheduling cancelled.")
                pause()
                return
            valid, res = validate_non_empty(reason_input, "Reason", min_length=3)
            if valid:
                reason = res
                break
            print_error(res)

        # Check for conflicts before saving
        has_conflict, conflict_msg = check_appointment_conflict(
            conn, appointment_date, appointment_time, department, patient["patient_id"]
        )
        if has_conflict:
            print_error(f"Scheduling Conflict: {conflict_msg}")
            pause()
            return

        # Show summary and ask for confirmation
        print("\nAppointment Summary:")
        print(f"  Patient:    {patient['full_name']} ({patient['patient_id']})")
        print(f"  Date:       {appointment_date}")
        print(f"  Time:       {appointment_time}")
        print(f"  Department: {department}")
        print(f"  Reason:     {reason}")

        if confirm_action("\nConfirm booking?", default_no=False):
            apt_id = schedule_appointment(
                conn, patient["patient_id"], appointment_date, appointment_time, department, reason
            )
            print_success(f"Appointment scheduled successfully! Appointment ID: {apt_id}")
        else:
            print_info("Booking cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nScheduling cancelled by user.")
    pause()


def handle_view_upcoming_appointments(conn: sqlite3.Connection) -> None:
    """Show upcoming appointments ordered by date."""
    print_subheader("Upcoming Appointments")
    appointments = get_upcoming_appointments(conn)

    headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status"]
    rows = [
        [
            a["appointment_id"],
            a["patient_id"],
            a["patient_name"],
            a["appointment_date"],
            a["appointment_time"],
            a["department"],
            a["status"]
        ]
        for a in appointments
    ]
    print_table(headers, rows, empty_message="No upcoming appointments scheduled.")
    pause()


def handle_search_appointments(conn: sqlite3.Connection) -> None:
    """Search appointments and print matching rows."""
    print_subheader("Search Appointments")
    query = input("Enter Appointment ID, Patient ID, or Patient Name: ").strip()

    if not query:
        print_error("Search term cannot be empty.")
        pause()
        return

    results = search_appointments(conn, query)
    headers = ["Apt ID", "Patient ID", "Patient Name", "Date", "Time", "Department", "Status", "Reason"]
    rows = [
        [
            a["appointment_id"],
            a["patient_id"],
            a["patient_name"],
            a["appointment_date"],
            a["appointment_time"],
            a["department"],
            a["status"],
            a["reason"]
        ]
        for a in results
    ]
    print_table(headers, rows, empty_message=f"No appointments found matching '{query}'.")
    pause()


def handle_reschedule_appointment(conn: sqlite3.Connection) -> None:
    """Ask for a new date and time to reschedule an existing booking."""
    print_subheader("Reschedule Appointment")
    apt_id_input = input("Enter Appointment ID to reschedule: ").strip()

    if not apt_id_input:
        print_error("Appointment ID is required.")
        pause()
        return

    apt = get_appointment_by_id(conn, apt_id_input)
    if not apt:
        print_error(f"Appointment '{apt_id_input}' not found.")
        pause()
        return

    if apt["status"] in ("Cancelled", "Completed"):
        print_error(f"Cannot reschedule an appointment with status '{apt['status']}'.")
        pause()
        return

    print_info(f"Current Schedule: {apt['appointment_date']} at {apt['appointment_time']} for {apt['patient_name']} ({apt['department']})")

    # New Date
    while True:
        new_date_input = input("Enter New Date (YYYY-MM-DD): ").strip()
        if not new_date_input:
            print_warning("Rescheduling cancelled.")
            pause()
            return
        valid, res = validate_date(new_date_input, allow_future=True, allow_past=False, field_name="New Date")
        if valid:
            new_date = res
            break
        print_error(res)

    # New Time
    while True:
        new_time_input = input("Enter New Time (HH:MM in 24hr format): ").strip()
        if not new_time_input:
            print_warning("Rescheduling cancelled.")
            pause()
            return
        valid, res = validate_time(new_time_input, field_name="New Time")
        if valid:
            new_time = res
            break
        print_error(res)

    if confirm_action(f"Confirm rescheduling {apt['appointment_id']} to {new_date} {new_time}?", default_no=False):
        success, msg = reschedule_appointment(conn, apt["appointment_id"], new_date, new_time)
        if success:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Rescheduling cancelled.")
    pause()


def handle_cancel_appointment(conn: sqlite3.Connection) -> None:
    """Ask for confirmation before cancelling an appointment."""
    print_subheader("Cancel Appointment")
    apt_id_input = input("Enter Appointment ID to cancel: ").strip()

    if not apt_id_input:
        print_error("Appointment ID is required.")
        pause()
        return

    apt = get_appointment_by_id(conn, apt_id_input)
    if not apt:
        print_error(f"Appointment '{apt_id_input}' not found.")
        pause()
        return

    if apt["status"] == "Cancelled":
        print_warning(f"Appointment {apt['appointment_id']} is already cancelled.")
        pause()
        return

    if apt["status"] == "Completed":
        print_error("Cannot cancel an appointment that has already been completed.")
        pause()
        return

    print_warning(f"You are cancelling appointment {apt['appointment_id']} for {apt['patient_name']} on {apt['appointment_date']} at {apt['appointment_time']}.")
    if confirm_action("Are you sure you want to cancel this appointment?", default_no=True):
        success, msg = cancel_appointment(conn, apt["appointment_id"])
        if success:
            print_success(msg)
        else:
            print_error(msg)
    else:
        print_info("Cancellation aborted.")
    pause()


def appointment_menu(conn: sqlite3.Connection) -> None:
    """Menu loop for the appointment section."""
    while True:
        print_subheader("Appointment Management Menu")
        print("  1. Schedule New Appointment")
        print("  2. View Upcoming Appointments")
        print("  3. Search Appointments (by ID / Patient)")
        print("  4. Reschedule Appointment")
        print("  5. Cancel Appointment")
        print("  6. Return to Main Menu")
        print("-" * 75)

        try:
            choice = input("Enter your choice (1-6): ")
        except (KeyboardInterrupt, EOFError):
            print()
            break

        valid, choice_num, err_msg = validate_menu_choice(choice, 1, 6)
        if not valid:
            print_error(err_msg)
            pause()
            continue

        if choice_num == 1:
            handle_schedule_appointment(conn)
        elif choice_num == 2:
            handle_view_upcoming_appointments(conn)
        elif choice_num == 3:
            handle_search_appointments(conn)
        elif choice_num == 4:
            handle_reschedule_appointment(conn)
        elif choice_num == 5:
            handle_cancel_appointment(conn)
        elif choice_num == 6:
            break
