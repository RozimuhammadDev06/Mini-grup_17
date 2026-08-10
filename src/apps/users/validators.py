"""
Password strength rules, defined once.

The project shipped these rules copy-pasted into three views with slightly
different wording; registration, password reset and password change now all
call :func:`validate_password_strength`.
"""

from __future__ import annotations

from django.contrib.auth.password_validation import \
    validate_password as django_validate_password
from django.core.exceptions import ValidationError

SYMBOLS = set("!@#$%^&*()?,._-=[]\"':;{}<>/\\|+~`")

MIN_LENGTH = 8
MAX_LENGTH = 128


def validate_password_strength(password: str, user=None) -> str:
    """Run Django's validators, then the project's composition rules."""
    errors: list[str] = []

    if password is None or len(password) < MIN_LENGTH:
        errors.append(
            f"Password must be at least {MIN_LENGTH} characters long.")
    elif len(password) > MAX_LENGTH:
        errors.append(
            f"Password must be at most {MAX_LENGTH} characters long.")
    else:
        if not any(c.isupper() for c in password):
            errors.append("Password must contain an uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain a lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain a digit.")
        if not any(c in SYMBOLS for c in password):
            errors.append("Password must contain a special character.")

    try:
        django_validate_password(password, user=user)
    except ValidationError as exc:
        errors.extend(exc.messages)

    if errors:
        raise ValidationError(errors)
    return password
