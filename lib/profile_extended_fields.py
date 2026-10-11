from __future__ import annotations

from typing import Any

import streamlit as st

from lib.interest_groups import (
    decode_group_interest_ids,
    encode_group_interest_ids,
    load_interest_groups,
)
from lib.supabase_client import SchemaClient

TEXT_LIMIT = 5000

PARKING_SHARE_NOT_AVAILABLE = "not_available"
PARKING_SHARE_FREE = "free"
PARKING_SHARE_PAID = "paid"

PARKING_SHARE_OPTIONS = [
    PARKING_SHARE_NOT_AVAILABLE,
    PARKING_SHARE_FREE,
    PARKING_SHARE_PAID,
]

PARKING_SHARE_LABELS = {
    PARKING_SHARE_NOT_AVAILABLE: "Not available to others",
    PARKING_SHARE_FREE: "Available to others — Free",
    PARKING_SHARE_PAID: "Available to others — Charges apply",
}

PARKING_UNITS = ["hours", "days", "months", "years"]
PARKING_UNIT_LABELS = {
    "hours": "Hours",
    "days": "Days",
    "months": "Months",
    "years": "Years",
}


def parking_share_label(value: str | None) -> str:
    return PARKING_SHARE_LABELS.get(value or "", "—")


def clip_text(value: str | None, limit: int = TEXT_LIMIT) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return text[:limit]


def validate_extended_profile_fields(
    data: dict[str, Any],
    *,
    valid_interest_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    bio = data.get("bio") or ""
    interests = data.get("group_interests") or ""
    if len(bio) > TEXT_LIMIT:
        errors.append(f"Bio must be at most {TEXT_LIMIT} characters.")
    if len(interests) > TEXT_LIMIT:
        errors.append(f"Interested in groups selection is too large.")

    selected_ids = decode_group_interest_ids(interests)
    if valid_interest_ids is not None:
        invalid = [i for i in selected_ids if i not in valid_interest_ids]
        if invalid:
            errors.append("One or more selected interest groups are no longer available.")

    share = data.get("parking_share_mode")
    if share and share not in PARKING_SHARE_OPTIONS:
        errors.append("Select a valid parking availability option.")

    unit = data.get("parking_availability_unit")
    duration = data.get("parking_availability_value")
    if unit and unit not in PARKING_UNITS:
        errors.append("Select a valid parking availability period.")
    if duration is not None and duration != "" and int(duration) < 1:
        errors.append("Parking availability duration must be at least 1.")

    charges = data.get("parking_charges")
    if share == PARKING_SHARE_PAID:
        if charges is None or charges == "":
            errors.append("Enter applicable parking charges when parking is paid.")
        else:
            try:
                if float(charges) < 0:
                    errors.append("Parking charges cannot be negative.")
            except (TypeError, ValueError):
                errors.append("Parking charges must be a number.")
    return errors


def normalize_extended_profile_fields(data: dict[str, Any]) -> dict[str, Any]:
    share = data.get("parking_share_mode") or None
    if share == "":
        share = None

    duration = data.get("parking_availability_value")
    if duration in ("", None):
        duration_val = None
    else:
        duration_val = int(duration)

    unit = data.get("parking_availability_unit") or None
    if unit == "":
        unit = None

    charges = data.get("parking_charges")
    if share != PARKING_SHARE_PAID or charges in ("", None):
        charges_val = None
    else:
        charges_val = float(charges)

    if share in (None, PARKING_SHARE_NOT_AVAILABLE):
        # Keep number/floor; clear share-related availability if not sharing.
        if share == PARKING_SHARE_NOT_AVAILABLE:
            duration_val = None
            unit = None
            charges_val = None

    interest_ids = data.get("group_interest_ids")
    if interest_ids is None:
        group_interests = clip_text(data.get("group_interests"))
    else:
        group_interests = encode_group_interest_ids(list(interest_ids or []))

    return {
        "parking_number": (data.get("parking_number") or "").strip() or None,
        "parking_floor": (data.get("parking_floor") or "").strip() or None,
        "parking_share_mode": share,
        "parking_availability_value": duration_val,
        "parking_availability_unit": unit,
        "parking_charges": charges_val,
        "bio": clip_text(data.get("bio")),
        "group_interests": group_interests,
    }


def render_extended_profile_fields(
    client: SchemaClient,
    *,
    key_prefix: str,
    current: dict | None = None,
) -> dict[str, Any]:
    """Render parking / bio / group-interest fields (outside Streamlit forms for reactivity)."""
    current = current or {}

    st.markdown("**Parking**")
    c1, c2 = st.columns(2)
    parking_number = c1.text_input(
        "Parking Number",
        value=current.get("parking_number") or "",
        key=f"{key_prefix}_parking_number",
    )
    parking_floor = c2.text_input(
        "Parking Floor",
        value=current.get("parking_floor") or "",
        key=f"{key_prefix}_parking_floor",
    )

    current_share = current.get("parking_share_mode") or PARKING_SHARE_NOT_AVAILABLE
    share_index = (
        PARKING_SHARE_OPTIONS.index(current_share)
        if current_share in PARKING_SHARE_OPTIONS
        else 0
    )
    parking_share_mode = st.selectbox(
        "Parking available to others",
        PARKING_SHARE_OPTIONS,
        index=share_index,
        format_func=lambda value: PARKING_SHARE_LABELS[value],
        key=f"{key_prefix}_parking_share_mode",
    )

    parking_availability_value = None
    parking_availability_unit = None
    parking_charges = None
    if parking_share_mode in (PARKING_SHARE_FREE, PARKING_SHARE_PAID):
        d1, d2 = st.columns(2)
        current_duration = current.get("parking_availability_value")
        parking_availability_value = d1.number_input(
            "Availability duration",
            min_value=1,
            value=int(current_duration or 1),
            step=1,
            key=f"{key_prefix}_parking_availability_value",
        )
        current_unit = current.get("parking_availability_unit") or "days"
        unit_index = (
            PARKING_UNITS.index(current_unit) if current_unit in PARKING_UNITS else 1
        )
        parking_availability_unit = d2.selectbox(
            "Availability period",
            PARKING_UNITS,
            index=unit_index,
            format_func=lambda value: PARKING_UNIT_LABELS[value],
            key=f"{key_prefix}_parking_availability_unit",
        )
        if parking_share_mode == PARKING_SHARE_PAID:
            current_charges = current.get("parking_charges")
            parking_charges = st.number_input(
                "Applicable charges",
                min_value=0.0,
                value=float(current_charges or 0.0),
                step=50.0,
                key=f"{key_prefix}_parking_charges",
            )

    st.markdown("**About**")
    bio = st.text_area(
        "Bio",
        value=current.get("bio") or "",
        max_chars=TEXT_LIMIT,
        height=120,
        help=f"Free text up to {TEXT_LIMIT} characters.",
        key=f"{key_prefix}_bio",
    )

    st.markdown("**Interested in groups**")
    interest_groups = load_interest_groups(client)
    selected_ids = decode_group_interest_ids(current.get("group_interests"))
    chosen: list[str] = []
    if not interest_groups:
        st.caption(
            "No group interest options yet. An admin can add them under Users."
        )
    else:
        st.caption("Select one or more groups you are interested in.")
        cols = st.columns(2)
        for index, group in enumerate(interest_groups):
            col = cols[index % 2]
            checked = col.checkbox(
                group["name"],
                value=group["id"] in selected_ids,
                key=f"{key_prefix}_interest_group_{group['id']}",
            )
            if checked:
                chosen.append(group["id"])

    return normalize_extended_profile_fields(
        {
            "parking_number": parking_number,
            "parking_floor": parking_floor,
            "parking_share_mode": parking_share_mode,
            "parking_availability_value": parking_availability_value,
            "parking_availability_unit": parking_availability_unit,
            "parking_charges": parking_charges,
            "bio": bio,
            "group_interest_ids": chosen,
        }
    )
