"""Helper utilities for the Python app."""

def format_currency(amount: float) -> str:
    """
    Format a number as currency.

    Args:
        amount: The amount to format

    Returns:
        Formatted currency string
    """
    return f"${amount:,.2f}"


def validate_email(email: str) -> bool:
    """
    Simple email validation.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    import re
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))


def calculate_percentage(part: float, whole: float) -> float:
    """
    Calculate percentage.

    Args:
        part: The part value
        whole: The whole value

    Returns:
        Percentage value
    """
    if whole == 0:
        return 0.0
    return (part / whole) * 100
