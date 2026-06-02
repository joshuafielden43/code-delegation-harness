#!/usr/bin/env python3
"""
This is a completely disposable file created purely for safe first tests
of the grok-coding-delegate skill.

Feel free to have Grok make changes here. Nothing in this file is used
by any real system. It exists only so you can exercise the full modern
output artifacts (structured JSON + .report.md + .patch) with zero risk.
"""

from typing import Any, Optional


def calculate_total(items: list[dict[str, Any]], tax_rate: float = 0.0) -> float:
    """Calculate the total price of items with optional tax.

    Computes subtotal as the sum of (price * quantity) for each item (quantity
    defaults to 1), then returns subtotal + (subtotal * tax_rate).

    Args:
        items (list[dict[str, Any]]): List of item dicts. Each must contain
            a numeric 'price' key and may contain an integer 'quantity' key.
        tax_rate (float): Tax rate as a decimal (e.g. 0.08 for 8%). Defaults
            to 0.0.

    Returns:
        float: The final total price including tax.
    """
    subtotal = sum(item['price'] * item.get('quantity', 1) for item in items)
    tax = subtotal * tax_rate
    return subtotal + tax


def format_user_name(first: str, last: str, middle: Optional[str] = None) -> str:
    """Format a full name from first, last, and optional middle name parts.

    Args:
        first (str): First name.
        last (str): Last name.
        middle (Optional[str]): Middle name, if any. Defaults to None.

    Returns:
        str: Formatted name as "first last" or "first middle last" when middle
            is provided.
    """
    if middle:
        return f"{first} {middle} {last}"
    return f"{first} {last}"


def is_valid_email(email: str) -> bool:
    """Check whether an email address appears valid using a minimal heuristic.

    Requires the presence of '@' and at least one '.' in the domain portion
    (after the last '@').

    Args:
        email (str): The email address to check.

    Returns:
        bool: True if '@' is present and the suffix after the final '@'
            contains a '.', otherwise False.
    """
    return "@" in email and "." in email.split("@")[-1]