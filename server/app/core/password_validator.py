"""
Password Complexity Validator — shared by forgot-password and change-password flows.

Rules:
  - Minimum 8 characters
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one digit (0-9)
  - At least one special character

Usage:
    violations = validate_password_complexity(new_password)
    if violations:
        raise HTTPException(422, detail={"violations": violations})
"""

import re
import string

_SPECIAL_CHARS = set(r"!@#$%^&*()_+-=[]{}|;:'\",.<>/?`~\\")


def validate_password_complexity(password: str) -> list[str]:
    """
    Validate password against complexity rules.

    Returns a list of unmet rule descriptions.
    An empty list means the password is valid.
    """
    violations: list[str] = []

    if len(password) < 8:
        violations.append("Minimum 8 characters")

    if not re.search(r"[A-Z]", password):
        violations.append("At least one uppercase letter (A-Z)")

    if not re.search(r"[a-z]", password):
        violations.append("At least one lowercase letter (a-z)")

    if not re.search(r"\d", password):
        violations.append("At least one digit (0-9)")

    if not any(c in _SPECIAL_CHARS for c in password):
        violations.append("At least one special character (!@#$%^&*...)")

    return violations
