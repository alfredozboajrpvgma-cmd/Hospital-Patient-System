"""
Handles our SQLite database connection, table setup, and transactions.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional
from config import DATABASE_PATH, DATA_DIR


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Connect to the SQLite database.
    Enables foreign keys and lets us access columns by name.
    """
    target_path = db_path if db_path is not None else str(DATABASE_PATH)
    
    # Create the data folder if it does not exist yet
    if target_path != ":memory:":
        parent_dir = os.path.dirname(target_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(target_path, check_same_thread=False, timeout=10.0)
    # SQLite turns off foreign keys by default, so we need to turn it on
    conn.execute("PRAGMA foreign_keys = ON;")
    # Row factory lets us write row['column_name'] instead of index numbers
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction_scope(conn: sqlite3.Connection):
    """
    Helps run multiple database steps safely.
    Saves everything on success, or cancels all changes if something fails.
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def create_schema(conn: sqlite3.Connection) -> None:
    """
    Creates all tables, constraints, and indexes.
    Safe to call anytime because it uses CREATE TABLE IF NOT EXISTS.
    """
    cursor = conn.cursor()

    # 1. Patients Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            sex TEXT NOT NULL CHECK(sex IN ('Male', 'Female', 'Other')),
            contact_number TEXT NOT NULL,
            address TEXT NOT NULL,
            emergency_contact TEXT NOT NULL,
            registration_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Archived'))
        );
    """)

    # 2. Appointments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            department TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled', 'Completed', 'Cancelled', 'Rescheduled')),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)

    # 3. Visits Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            visit_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            visit_date TEXT NOT NULL,
            department TEXT NOT NULL,
            attending_provider TEXT NOT NULL,
            notes TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)

    # 4. Bills Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            bill_date TEXT NOT NULL,
            total_amount TEXT NOT NULL DEFAULT '0.00',
            paid_amount TEXT NOT NULL DEFAULT '0.00',
            balance TEXT NOT NULL DEFAULT '0.00',
            status TEXT NOT NULL DEFAULT 'Unpaid' CHECK(status IN ('Unpaid', 'Partially Paid', 'Paid')),
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON UPDATE CASCADE
        );
    """)

    # 5. Bill Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT NOT NULL,
            service_description TEXT NOT NULL,
            amount TEXT NOT NULL,
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
        );
    """)

    # 6. Payments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            bill_id TEXT NOT NULL,
            payment_date TEXT NOT NULL,
            amount TEXT NOT NULL,
            payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash', 'PhilHealth', 'HMO / Health Card', 'GCash', 'Maya', 'Credit Card', 'Debit Card', 'Bank Transfer')),
            notes TEXT,
            FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON UPDATE CASCADE
        );
    """)

    # Indexes help searches run faster as records increase
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_patient ON visits(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id);")

    conn.commit()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Prepares the database file and makes sure all tables are ready.
    Called once when the application starts.
    """
    conn = get_connection(db_path)
    try:
        create_schema(conn)
    finally:
        conn.close()
