"""
Validation functions for user input.
We check inputs here before sending them to the database so bad data does not crash the program.
"""

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from typing import Tuple, Optional
from config import DATE_FORMAT, TIME_FORMAT, VALID_SEX_OPTIONS


def validate_non_empty(
    text: str, field_name: str = "Field", min_length: int = 1, max_length: int = 255
) -> Tuple[bool, str]:
    """Make sure text is not blank and within character limits."""
    if not text or not text.strip():
        return False, f"{field_name} cannot be empty."
    
    cleaned = text.strip()
    if len(cleaned) < min_length:
        return False, f"{field_name} must be at least {min_length} characters."
    if len(cleaned) > max_length:
        return False, f"{field_name} must not exceed {max_length} characters."
    
    return True, cleaned


def validate_date(
    date_str: str,
    allow_future: bool = True,
    allow_past: bool = True,
    field_name: str = "Date"
) -> Tuple[bool, str]:
    """
    Check if a date is in YYYY-MM-DD format and is a real calendar date.
    Also checks whether future or past dates are allowed for this specific field.
    """
    if not date_str or not date_str.strip():
        return False, f"{field_name} cannot be empty."

    cleaned = date_str.strip()
    try:
        # strptime checks leap years and invalid days like Feb 30
        parsed_date = datetime.strptime(cleaned, DATE_FORMAT).date()
    except ValueError:
        return False, f"Invalid {field_name} format. Expected YYYY-MM-DD (e.g., 2024-05-18)."

    today = date.today()
    if not allow_future and parsed_date > today:
        return False, f"{field_name} cannot be a future date."
    if not allow_past and parsed_date < today:
        return False, f"{field_name} cannot be in the past."

    return True, parsed_date.strftime(DATE_FORMAT)


def validate_time(time_str: str, field_name: str = "Time") -> Tuple[bool, str]:
    """Check if time is valid in 24-hour HH:MM format."""
    if not time_str or not time_str.strip():
        return False, f"{field_name} cannot be empty."

    cleaned = time_str.strip()
    try:
        parsed_time = datetime.strptime(cleaned, TIME_FORMAT).time()
        return True, parsed_time.strftime(TIME_FORMAT)
    except ValueError:
        return False, f"Invalid {field_name} format. Expected HH:MM in 24-hour format (e.g., 09:30 or 14:15)."


def validate_phone(phone_str: str, field_name: str = "Contact number") -> Tuple[bool, str]:
    """
    Check if the phone number is valid.
    Accepts Philippine mobile formats (09xx, +639xx), landlines, and international numbers.
    """
    if not phone_str or not phone_str.strip():
        return False, f"{field_name} cannot be empty."

    cleaned = phone_str.strip()
    # Allow numbers with spaces, dashes, or parentheses
    if not re.match(r"^(\+)?[0-9\s\-()]{7,25}$", cleaned):
        return False, f"Invalid {field_name}. Use a valid PH format (e.g., 09171234567, +639171234567, or (02) 8123-4567)."

    # Count actual digits to make sure it's not too short or too long
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False, f"{field_name} must contain between 7 and 15 digits."

    return True, cleaned


def validate_sex(sex_str: str) -> Tuple[bool, str]:
    """Convert user input into Male, Female, or Other."""
    if not sex_str or not sex_str.strip():
        return False, "Sex cannot be empty. Please select Male, Female, or Other."

    cleaned = sex_str.strip().lower()
    # Map common shortcuts to the standard value
    mapping = {
        "1": "Male",
        "m": "Male",
        "male": "Male",
        "2": "Female",
        "f": "Female",
        "female": "Female",
        "3": "Other",
        "o": "Other",
        "other": "Other"
    }

    if cleaned in mapping:
        return True, mapping[cleaned]

    return False, "Invalid selection. Please choose Male, Female, or Other."


def validate_decimal_amount(
    amount_str: str,
    min_val: Decimal = Decimal("0.01"),
    max_val: Decimal = Decimal("10000000.00"),
    field_name: str = "Amount"
) -> Tuple[bool, Optional[Decimal], str]:
    """
    Safely turn a money string into a Python Decimal.
    Supports Philippine Peso symbols ('₱', 'PHP', 'P') and standard numbers.
    """
    if not amount_str or not amount_str.strip():
        return False, None, f"{field_name} cannot be empty."

    # Strip currency symbols and commas so Decimal can parse it
    cleaned = (
        amount_str.strip()
        .replace("₱", "")
        .replace("PHP", "")
        .replace("Php", "")
        .replace("php", "")
        .replace("$", "")
        .replace(",", "")
        .strip()
    )
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return False, None, f"Invalid {field_name}. Please enter a valid number (e.g., 500.00 or 1250.50)."

    # Reject more than 2 decimal places (like 12.345)
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        return False, None, f"{field_name} cannot have more than 2 decimal places."

    if amount < min_val:
        return False, None, f"{field_name} must be at least {min_val:.2f}."
    if amount > max_val:
        return False, None, f"{field_name} cannot exceed {max_val:.2f}."

    # Round to standard 2 decimal places
    amount = amount.quantize(Decimal("0.01"))
    return True, amount, f"{amount:.2f}"


def validate_menu_choice(choice_str: str, min_choice: int, max_choice: int) -> Tuple[bool, Optional[int], str]:
    """Check if the user picked a valid number from the menu options."""
    if not choice_str or not choice_str.strip():
        return False, None, "Input cannot be empty. Please enter a valid menu number."

    cleaned = choice_str.strip()
    if not cleaned.isdigit():
        return False, None, f"Invalid input '{cleaned}'. Please enter a number between {min_choice} and {max_choice}."

    val = int(cleaned)
    if val < min_choice or val > max_choice:
        return False, None, f"Choice must be between {min_choice} and {max_choice}."

    return True, val, ""
