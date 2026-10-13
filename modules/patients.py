"""
Patient Management module.
Handles registering new patients, searching, updating info, and archiving records.
"""

import sqlite3
from datetime import date
from typing import Optional, List, Dict, Any

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
    validate_phone,
    validate_sex,
    validate_menu_choice
)
from config import DATE_FORMAT


# ==========================================
# Database Operations
# ==========================================

def generate_patient_id(conn: sqlite3.Connection) -> str:
    """
    Generate the next patient ID like PAT-1001, PAT-1002, etc.
    Looks up the highest existing number and adds 1.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id FROM patients WHERE patient_id LIKE 'PAT-%' ORDER BY patient_id DESC")
    rows = cursor.fetchall()
    
    max_id_num = 1000
    for row in rows:
        pid = row["patient_id"]
        parts = pid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val
                
    next_id_num = max_id_num + 1
    return f"PAT-{next_id_num}"


def register_patient(
    conn: sqlite3.Connection,
    full_name: str,
    dob: str,
    sex: str,
    contact_number: str,
    address: str,
    emergency_contact: str,
    registration_date: Optional[str] = None
) -> str:
    """Save a new patient record into the database and return their assigned ID."""
    patient_id = generate_patient_id(conn)
    reg_date = registration_date or date.today().strftime(DATE_FORMAT)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO patients (
            patient_id, full_name, dob, sex, contact_number,
            address, emergency_contact, registration_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active');
    """, (
        patient_id, full_name, dob, sex, contact_number,
        address, emergency_contact, reg_date
    ))
    conn.commit()
    return patient_id


def check_potential_duplicate(
    conn: sqlite3.Connection,
    full_name: str,
    dob: str,
    contact_number: str
) -> Optional[sqlite3.Row]:
    """Check if someone with the same name, birthday, and contact number is already registered."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM patients 
        WHERE LOWER(full_name) = LOWER(?) AND dob = ? AND contact_number = ?
    """, (full_name, dob, contact_number))
    return cursor.fetchone()


def get_patient_by_id(conn: sqlite3.Connection, patient_id: str) -> Optional[sqlite3.Row]:
    """Look up a single patient using their ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE UPPER(patient_id) = UPPER(?)", (patient_id.strip(),))
    return cursor.fetchone()


def get_all_patients(
    conn: sqlite3.Connection,
    filter_status: Optional[str] = None
) -> List[sqlite3.Row]:
    """Get all patients, or filter by Active / Archived."""
    cursor = conn.cursor()
    if filter_status:
        cursor.execute("SELECT * FROM patients WHERE status = ? ORDER BY patient_id ASC", (filter_status,))
    else:
        cursor.execute("SELECT * FROM patients ORDER BY patient_id ASC")
    return cursor.fetchall()


def search_patients(conn: sqlite3.Connection, query: str) -> List[sqlite3.Row]:
    """Find patients by matching part of their ID or name."""
    search_term = f"%{query.strip()}%"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM patients 
        WHERE patient_id LIKE ? OR full_name LIKE ?
        ORDER BY patient_id ASC
    """, (search_term, search_term))
    return cursor.fetchall()


def update_patient(
    conn: sqlite3.Connection,
    patient_id: str,
    **fields: Any
) -> bool:
    """Update patient details like address or phone number."""
    allowed_fields = {
        "full_name", "dob", "sex", "contact_number",
        "address", "emergency_contact", "status"
    }
    updates = []
    values = []

    # Only include fields that are actually allowed and have values
    for key, value in fields.items():
        if key in allowed_fields and value is not None:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(patient_id)
    query = f"UPDATE patients SET {', '.join(updates)} WHERE patient_id = ?"
    cursor = conn.cursor()
    cursor.execute(query, tuple(values))
    conn.commit()
    return cursor.rowcount > 0


def archive_patient(conn: sqlite3.Connection, patient_id: str) -> bool:
    """
    Archive a patient record instead of permanently deleting it.
    This keeps their medical and billing history safe.
    """
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Archived' WHERE patient_id = ?", (patient_id,))
    conn.commit()
    return cursor.rowcount > 0


def reactivate_patient(conn: sqlite3.Connection, patient_id: str) -> bool:
    """Change an archived patient's status back to Active."""
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Active' WHERE patient_id = ?", (patient_id,))
    conn.commit()
    return cursor.rowcount > 0


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_register_patient(conn: sqlite3.Connection) -> None:
    """Ask for patient details, check each input, and save to database."""
    print_subheader("Register New Patient")
    print("Leave input blank or press Ctrl+C to cancel at any prompt.\n")

    try:
        # Full Name
        while True:
            name_input = input("Enter Full Name: ")
            if not name_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_non_empty(name_input, "Full Name", min_length=2)
            if valid:
                full_name = res
                break
            print_error(res)

        # Date of Birth
        while True:
            dob_input = input("Enter Date of Birth (YYYY-MM-DD): ")
            if not dob_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_date(dob_input, allow_future=False, allow_past=True, field_name="Date of Birth")
            if valid:
                dob = res
                break
            print_error(res)

        # Sex
        while True:
            sex_input = input("Enter Sex (Male/Female/Other or M/F/O): ")
            if not sex_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_sex(sex_input)
            if valid:
                sex = res
                break
            print_error(res)

        # Contact Number
        while True:
            contact_input = input("Enter Contact Number (e.g. 09171234567 or +639171234567): ")
            if not contact_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_phone(contact_input, "Contact number")
            if valid:
                contact_number = res
                break
            print_error(res)

        # Address
        while True:
            address_input = input("Enter Address (Street/Subdivision, Brgy, City/Municipality, Province): ")
            if not address_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_non_empty(address_input, "Address", min_length=3)
            if valid:
                address = res
                break
            print_error(res)

        # Emergency Contact
        while True:
            emerg_input = input("Enter Emergency Contact (Full Name & Contact No.): ")
            if not emerg_input.strip():
                print_warning("Registration cancelled.")
                return
            valid, res = validate_non_empty(emerg_input, "Emergency Contact", min_length=3)
            if valid:
                emergency_contact = res
                break
            print_error(res)

        # Warn if this person might already be in the database
        duplicate = check_potential_duplicate(conn, full_name, dob, contact_number)
        if duplicate:
            print_warning(f"An existing patient record ({duplicate['patient_id']}) matches this Name, DOB, and Phone!")
            if not confirm_action("Do you still want to register this as a new record?", default_no=True):
                print_info("Registration aborted.")
                return

        # Show a summary so the user can double check before saving
        print("\nPatient Summary:")
        print(f"  Name:              {full_name}")
        print(f"  DOB:               {dob}")
        print(f"  Sex:               {sex}")
        print(f"  Contact:           {contact_number}")
        print(f"  Address:           {address}")
        print(f"  Emergency Contact: {emergency_contact}")
        
        if confirm_action("\nConfirm registration?", default_no=False):
            pid = register_patient(
                conn, full_name, dob, sex, contact_number, address, emergency_contact
            )
            print_success(f"Patient registered successfully! Assigned ID: {pid}")
        else:
            print_info("Registration cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nRegistration cancelled by user.")
    pause()


def handle_view_all_patients(conn: sqlite3.Connection) -> None:
    """Display all registered patients in a table."""
    print_subheader("All Registered Patients")
    patients = get_all_patients(conn)

    headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
    rows = [
        [
            p["patient_id"],
            p["full_name"],
            p["dob"],
            p["sex"],
            p["contact_number"],
            p["status"]
        ]
        for p in patients
    ]
    print_table(headers, rows, empty_message="No patient records found in database.")
    pause()


def handle_search_patients(conn: sqlite3.Connection) -> None:
    """Find patients by matching their ID or part of their name."""
    print_subheader("Search Patients")
    query = input("Enter Patient ID or Name to search: ").strip()

    if not query:
        print_error("Search term cannot be empty.")
        pause()
        return

    results = search_patients(conn, query)
    headers = ["Patient ID", "Full Name", "DOB", "Sex", "Contact", "Status"]
    rows = [
        [
            p["patient_id"],
            p["full_name"],
            p["dob"],
            p["sex"],
            p["contact_number"],
            p["status"]
        ]
        for p in results
    ]
    print_table(headers, rows, empty_message=f"No patients found matching '{query}'.")
    pause()


def handle_view_patient_details(conn: sqlite3.Connection) -> None:
    """Show the complete profile of a specific patient."""
    print_subheader("View Patient Details")
    pid_input = input("Enter Patient ID: ").strip()

    if not pid_input:
        print_error("Patient ID is required.")
        pause()
        return

    patient = get_patient_by_id(conn, pid_input)
    if not patient:
        print_error(f"Patient with ID '{pid_input}' was not found.")
        pause()
        return

    print()
    print("=" * 60)
    print(f"  PATIENT RECORD: {patient['patient_id']} ({patient['status']})")
    print("=" * 60)
    print(f"  Full Name:          {patient['full_name']}")
    print(f"  Date of Birth:      {patient['dob']}")
    print(f"  Sex:                {patient['sex']}")
    print(f"  Contact Number:     {patient['contact_number']}")
    print(f"  Address:            {patient['address']}")
    print(f"  Emergency Contact:  {patient['emergency_contact']}")
    print(f"  Registration Date:  {patient['registration_date']}")
    print(f"  Account Status:     {patient['status']}")
    print("=" * 60)
    pause()


def handle_update_patient(conn: sqlite3.Connection) -> None:
    """Let the user edit patient fields while keeping current values if left blank."""
    print_subheader("Update Patient Record")
    pid_input = input("Enter Patient ID to update: ").strip()

    if not pid_input:
        print_error("Patient ID is required.")
        pause()
        return

    patient = get_patient_by_id(conn, pid_input)
    if not patient:
        print_error(f"Patient with ID '{pid_input}' was not found.")
        pause()
        return

    # If archived, offer to reactivate before editing
    if patient["status"] == "Archived":
        print_warning("This patient record is currently ARCHIVED.")
        if confirm_action("Would you like to reactivate this patient first?", default_no=True):
            reactivate_patient(conn, patient["patient_id"])
            print_success(f"Patient {patient['patient_id']} has been reactivated.")
        else:
            print_info("Cannot modify an archived record.")
            pause()
            return

    print(f"\nEditing record for {patient['patient_id']} ({patient['full_name']})")
    print("Press Enter without typing to keep the current value.\n")

    updated_fields: Dict[str, Any] = {}

    try:
        # Full Name
        new_name = input(f"Full Name [{patient['full_name']}]: ").strip()
        if new_name:
            val, res = validate_non_empty(new_name, "Full Name", min_length=2)
            if val:
                updated_fields["full_name"] = res
            else:
                print_error(f"Keeping existing name due to error: {res}")

        # Date of Birth
        new_dob = input(f"Date of Birth [{patient['dob']}]: ").strip()
        if new_dob:
            val, res = validate_date(new_dob, allow_future=False, allow_past=True, field_name="DOB")
            if val:
                updated_fields["dob"] = res
            else:
                print_error(f"Keeping existing DOB due to error: {res}")

        # Sex
        new_sex = input(f"Sex [{patient['sex']}]: ").strip()
        if new_sex:
            val, res = validate_sex(new_sex)
            if val:
                updated_fields["sex"] = res
            else:
                print_error(f"Keeping existing sex due to error: {res}")

        # Contact Number
        new_phone = input(f"Contact Number [{patient['contact_number']}]: ").strip()
        if new_phone:
            val, res = validate_phone(new_phone, "Contact number")
            if val:
                updated_fields["contact_number"] = res
            else:
                print_error(f"Keeping existing contact due to error: {res}")

        # Address
        new_addr = input(f"Address [{patient['address']}]: ").strip()
        if new_addr:
            val, res = validate_non_empty(new_addr, "Address", min_length=3)
            if val:
                updated_fields["address"] = res
            else:
                print_error(f"Keeping existing address due to error: {res}")

        # Emergency Contact
        new_emerg = input(f"Emergency Contact [{patient['emergency_contact']}]: ").strip()
        if new_emerg:
            val, res = validate_non_empty(new_emerg, "Emergency contact", min_length=3)
            if val:
                updated_fields["emergency_contact"] = res
            else:
                print_error(f"Keeping existing emergency contact due to error: {res}")

        if not updated_fields:
            print_info("No changes were made.")
            pause()
            return

        if confirm_action("\nSave updated patient details?", default_no=False):
            if update_patient(conn, patient["patient_id"], **updated_fields):
                print_success(f"Patient {patient['patient_id']} updated successfully.")
            else:
                print_error("Failed to update patient record.")
        else:
            print_info("Updates discarded.")

    except (KeyboardInterrupt, EOFError):
        print("\nUpdate cancelled by user.")
    pause()


def handle_archive_patient(conn: sqlite3.Connection) -> None:
    """Ask for confirmation before archiving a patient."""
    print_subheader("Archive Patient Record")
    pid_input = input("Enter Patient ID to archive: ").strip()

    if not pid_input:
        print_error("Patient ID is required.")
        pause()
        return

    patient = get_patient_by_id(conn, pid_input)
    if not patient:
        print_error(f"Patient with ID '{pid_input}' was not found.")
        pause()
        return

    if patient["status"] == "Archived":
        print_warning(f"Patient {patient['patient_id']} is already archived.")
        pause()
        return

    print_warning(f"You are about to archive patient {patient['patient_id']} - {patient['full_name']}.")
    print_info("Archiving preserves historical visits, appointments, and billing data while marking the patient inactive.")

    if confirm_action("Are you sure you want to archive this record?", default_no=True):
        if archive_patient(conn, patient["patient_id"]):
            print_success(f"Patient {patient['patient_id']} has been archived.")
        else:
            print_error("Failed to archive patient record.")
    else:
        print_info("Archiving cancelled.")
    pause()


def patient_menu(conn: sqlite3.Connection) -> None:
    """Menu loop for the patient section."""
    while True:
        print_subheader("Patient Management Menu")
        print("  1. Register New Patient")
        print("  2. View All Patients")
        print("  3. Search Patients (by ID or Name)")
        print("  4. View Patient Details")
        print("  5. Update Patient Details")
        print("  6. Archive Patient Record")
        print("  7. Return to Main Menu")
        print("-" * 75)

        try:
            choice = input("Enter your choice (1-7): ")
        except (KeyboardInterrupt, EOFError):
            print()
            break

        valid, choice_num, err_msg = validate_menu_choice(choice, 1, 7)
        if not valid:
            print_error(err_msg)
            pause()
            continue

        if choice_num == 1:
            handle_register_patient(conn)
        elif choice_num == 2:
            handle_view_all_patients(conn)
        elif choice_num == 3:
            handle_search_patients(conn)
        elif choice_num == 4:
            handle_view_patient_details(conn)
        elif choice_num == 5:
            handle_update_patient(conn)
        elif choice_num == 6:
            handle_archive_patient(conn)
        elif choice_num == 7:
            break
