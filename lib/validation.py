from __future__ import annotations

import re

EMAIL_PLACEHOLDER = "name@example.com"
MOBILE_PLACEHOLDER = "9876543210"
MOBILE_HELP = "10-digit mobile starting with 6, 7, 8, or 9. +91 is optional."

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)+$"
)


def validate_email_address(
    value: str | None,
    *,
    required: bool = False,
    label: str = "Email",
) -> str | None:
    """Return an error when an email is missing or not a normal address."""
    text = (value or "").strip()
    if not text:
        return f"{label} is required." if required else None
    if len(text) > 254 or not _EMAIL_RE.fullmatch(text):
        return f"Enter a valid {label.lower()} address (example: name@example.com)."
    return None


def validate_mobile_number(
    value: str | None,
    *,
    required: bool = False,
    label: str = "Mobile number",
) -> str | None:
    """Return an error unless the value is a 10-digit Indian mobile, with optional +91."""
    text = (value or "").strip()
    if not text:
        return f"{label} is required." if required else None
    if re.search(r"[A-Za-z]", text):
        return f"{label} must be digits only, with an optional +91 prefix."
    digits = re.sub(r"\D", "", text)
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "6789":
        return None
    return (
        f"{label} must be a 10-digit mobile number starting with 6, 7, 8, or 9. "
        "You can prefix it with +91."
    )


def contact_field_errors(
    *,
    email: str | None = None,
    email_required: bool = False,
    email_label: str = "Email",
    phone: str | None = None,
    phone_required: bool = False,
    phone_label: str = "Phone",
    whatsapp: str | None = None,
    whatsapp_required: bool = False,
    whatsapp_label: str = "WhatsApp number",
) -> list[str]:
    """Format checks for the email, phone, and WhatsApp fields on a form."""
    errors: list[str] = []
    email_error = validate_email_address(
        email, required=email_required, label=email_label
    )
    if email_error:
        errors.append(email_error)
    phone_error = validate_mobile_number(
        phone, required=phone_required, label=phone_label
    )
    if phone_error:
        errors.append(phone_error)
    whatsapp_error = validate_mobile_number(
        whatsapp, required=whatsapp_required, label=whatsapp_label
    )
    if whatsapp_error:
        errors.append(whatsapp_error)
    return errors


def validate_password(password: str) -> str | None:
    """Return an error message if password is invalid, else None."""
    if len(password) < 7:
        return "Password must be at least 7 characters."
    if not re.search(r"[a-zA-Z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    return None
