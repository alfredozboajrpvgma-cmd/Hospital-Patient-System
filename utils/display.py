"""
Helpers for terminal output and formatting.
Prints banners, status alerts, yes/no confirmations, and clean ASCII tables.
"""

from typing import List, Any, Optional


def print_header(title: str, width: int = 75) -> None:
    """Print a main section title with double borders."""
    print()
    print("=" * width)
    print(f"  {title.upper()}")
    print("=" * width)


def print_subheader(title: str, width: int = 75) -> None:
    """Print a section divider with single borders."""
    print()
    print("-" * width)
    print(f"  [ {title.upper()} ]")
    print("-" * width)


def print_success(message: str) -> None:
    """Print a success status message."""
    print(f"[SUCCESS] {message}")


def print_error(message: str) -> None:
    """Print an error status message."""
    print(f"[ERROR] {message}")


def print_warning(message: str) -> None:
    """Print a warning status message."""
    print(f"[WARNING] {message}")


def print_info(message: str) -> None:
    """Print an informational note."""
    print(f"[INFO] {message}")


def print_table(
    headers: List[str],
    rows: List[List[Any]],
    alignments: Optional[List[str]] = None,
    empty_message: str = "No records found."
) -> None:
    """
    Print records inside a clean bordered table.
    Calculates column widths automatically so text lines up neatly.
    """
    if not rows:
        print()
        print(f"  ({empty_message})")
        print()
        return

    num_cols = len(headers)
    str_rows = [[str(cell if cell is not None else "") for cell in row] for row in rows]

    # Find the widest item in each column so we know how much space to give
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for idx in range(min(num_cols, len(row))):
            col_widths[idx] = max(col_widths[idx], len(row[idx]))

    # Default to left-align if no alignments were specified
    if not alignments:
        alignments = ["left"] * num_cols

    # Build the horizontal line (+---+---+)
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    print()
    print(separator)

    # Print the column headers
    header_cells = []
    for idx, (header, width) in enumerate(zip(headers, col_widths)):
        align = alignments[idx]
        if align == "right":
            header_cells.append(f" {header.rjust(width)} ")
        elif align == "center":
            header_cells.append(f" {header.center(width)} ")
        else:
            header_cells.append(f" {header.ljust(width)} ")
    print("|" + "|".join(header_cells) + "|")
    print(separator)

    # Print each row of data
    for row in str_rows:
        row_cells = []
        for idx in range(num_cols):
            val = row[idx] if idx < len(row) else ""
            width = col_widths[idx]
            align = alignments[idx] if idx < len(alignments) else "left"

            if align == "right":
                row_cells.append(f" {val.rjust(width)} ")
            elif align == "center":
                row_cells.append(f" {val.center(width)} ")
            else:
                row_cells.append(f" {val.ljust(width)} ")
        print("|" + "|".join(row_cells) + "|")

    print(separator)
    print(f"  Total records: {len(rows)}")
    print()


def confirm_action(prompt: str = "Are you sure you want to proceed?", default_no: bool = True) -> bool:
    """
    Ask the user to confirm with y or n before performing sensitive actions.
    Returns True if confirmed, or False if cancelled.
    """
    options = "[y/N]" if default_no else "[Y/n]"
    while True:
        try:
            choice = input(f"{prompt} {options}: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return False

        if not choice:
            return not default_no
        if choice in ("y", "yes"):
            return True
        if choice in ("n", "no"):
            return False

        print("Please enter 'y' for Yes or 'n' for No.")


def pause(message: str = "\nPress Enter to continue...") -> None:
    """Pause execution until the user presses Enter so they have time to read."""
    try:
        input(message)
    except (KeyboardInterrupt, EOFError):
        print()
