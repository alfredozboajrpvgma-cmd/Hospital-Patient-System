"""
Main Program

Hospital Patient Management System (CLI) - Philippine Edition.
Shows the main numbered menu, sets up the database, and routes
the user to each module.
"""

import sys
import sqlite3

# Ensure Windows terminal outputs UTF-8 properly for the Philippine Peso symbol (₱)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from database import init_db, get_connection
from utils.display import (
    print_header,
    print_error,
    print_info,
    confirm_action,
    pause
)
from utils.validators import validate_menu_choice

from modules.patients import patient_menu
from modules.appointments import appointment_menu
from modules.visits import visit_menu
from modules.billing import billing_menu
from modules.reports import reports_menu


def display_main_menu() -> None:
    """Print the main menu options on the terminal screen."""
    print("=======================================================================")
    print("           PHILIPPINE HOSPITAL PATIENT MANAGEMENT SYSTEM (CLI)        ")
    print("=======================================================================")
    print("  1. Patient Management")
    print("  2. Appointment Management")
    print("  3. Visit Records")
    print("  4. Billing and Payments")
    print("  5. Reports")
    print("  6. Exit")
    print("=======================================================================")


def main() -> None:
    """Set up the database and run the main program loop."""
    try:
        # Create tables if they do not exist yet, then open connection
        init_db()
        conn = get_connection()
    except sqlite3.Error as exc:
        print_error(f"Failed to initialize hospital database: {exc}")
        sys.exit(1)

    print_header("Welcome to Philippine Hospital Patient System (CLI)")
    print_info("Philippine Hospital Database initialized and ready (Currency: PHP / ₱).")

    try:
        # Main program loop
        while True:
            display_main_menu()
            try:
                choice = input("Enter your choice (1-6): ")
            except (KeyboardInterrupt, EOFError):
                print()
                if confirm_action("\nDo you wish to exit the Hospital System?", default_no=False):
                    break
                else:
                    continue

            valid, choice_num, err_msg = validate_menu_choice(choice, 1, 6)
            if not valid or choice_num is None:
                print_error(err_msg)
                pause()
                continue

            # Route user choice to the right module submenu
            if choice_num == 1:
                patient_menu(conn)
            elif choice_num == 2:
                appointment_menu(conn)
            elif choice_num == 3:
                visit_menu(conn)
            elif choice_num == 4:
                billing_menu(conn)
            elif choice_num == 5:
                reports_menu(conn)
            elif choice_num == 6:
                if confirm_action("Are you sure you want to exit the application?", default_no=False):
                    print_info("Thank you for using the Hospital Patient Management System. Goodbye!")
                    break
    finally:
        # Always close database connection when exiting
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
