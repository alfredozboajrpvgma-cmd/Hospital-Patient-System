"""
Settings and constants for the Hospital Patient System.
We keep these in one place so we don't have to hardcode names, paths, or options in other files.
"""

import sys
import os
from pathlib import Path

# Main project folder (supports both normal python run and compiled .exe)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Where the SQLite database file is stored
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "hospital.db"

# Currency settings for the Philippines
CURRENCY_SYMBOL = "₱"
CURRENCY_CODE = "PHP"

# Standard date and time formats
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
TIME_FORMAT = "%H:%M"

# Hospital departments available for appointments and visits
DEPARTMENTS = [
    "Outpatient Department (OPD)",
    "Emergency Room (ER)",
    "Internal Medicine",
    "Pediatrics",
    "Obstetrics and Gynecology (OB-GYN)",
    "Surgery",
    "Cardiology",
    "Orthopedics",
    "Radiology",
    "Laboratory & Diagnostics"
]

# Allowed patient inputs
VALID_SEX_OPTIONS = ["Male", "Female", "Other"]
VALID_PATIENT_STATUS = ["Active", "Archived"]

# Allowed appointment statuses
VALID_APPOINTMENT_STATUS = ["Scheduled", "Completed", "Cancelled", "Rescheduled"]

# Allowed billing statuses and common Philippine payment options
VALID_BILL_STATUS = ["Unpaid", "Partially Paid", "Paid"]
VALID_PAYMENT_METHODS = [
    "Cash",
    "PhilHealth",
    "HMO / Health Card",
    "GCash",
    "Maya",
    "Credit Card",
    "Debit Card",
    "Bank Transfer"
]
