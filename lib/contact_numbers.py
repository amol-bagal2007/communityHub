from __future__ import annotations

import re

from lib.supabase_client import SchemaClient

DUPLICATE_CONTACT_MSG = (
    "This phone or WhatsApp number already exists. Please use a different number."
)


def normalize_contact_digits(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def duplicate_contact_message(
    client: SchemaClient,
    numbers: list[str | None],
    *,
    exclude_vendor_id: str | None = None,
    exclude_business_id: str | None = None,
    exclude_profile_id: str | None = None,
) -> str | None:
    """Return an error if a phone/WhatsApp is already used by a profile, vendor, or business."""
    seen: list[str] = []
    for raw in numbers:
        digits = normalize_contact_digits(raw)
        if digits and digits not in seen:
            seen.append(digits)
    if not seen:
        return None

    for digits in seen:
        try:
            taken = (
                client.raw.rpc(
                    "contact_number_exists",
                    {
                        "p_number": digits,
                        "p_exclude_vendor": exclude_vendor_id,
                        "p_exclude_business": exclude_business_id,
                        "p_exclude_profile": exclude_profile_id,
                    },
                )
                .execute()
                .data
            )
            if taken is True or taken == [True]:
                return DUPLICATE_CONTACT_MSG
        except Exception:
            if _visible_duplicate(
                client,
                digits,
                exclude_vendor_id=exclude_vendor_id,
                exclude_business_id=exclude_business_id,
                exclude_profile_id=exclude_profile_id,
            ):
                return DUPLICATE_CONTACT_MSG
    return None


def message_if_duplicate_db_error(exc: Exception) -> str | None:
    text = str(exc)
    if "already exists" in text.lower() and ("phone" in text.lower() or "whatsapp" in text.lower()):
        return DUPLICATE_CONTACT_MSG
    return None


def _visible_duplicate(
    client: SchemaClient,
    digits: str,
    *,
    exclude_vendor_id: str | None,
    exclude_business_id: str | None,
    exclude_profile_id: str | None = None,
) -> bool:
    try:
        vendors = (
            client.table("vendors")
            .select("id, contact_phone, personal_whatsapp")
            .execute()
            .data
            or []
        )
        for row in vendors:
            if exclude_vendor_id and row.get("id") == exclude_vendor_id:
                continue
            if digits in {
                normalize_contact_digits(row.get("contact_phone")),
                normalize_contact_digits(row.get("personal_whatsapp")),
            }:
                return True
    except Exception:
        pass
    try:
        businesses = (
            client.table("local_businesses")
            .select("id, phone, whatsapp_number")
            .execute()
            .data
            or []
        )
        for row in businesses:
            if exclude_business_id and row.get("id") == exclude_business_id:
                continue
            if digits in {
                normalize_contact_digits(row.get("phone")),
                normalize_contact_digits(row.get("whatsapp_number")),
            }:
                return True
    except Exception:
        pass
    try:
        profiles = (
            client.table("profiles")
            .select("id, phone, personal_whatsapp")
            .execute()
            .data
            or []
        )
        for row in profiles:
            if exclude_profile_id and row.get("id") == exclude_profile_id:
                continue
            if digits in {
                normalize_contact_digits(row.get("phone")),
                normalize_contact_digits(row.get("personal_whatsapp")),
            }:
                return True
    except Exception:
        pass
    return False
