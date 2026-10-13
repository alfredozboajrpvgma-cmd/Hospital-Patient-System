# Hospital Patient Management System (CLI) - Philippine Edition

A terminal-based hospital management system written in Python 3 and SQLite. Built as an IT programming project to handle everyday hospital tasks like patient registration, doctor appointments, consultation records, itemized billing in Philippine Pesos (PHP), and reports.

---

## About the Project

This project was built to practice writing clean, modular Python code without relying on external web frameworks or heavy third-party packages. Everything runs directly in the command prompt or terminal using Python's built-in libraries.

We customized this project for Philippine healthcare settings:
- Currency is in Philippine Peso (PHP / ₱).
- Supports local payment options like Cash, PhilHealth, GCash, Maya, and HMO cards.
- Validates Philippine contact numbers (e.g., `0917-123-4567` or `+639181234567`).
- Common hospital departments like OPD, ER, Pediatrics, Internal Medicine, Surgery, and OB-GYN.

---

## Main Features

### 1. Patient Management
- Register new patients with basic info (Name, Birthday, Sex, Contact, Address, Emergency Contact).
- Auto-generates patient IDs (like `PAT-1001`, `PAT-1002`).
- Checks for potential duplicate patients before registering.
- Search patients by ID or by name.
- Update patient information.
- Archive patients instead of deleting them permanently so medical history isn't lost.
- Reactivate archived patients anytime.

### 2. Appointment Scheduling
- Schedule consultations with a specific department and date/time.
- Prevents double-booking (checks if the doctor/department or the patient is already booked at that slot).
- Reschedule or cancel appointments.
- Filter appointments by status (Scheduled, Completed, Cancelled).

### 3. Clinical Visit Records
- Log doctor consultations, attending physician, and clinical notes/diagnosis.
- View the complete visit history of a specific patient.
- View all hospital visits or look up details for a single visit.

### 4. Billing and Payments (PHP)
- Create itemized hospital bills (Doctor's PF, lab tests, medicines, etc.).
- Computes totals and remaining balances using Python's `Decimal` to avoid rounding errors with centavos.
- Accepts full or partial payments.
- Supports Cash, PhilHealth, GCash, Maya, HMO, Credit/Debit card, and Bank Transfer.
- Tracks invoice status: Unpaid, Partially Paid, or Paid.
- Generates a printable-style invoice in the terminal.

### 5. Reports and Analytics
- Executive dashboard showing patient, appointment, visit, and revenue totals.
- Patient breakdown (Active vs. Archived).
- Appointment statistics grouped by status and department.
- Daily and monthly visit counts.
- Financial report showing total billed, total collected, and remaining balance.

---

## Project Structure

```
Hospital Patient System (CLI)/
├── main.py                     # Program entry point and main menu
├── database.py                 # SQLite database setup and tables
├── config.py                   # System constants (departments, payment methods, currency)
├── requirements.txt            # Project dependencies (standard library only)
├── README.md                   # Project documentation
├── data/
│   └── hospital.db             # SQLite database file (created automatically on first run)
├── modules/
│   ├── patients.py             # Patient records logic and menu
│   ├── appointments.py         # Appointment booking logic and menu
│   ├── visits.py               # Visit records logic and menu
│   ├── billing.py              # Billing and payment logic and menu
│   └── reports.py              # System summaries and reports menu
├── utils/
│   ├── display.py              # Terminal table formatting and headers
│   └── validators.py           # Input validation (dates, times, phone numbers, money)
└── tests/
    ├── test_patients.py        # Tests for patient CRUD and ID generation
    ├── test_appointments.py    # Tests for booking and conflict detection
    ├── test_billing.py         # Tests for bill math and payment tracking
    ├── test_visits.py          # Tests for visit logging
    └── test_validators.py      # Tests for validation helpers
```

---

## How to Run the Program

### Requirements
- Python 3.8 or higher installed on your computer.
- That's it! No `pip install` needed because the project uses Python's standard library (`sqlite3`, `datetime`, `decimal`, `unittest`).

### Option 1: Run the Standalone .EXE (No Python Needed)
You can run the program directly without installing Python:
- Just double-click `Hospital_Patient_System.exe` in the project folder (or run `.\Hospital_Patient_System.exe` in PowerShell / CMD).

### Option 2: Run via Python Script
1. Open your terminal or Command Prompt (PowerShell / CMD).
2. Go to the project folder:
   ```bash
   cd "Hospital Patient System (CLI)"
   ```
3. Run `main.py`:
   ```bash
   # On Windows:
   py main.py

   # Or:
   python main.py
   ```

When you run it for the first time, it automatically creates the `data/hospital.db` SQLite database and all required tables.

---

## Running the Unit Tests

We wrote automated tests using Python's built-in `unittest` module. The tests use a temporary in-memory database (`:memory:`) so running them will never touch or mess up your actual saved hospital data.

To run all tests:

```bash
# On Windows:
py -m unittest discover tests -v

# Or:
python -m unittest discover tests -v
```

All 27 test cases should pass with `OK`.

---

## Database Tables

The database has 6 tables connected with foreign keys:

1. **`patients`** - Stores patient profiles (`patient_id`, `full_name`, `dob`, `sex`, `contact_number`, `address`, `emergency_contact`, `status`).
2. **`appointments`** - Stores scheduled visits (`appointment_id`, `patient_id`, `appointment_date`, `appointment_time`, `department`, `reason`, `status`).
3. **`visits`** - Clinical visit notes (`visit_id`, `patient_id`, `visit_date`, `department`, `attending_provider`, `notes`).
4. **`bills`** - Invoice summary (`bill_id`, `patient_id`, `bill_date`, `total_amount`, `paid_amount`, `balance`, `status`).
5. **`bill_items`** - Line items for each bill (`item_id`, `bill_id`, `service_description`, `amount`).
6. **`payments`** - Payment transactions (`payment_id`, `bill_id`, `payment_date`, `amount`, `payment_method`, `notes`).

---

## Key Design Choices

A few things we focused on while building this:
- **Foreign Keys Enabled**: SQLite disables foreign keys by default, so we run `PRAGMA foreign_keys = ON;` on every connection to keep data properly linked.
- **Decimal for Money**: Floating-point numbers like `float` can have rounding glitches (e.g., `0.1 + 0.2 = 0.30000000000000004`). We used Python's `Decimal` type so all peso and centavo amounts are 100% accurate.
- **Soft Deleting (Archive)**: In a hospital system, deleting patient records permanently can wipe out their medical history and past billing trails. Instead of `DELETE`, we change their status to `Archived`.
- **Conflict Checking**: Before confirming an appointment, the system checks whether the patient or the department is already booked at that same date and time to prevent double-booking.

---

## Project Info
- **Language**: Python 3
- **Database**: SQLite
- **Interface**: Command Line Interface (CLI)
- **Target OS**: Windows / macOS / Linux
