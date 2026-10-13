"""
Hospital Reports Module

Generates real-time statistics directly from SQLite:
- Patient counts (active vs. archived)
- Appointments by status and department
- Visit summaries by department and date
- Financial totals (billed, collected, and unpaid balances in PHP)
"""

import sqlite3
from decimal import Decimal
from typing import Dict, Any, List

from utils.display import (
    print_subheader,
    print_info,
    print_table,
    pause
)
from utils.validators import validate_menu_choice
from config import CURRENCY_SYMBOL, CURRENCY_CODE


# ==========================================
# Database Aggregation Queries
# ==========================================

def get_patient_statistics(conn: sqlite3.Connection) -> Dict[str, int]:
    """Count total, active, and archived patients."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'Archived' THEN 1 ELSE 0 END) as archived
        FROM patients;
    """)
    row = cursor.fetchone()
    return {
        "total": row["total"] if row and row["total"] else 0,
        "active": row["active"] if row and row["active"] else 0,
        "archived": row["archived"] if row and row["archived"] else 0,
    }


def get_appointment_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Count total appointments and group them by status and department."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM appointments;")
    total = cursor.fetchone()["total"]

    # Count by status (Scheduled, Rescheduled, Completed, Cancelled)
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM appointments 
        GROUP BY status;
    """)
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    # Count by department
    cursor.execute("""
        SELECT department, COUNT(*) as count 
        FROM appointments 
        GROUP BY department 
        ORDER BY count DESC;
    """)
    dept_counts = cursor.fetchall()

    return {
        "total": total,
        "by_status": status_counts,
        "by_department": dept_counts
    }


def get_visit_summary(conn: sqlite3.Connection, group_by: str = "department") -> List[sqlite3.Row]:
    """Count visits grouped by department, month, or date."""
    cursor = conn.cursor()
    if group_by == "month":
        cursor.execute("""
            SELECT SUBSTR(visit_date, 1, 7) as period, COUNT(*) as count
            FROM visits
            GROUP BY period
            ORDER BY period DESC;
        """)
    elif group_by == "date":
        cursor.execute("""
            SELECT SUBSTR(visit_date, 1, 10) as period, COUNT(*) as count
            FROM visits
            GROUP BY period
            ORDER BY period DESC
            LIMIT 15;
        """)
    else:  # Department
        cursor.execute("""
            SELECT department as period, COUNT(*) as count
            FROM visits
            GROUP BY department
            ORDER BY count DESC;
        """)
    return cursor.fetchall()


def get_financial_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Calculate total billed, total paid, and total unpaid balance using Decimal."""
    cursor = conn.cursor()

    cursor.execute("SELECT total_amount, paid_amount, balance, status FROM bills;")
    bills = cursor.fetchall()

    total_billed = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_balance = Decimal("0.00")
    status_counts = {"Unpaid": 0, "Partially Paid": 0, "Paid": 0}

    # Loop through each bill and add up the money totals accurately
    for b in bills:
        total_billed += Decimal(str(b["total_amount"]))
        total_paid += Decimal(str(b["paid_amount"]))
        total_balance += Decimal(str(b["balance"]))
        st = b["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "total_bills": len(bills),
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "status_counts": status_counts
    }


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_patient_report(conn: sqlite3.Connection) -> None:
    """Show patient population summary on screen."""
    print_subheader("Patient Demographics Report")
    stats = get_patient_statistics(conn)

    print()
    print("=" * 55)
    print("  PATIENT RECORDS SUMMARY")
    print("=" * 55)
    print(f"  Total Registered Patients: {stats['total']:>6}")
    print(f"  Active Patients:           {stats['active']:>6}")
    print(f"  Archived Patients:         {stats['archived']:>6}")
    print("=" * 55)
    pause()


def handle_appointment_report(conn: sqlite3.Connection) -> None:
    """Show appointment totals by status and department."""
    print_subheader("Appointment Statistics Report")
    stats = get_appointment_statistics(conn)

    print()
    print("=" * 55)
    print(f"  TOTAL APPOINTMENTS BOOKED: {stats['total']}")
    print("=" * 55)
    print("  BREAKDOWN BY STATUS:")
    for st in ["Scheduled", "Rescheduled", "Completed", "Cancelled"]:
        count = stats["by_status"].get(st, 0)
        print(f"    - {st.ljust(15)}: {count:>4}")

    print("-" * 55)
    print("  BREAKDOWN BY DEPARTMENT:")
    if stats["by_department"]:
        for row in stats["by_department"]:
            print(f"    - {row['department'].ljust(22)}: {row['count']:>4}")
    else:
        print("    (No department appointment data)")
    print("=" * 55)
    pause()


def handle_visit_report(conn: sqlite3.Connection) -> None:
    """Show visits broken down by department and recent daily activity."""
    print_subheader("Clinical Visits Summary")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM visits;")
    total_visits = cursor.fetchone()["count"]

    print_info(f"Total Hospital Visits Recorded: {total_visits}")

    print("\n--- Visits by Department ---")
    dept_rows = get_visit_summary(conn, group_by="department")
    headers_dept = ["Department", "Total Visits"]
    data_dept = [[r["period"], r["count"]] for r in dept_rows]
    print_table(headers_dept, data_dept, alignments=["left", "right"], empty_message="No visits recorded yet.")

    print("\n--- Recent Daily Visit Activity (Last 15 Days Active) ---")
    daily_rows = get_visit_summary(conn, group_by="date")
    headers_daily = ["Date", "Visits Logged"]
    data_daily = [[r["period"], r["count"]] for r in daily_rows]
    print_table(headers_daily, data_daily, alignments=["left", "right"], empty_message="No daily activity recorded.")

    pause()


def handle_financial_report(conn: sqlite3.Connection) -> None:
    """Show overall hospital earnings, collections, and unpaid balances."""
    print_subheader("Hospital Financial & Billing Summary")
    stats = get_financial_statistics(conn)

    print()
    print("=" * 60)
    print("  FINANCIAL REVENUE AND BILLING OVERVIEW")
    print("=" * 60)
    print(f"  Total Invoices Generated:  {stats['total_bills']:>8}")
    print(f"  Total Billed Amount:       {CURRENCY_SYMBOL}{stats['total_billed']:>12.2f}")
    print(f"  Total Payments Received:   {CURRENCY_SYMBOL}{stats['total_paid']:>12.2f}")
    print(f"  Total Outstanding Balance: {CURRENCY_SYMBOL}{stats['total_balance']:>12.2f}")
    print("-" * 60)
    print("  INVOICE STATUS COUNTS:")
    print(f"    * Paid In Full:          {stats['status_counts'].get('Paid', 0):>8}")
    print(f"    * Partially Paid:        {stats['status_counts'].get('Partially Paid', 0):>8}")
    print(f"    * Unpaid:                {stats['status_counts'].get('Unpaid', 0):>8}")
    print("=" * 60)
    pause()


def handle_comprehensive_dashboard(conn: sqlite3.Connection) -> None:
    """Show an all-in-one summary of patients, appointments, visits, and revenue."""
    print_subheader("Hospital Executive Dashboard")

    p_stats = get_patient_statistics(conn)
    a_stats = get_appointment_statistics(conn)
    f_stats = get_financial_statistics(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM visits;")
    v_total = cursor.fetchone()["count"]

    print()
    print("=======================================================================")
    print("              HOSPITAL MANAGEMENT EXECUTIVE SUMMARY                    ")
    print("=======================================================================")
    print("  [PATIENTS]")
    print(f"    Total Registered: {p_stats['total']} | Active: {p_stats['active']} | Archived: {p_stats['archived']}")
    print("-" * 71)
    print("  [APPOINTMENTS]")
    print(f"    Total: {a_stats['total']} | Scheduled: {a_stats['by_status'].get('Scheduled', 0)} | Rescheduled: {a_stats['by_status'].get('Rescheduled', 0)} | Cancelled: {a_stats['by_status'].get('Cancelled', 0)}")
    print("-" * 71)
    print("  [CLINICAL VISITS]")
    print(f"    Total Patient Visits Logged: {v_total}")
    print("-" * 71)
    print("  [FINANCIAL REVENUE]")
    print(f"    Total Billed:      {CURRENCY_SYMBOL}{f_stats['total_billed']:.2f}")
    print(f"    Payments Received: {CURRENCY_SYMBOL}{f_stats['total_paid']:.2f}")
    print(f"    Outstanding Bal:   {CURRENCY_SYMBOL}{f_stats['total_balance']:.2f}")
    print("=======================================================================")
    pause()


def reports_menu(conn: sqlite3.Connection) -> None:
    """Submenu for hospital reports and summaries."""
    while True:
        print_subheader("Hospital Reports & Analytics Menu")
        print("  1. Hospital Executive Dashboard (Overview)")
        print("  2. Patient Demographics Report")
        print("  3. Appointment Statistics Report")
        print("  4. Clinical Visits Summary")
        print("  5. Financial & Revenue Report")
        print("  6. Return to Main Menu")
        print("-" * 75)

        try:
            choice = input("Enter your choice (1-6): ")
        except (KeyboardInterrupt, EOFError):
            print()
            break

        valid, choice_num, err_msg = validate_menu_choice(choice, 1, 6)
        if not valid:
            from utils.display import print_error
            print_error(err_msg)
            pause()
            continue

        if choice_num == 1:
            handle_comprehensive_dashboard(conn)
        elif choice_num == 2:
            handle_patient_report(conn)
        elif choice_num == 3:
            handle_appointment_report(conn)
        elif choice_num == 4:
            handle_visit_report(conn)
        elif choice_num == 5:
            handle_financial_report(conn)
        elif choice_num == 6:
            break
