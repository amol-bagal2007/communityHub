from __future__ import annotations

from datetime import date
from typing import Any

from lib.profile_extended_fields import validate_extended_profile_fields
from lib.roles import ROLE_TENANT, is_owner
from lib.titles import is_valid_title
from lib.user_demographics import normalize_age, sex_age_validation_errors

EXTENDED_KEYS = (
    "parking_number",
    "parking_floor",
    "parking_share_mode",
    "parking_availability_value",
    "parking_availability_unit",
    "parking_charges",
    "bio",
    "group_interests",
)


def collect_profile_update_errors(
    *,
    title: str,
    first_name: str,
    last_name: str,
    sex: str,
    age: int | float | str | None,
    role: str,
    flat_number: str,
    staying_within_society: bool,
    tenant_expiry: date | None,
    society_id: str | None,
    tower_id: str | None,
    email: str,
    extended_fields: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not is_valid_title(title):
        errors.append("Please select a title.")
    if not first_name.strip():
        errors.append("First name is required.")
    if not last_name.strip():
        errors.append("Last name is required.")
    errors.extend(sex_age_validation_errors(sex, age))
    if not email.strip():
        errors.append("Email is required.")
    if not flat_number.strip():
        errors.append("Flat / unit number is required.")
    if not society_id:
        errors.append("Please select a society.")
    if not tower_id:
        errors.append("Please select a tower.")
    if is_owner(role) and not staying_within_society:
        errors.append("Owners must confirm that they are staying within the society.")
    if role == ROLE_TENANT and not tenant_expiry:
        errors.append("Tenant expiry date is required.")
    if extended_fields:
        errors.extend(validate_extended_profile_fields(extended_fields))
    return errors


def build_profile_update_payload(
    *,
    title: str,
    first_name: str,
    last_name: str,
    sex: str,
    age: int | float | str | None,
    phone: str,
    email: str,
    member_group_id: str | None,
    member_sub_group_id: str | None,
    role: str,
    society_id: str,
    tower_id: str,
    flat_number: str,
    staying_within_society: bool,
    tenant_expiry: date | None,
    for_reapproval: bool,
    personal_whatsapp: str = "",
    extended_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_age = normalize_age(age)
    payload: dict[str, Any] = {
        "title": title,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "sex": sex,
        "age": normalized_age,
        "phone": phone.strip() or None,
        "personal_whatsapp": (personal_whatsapp or "").strip() or None,
        "email": email.strip(),
        "member_group_id": member_group_id,
        "member_sub_group_id": member_sub_group_id,
        "role": role,
        "society_id": society_id,
        "tower_id": tower_id,
        "flat_number": flat_number.strip(),
        "staying_within_society": staying_within_society if is_owner(role) else False,
        "tenant_expiry_date": tenant_expiry.isoformat() if role == ROLE_TENANT and tenant_expiry else None,
    }
    if extended_fields:
        payload.update(extended_fields)
    if for_reapproval:
        payload["status"] = "pending"
    return payload


def profile_has_changes(profile: dict, payload: dict[str, Any]) -> bool:
    comparable = {
        "title": payload.get("title"),
        "first_name": payload.get("first_name"),
        "last_name": payload.get("last_name"),
        "sex": payload.get("sex"),
        "age": payload.get("age"),
        "phone": payload.get("phone"),
        "personal_whatsapp": payload.get("personal_whatsapp"),
        "email": payload.get("email"),
        "member_group_id": payload.get("member_group_id"),
        "member_sub_group_id": payload.get("member_sub_group_id"),
        "role": payload.get("role"),
        "society_id": payload.get("society_id"),
        "tower_id": payload.get("tower_id"),
        "flat_number": payload.get("flat_number"),
        "staying_within_society": payload.get("staying_within_society"),
        "tenant_expiry_date": payload.get("tenant_expiry_date"),
    }
    for key in EXTENDED_KEYS:
        comparable[key] = payload.get(key)

    for key, new_value in comparable.items():
        old_value = profile.get(key)
        if key == "tenant_expiry_date":
            old_str = str(old_value)[:10] if old_value else None
            new_str = str(new_value)[:10] if new_value else None
            if old_str != new_str:
                return True
            continue
        if key == "parking_charges":
            try:
                old_num = float(old_value) if old_value is not None else None
                new_num = float(new_value) if new_value is not None else None
                if old_num != new_num:
                    return True
            except (TypeError, ValueError):
                if old_value != new_value:
                    return True
            continue
        if old_value != new_value:
            return True
    return False
