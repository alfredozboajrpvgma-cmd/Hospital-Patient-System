"""
Billing and Payment Module - Philippine Edition

Handles creating bills with itemized services, recording payments (Cash, GCash, Maya, etc.),
calculating balances, and keeping track of paid/unpaid invoices in Philippine Peso (PHP).
"""

import sqlite3
from datetime import datetime, date
from decimal import Decimal
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
    validate_decimal_amount,
    validate_menu_choice
)
from config import (
    VALID_PAYMENT_METHODS,
    DATE_FORMAT,
    DATETIME_FORMAT,
    CURRENCY_SYMBOL,
    CURRENCY_CODE
)


# ==========================================
# Database Operations
# ==========================================

def generate_bill_id(conn: sqlite3.Connection) -> str:
    """Generate the next bill ID like BIL-1001, BIL-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT bill_id FROM bills WHERE bill_id LIKE 'BIL-%' ORDER BY bill_id DESC")
    rows = cursor.fetchall()

    # Find the highest bill number and add 1
    max_id_num = 1000
    for row in rows:
        bid = row["bill_id"]
        parts = bid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"BIL-{next_id_num}"


def generate_payment_id(conn: sqlite3.Connection) -> str:
    """Generate the next payment ID like PAY-1001, PAY-1002."""
    cursor = conn.cursor()
    cursor.execute("SELECT payment_id FROM payments WHERE payment_id LIKE 'PAY-%' ORDER BY payment_id DESC")
    rows = cursor.fetchall()

    # Find the highest payment number and add 1
    max_id_num = 1000
    for row in rows:
        pid = row["payment_id"]
        parts = pid.split("-")
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_id_num:
                max_id_num = val

    next_id_num = max_id_num + 1
    return f"PAY-{next_id_num}"


def create_bill(
    conn: sqlite3.Connection,
    patient_id: str,
    items: List[Tuple[str, Decimal]],
    bill_date: Optional[str] = None
) -> str:
    """Create a new bill and its line items inside a single database transaction."""
    if not items:
        raise ValueError("Cannot create a bill with zero items.")

    bill_id = generate_bill_id(conn)
    date_val = bill_date or date.today().strftime(DATE_FORMAT)

    # Add up all line items using Decimal for exact cents
    total_amount = sum((amount for _, amount in items), Decimal("0.00"))
    total_str = f"{total_amount:.2f}"
    paid_str = "0.00"
    balance_str = total_str
    status = "Unpaid"

    cursor = conn.cursor()
    # Save the main bill record first
    cursor.execute("""
        INSERT INTO bills (
            bill_id, patient_id, bill_date, total_amount, paid_amount, balance, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (bill_id, patient_id, date_val, total_str, paid_str, balance_str, status))

    # Save each service line item linked to this bill
    for desc, amt in items:
        cursor.execute("""
            INSERT INTO bill_items (bill_id, service_description, amount)
            VALUES (?, ?, ?);
        """, (bill_id, desc, f"{amt:.2f}"))

    conn.commit()
    return bill_id


def get_bill_by_id(conn: sqlite3.Connection, bill_id: str) -> Optional[sqlite3.Row]:
    """Get a bill record along with patient contact details."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name, p.contact_number
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE UPPER(b.bill_id) = UPPER(?)
    """, (bill_id.strip(),))
    return cursor.fetchone()


def get_bill_items(conn: sqlite3.Connection, bill_id: str) -> List[sqlite3.Row]:
    """Get all itemized charges listed on a bill."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM bill_items WHERE UPPER(bill_id) = UPPER(?) ORDER BY item_id ASC
    """, (bill_id.strip(),))
    return cursor.fetchall()


def get_payments_by_bill(conn: sqlite3.Connection, bill_id: str) -> List[sqlite3.Row]:
    """Get all payments made towards a specific bill."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM payments WHERE UPPER(bill_id) = UPPER(?) ORDER BY payment_date ASC
    """, (bill_id.strip(),))
    return cursor.fetchall()


def get_all_bills(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get every bill in the database, newest first."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        ORDER BY b.bill_date DESC, b.bill_id DESC
    """)
    return cursor.fetchall()


def get_outstanding_bills(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """Get all bills that still have an unpaid balance (Unpaid or Partially Paid)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE b.status IN ('Unpaid', 'Partially Paid') AND CAST(b.balance AS REAL) > 0
        ORDER BY b.bill_date DESC
    """)
    return cursor.fetchall()


def get_bills_by_patient(conn: sqlite3.Connection, patient_id: str) -> List[sqlite3.Row]:
    """Get all bills belonging to a single patient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.*, p.full_name as patient_name
        FROM bills b
        JOIN patients p ON b.patient_id = p.patient_id
        WHERE UPPER(b.patient_id) = UPPER(?)
        ORDER BY b.bill_date DESC
    """, (patient_id.strip(),))
    return cursor.fetchall()


def record_payment(
    conn: sqlite3.Connection,
    bill_id: str,
    amount: Decimal,
    payment_method: str,
    notes: str = "",
    payment_date: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Record a payment against a bill, recalculate balance, and update status.
    Returns: (success, message, payment_id)
    """
    if amount <= Decimal("0.00"):
        return False, "Payment amount must be greater than 0.", None

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills WHERE UPPER(bill_id) = UPPER(?)", (bill_id.strip(),))
    bill = cursor.fetchone()

    if not bill:
        return False, f"Bill '{bill_id}' not found.", None

    current_balance = Decimal(str(bill["balance"]))
    current_paid = Decimal(str(bill["paid_amount"]))
    total_amount = Decimal(str(bill["total_amount"]))

    # Check if the bill is already fully settled
    if current_balance <= Decimal("0.00"):
        return False, f"Bill '{bill_id}' is already fully paid.", None

    # Make sure payment does not exceed the remaining balance
    if amount > current_balance:
        return False, f"Payment amount ({CURRENCY_SYMBOL}{amount:.2f}) exceeds outstanding balance ({CURRENCY_SYMBOL}{current_balance:.2f}).", None

    # Calculate new paid amount and remaining balance
    new_paid = current_paid + amount
    new_balance = current_balance - amount

    # If remaining balance reaches zero, mark as Paid; otherwise Partially Paid
    if new_balance == Decimal("0.00"):
        new_status = "Paid"
    else:
        new_status = "Partially Paid"

    payment_id = generate_payment_id(conn)
    pay_date = payment_date or datetime.now().strftime(DATETIME_FORMAT)

    try:
        # Save payment record and update bill totals together
        cursor.execute("""
            INSERT INTO payments (
                payment_id, bill_id, payment_date, amount, payment_method, notes
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (payment_id, bill["bill_id"], pay_date, f"{amount:.2f}", payment_method, notes))

        cursor.execute("""
            UPDATE bills
            SET paid_amount = ?, balance = ?, status = ?
            WHERE bill_id = ?;
        """, (f"{new_paid:.2f}", f"{new_balance:.2f}", new_status, bill["bill_id"]))

        conn.commit()
        return True, f"Payment of {CURRENCY_SYMBOL}{amount:.2f} recorded successfully via {payment_method}! Remaining balance: {CURRENCY_SYMBOL}{new_balance:.2f}", payment_id
    except Exception as exc:
        conn.rollback()
        return False, f"Failed to record payment: {exc}", None


# ==========================================
# CLI Submenu and Handlers
# ==========================================

def handle_generate_bill(conn: sqlite3.Connection) -> None:
    """Menu flow to build and save a new bill with itemized services."""
    from modules.patients import get_patient_by_id

    print_subheader("Generate New Hospital Bill")
    try:
        pid_input = input("Enter Patient ID: ").strip()
        if not pid_input:
            print_warning("Billing cancelled.")
            pause()
            return

        patient = get_patient_by_id(conn, pid_input)
        if not patient:
            print_error(f"Patient with ID '{pid_input}' not found.")
            pause()
            return

        print_info(f"Generating bill for: {patient['full_name']} ({patient['patient_id']})")
        print("\nEnter service items one by one. Enter empty description when finished.\n")

        items: List[Tuple[str, Decimal]] = []

        # Keep adding items until the user enters an empty description
        while True:
            item_num = len(items) + 1
            desc_input = input(f"Item #{item_num} Description (or press Enter to finish): ").strip()
            if not desc_input:
                if items:
                    break
                else:
                    print_warning("Bill creation cancelled (no items added).")
                    pause()
                    return

            valid_desc, desc = validate_non_empty(desc_input, f"Item #{item_num} Description", min_length=2)
            if not valid_desc:
                print_error(desc)
                continue

            # Get cost for this item
            while True:
                charge_input = input(f"Item #{item_num} Amount ({CURRENCY_SYMBOL}): ").strip()
                valid_amt, amt_decimal, err = validate_decimal_amount(charge_input, field_name=f"Charge for '{desc}'")
                if valid_amt and amt_decimal is not None:
                    items.append((desc, amt_decimal))
                    print_info(f"Added: {desc} -> {CURRENCY_SYMBOL}{amt_decimal:.2f}")
                    break
                print_error(err)

        total_sum = sum((amt for _, amt in items), Decimal("0.00"))

        # Show bill summary before saving
        print("\nBill Summary:")
        print(f"  Patient:      {patient['full_name']} ({patient['patient_id']})")
        print(f"  Total Items:  {len(items)}")
        for i, (d, a) in enumerate(items, 1):
            print(f"    {i}. {d.ljust(35)} {CURRENCY_SYMBOL}{a:>9.2f}")
        print("  " + "-" * 48)
        print(f"  Total Amount: {CURRENCY_SYMBOL}{total_sum:.2f}")

        if confirm_action("\nConfirm and generate bill?", default_no=False):
            bill_id = create_bill(conn, patient["patient_id"], items)
            print_success(f"Bill created successfully! Bill ID: {bill_id}")
        else:
            print_info("Bill generation cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled by user.")
    pause()


def handle_record_payment(conn: sqlite3.Connection) -> None:
    """Menu flow to collect and record a payment against an unpaid bill."""
    print_subheader("Record Bill Payment")
    try:
        bill_id_input = input("Enter Bill ID: ").strip()
        if not bill_id_input:
            print_warning("Payment cancelled.")
            pause()
            return

        bill = get_bill_by_id(conn, bill_id_input)
        if not bill:
            print_error(f"Bill with ID '{bill_id_input}' was not found.")
            pause()
            return

        cur_balance = Decimal(str(bill["balance"]))
        if cur_balance <= Decimal("0.00"):
            print_warning(f"Bill {bill['bill_id']} is already PAID IN FULL. No payment needed.")
            pause()
            return

        # Show current billing status
        print_info(f"Bill: {bill['bill_id']} | Patient: {bill['patient_name']}")
        print(f"  Total Amount:        {CURRENCY_SYMBOL}{Decimal(str(bill['total_amount'])):.2f}")
        print(f"  Already Paid:        {CURRENCY_SYMBOL}{Decimal(str(bill['paid_amount'])):.2f}")
        print(f"  Outstanding Balance: {CURRENCY_SYMBOL}{cur_balance:.2f}")

        # Get payment amount from user
        while True:
            amt_input = input(f"\nEnter payment amount (Max: {CURRENCY_SYMBOL}{cur_balance:.2f}): ").strip()
            if not amt_input:
                print_warning("Payment cancelled.")
                pause()
                return

            valid, pay_amount, err = validate_decimal_amount(
                amt_input, min_val=Decimal("0.01"), max_val=cur_balance, field_name="Payment amount"
            )
            if valid and pay_amount is not None:
                break
            print_error(err)

        # Show Philippine payment channels (Cash, GCash, Maya, etc.)
        print("\nSelect Payment Method (PH Channels Available):")
        for idx, method in enumerate(VALID_PAYMENT_METHODS, 1):
            print(f"  {idx}. {method}")

        method_choice = input(f"Enter choice (1-{len(VALID_PAYMENT_METHODS)}): ").strip()
        valid_m, m_idx, _ = validate_menu_choice(method_choice, 1, len(VALID_PAYMENT_METHODS))
        if not valid_m or m_idx is None:
            print_error("Invalid payment method.")
            pause()
            return
        payment_method = VALID_PAYMENT_METHODS[m_idx - 1]

        notes = input("Enter optional transaction notes / reference number: ").strip()

        # Confirm before saving payment
        if confirm_action(f"\nConfirm recording payment of {CURRENCY_SYMBOL}{pay_amount:.2f} via {payment_method}?", default_no=False):
            success, msg, pay_id = record_payment(conn, bill["bill_id"], pay_amount, payment_method, notes)
            if success:
                print_success(f"{msg} (Payment ID: {pay_id})")
            else:
                print_error(msg)
        else:
            print_info("Payment cancelled.")

    except (KeyboardInterrupt, EOFError):
        print("\nPayment cancelled by user.")
    pause()


def handle_view_all_bills(conn: sqlite3.Connection) -> None:
    """Show all hospital bills in a table."""
    print_subheader("All Hospital Bills")
    bills = get_all_bills(conn)

    headers = ["Bill ID", "Patient ID", "Patient Name", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["patient_id"],
            b["patient_name"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message="No bills found in the database.")
    pause()


def handle_view_outstanding_bills(conn: sqlite3.Connection) -> None:
    """Show only bills that still have an unpaid balance."""
    print_subheader("Outstanding Hospital Bills")
    bills = get_outstanding_bills(conn)

    headers = ["Bill ID", "Patient ID", "Patient Name", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["patient_id"],
            b["patient_name"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message="No outstanding bills! All invoices are fully paid.")
    pause()


def handle_view_bill_details(conn: sqlite3.Connection) -> None:
    """Print a complete printable-style invoice with itemized services and payments."""
    print_subheader("Bill Invoice Details")
    bill_id_input = input("Enter Bill ID: ").strip()
    if not bill_id_input:
        print_error("Bill ID is required.")
        pause()
        return

    bill = get_bill_by_id(conn, bill_id_input)
    if not bill:
        print_error(f"Bill with ID '{bill_id_input}' not found.")
        pause()
        return

    items = get_bill_items(conn, bill["bill_id"])
    payments = get_payments_by_bill(conn, bill["bill_id"])

    print()
    print("=" * 70)
    print(f"  HOSPITAL INVOICE: {bill['bill_id']}")
    print("=" * 70)
    print(f"  Patient:             {bill['patient_name']} ({bill['patient_id']})")
    print(f"  Contact:             {bill['contact_number']}")
    print(f"  Invoice Date:        {bill['bill_date']}")
    print(f"  Status:              {bill['status']}")
    print("-" * 70)
    print("  ITEMIZED SERVICES:")
    for idx, item in enumerate(items, 1):
        amt = Decimal(str(item["amount"]))
        print(f"    {idx}. {item['service_description'].ljust(45)} {CURRENCY_SYMBOL}{amt:>9.2f}")
    print("-" * 70)
    print(f"  TOTAL AMOUNT:        {CURRENCY_SYMBOL}{Decimal(str(bill['total_amount'])):.2f}")
    print(f"  PAID AMOUNT:         {CURRENCY_SYMBOL}{Decimal(str(bill['paid_amount'])):.2f}")
    print(f"  OUTSTANDING BALANCE: {CURRENCY_SYMBOL}{Decimal(str(bill['balance'])):.2f}")
    print("-" * 70)

    # Show transaction history if any payments exist
    if payments:
        print("  PAYMENT TRANSACTIONS:")
        for p in payments:
            amt = Decimal(str(p["amount"]))
            note_str = f" ({p['notes']})" if p['notes'] else ""
            print(f"    * {p['payment_date']} | {p['payment_id']} | {p['payment_method']} | {CURRENCY_SYMBOL}{amt:.2f}{note_str}")
    else:
        print("  No payments recorded for this bill.")
    print("=" * 70)
    pause()


def handle_view_patient_billing(conn: sqlite3.Connection) -> None:
    """Show all bills belonging to one specific patient."""
    from modules.patients import get_patient_by_id

    print_subheader("Patient Billing History")
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

    bills = get_bills_by_patient(conn, patient["patient_id"])
    print_info(f"Billing records for: {patient['full_name']} ({patient['patient_id']})")

    headers = ["Bill ID", "Date", f"Total ({CURRENCY_CODE})", f"Paid ({CURRENCY_CODE})", f"Balance ({CURRENCY_CODE})", "Status"]
    alignments = ["left", "left", "right", "right", "right", "left"]
    rows = [
        [
            b["bill_id"],
            b["bill_date"],
            f"{Decimal(str(b['total_amount'])):.2f}",
            f"{Decimal(str(b['paid_amount'])):.2f}",
            f"{Decimal(str(b['balance'])):.2f}",
            b["status"]
        ]
        for b in bills
    ]
    print_table(headers, rows, alignments=alignments, empty_message=f"No bills on record for {patient['patient_id']}.")
    pause()


def billing_menu(conn: sqlite3.Connection) -> None:
    """Submenu for handling bills and payments."""
    while True:
        print_subheader("Billing & Payment Menu")
        print("  1. Generate New Hospital Bill")
        print("  2. Record Payment for Bill")
        print("  3. View All Bills")
        print("  4. View Outstanding Bills")
        print("  5. View Bill Invoice Details")
        print("  6. View Patient Billing History")
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
            handle_generate_bill(conn)
        elif choice_num == 2:
            handle_record_payment(conn)
        elif choice_num == 3:
            handle_view_all_bills(conn)
        elif choice_num == 4:
            handle_view_outstanding_bills(conn)
        elif choice_num == 5:
            handle_view_bill_details(conn)
        elif choice_num == 6:
            handle_view_patient_billing(conn)
        elif choice_num == 7:
            break
