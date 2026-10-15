from __future__ import annotations

from typing import Any

import streamlit as st

from lib.profile_extended_fields import (
    PARKING_SHARE_FREE,
    PARKING_SHARE_PAID,
    PARKING_UNIT_LABELS,
    parking_share_label,
)
from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"


def _rpc_error(exc: Exception) -> str:
    message = str(exc)
    if "get_available_parking" in message or "PGRST202" in message:
        return "Parking sharing is unavailable (run migration 028)."
    return message


def load_available_parking(client: SchemaClient) -> tuple[list[dict], str | None]:
    try:
        rows = client.raw.rpc("get_available_parking").execute().data or []
        return [row for row in rows if isinstance(row, dict)], None
    except Exception as exc:
        return [], _rpc_error(exc)


def submit_parking_request(
    client: SchemaClient,
    *,
    owner_id: str,
    message: str | None = None,
) -> str | None:
    try:
        client.raw.rpc(
            "submit_parking_request",
            {
                "p_owner_id": owner_id,
                "p_message": (message or "").strip() or None,
            },
        ).execute()
        return None
    except Exception as exc:
        return _rpc_error(exc)


def respond_parking_request(
    client: SchemaClient,
    *,
    request_id: str,
    approve: bool,
    comment: str | None = None,
) -> str | None:
    try:
        client.raw.rpc(
            "respond_parking_request",
            {
                "p_request_id": request_id,
                "p_approve": approve,
                "p_comment": (comment or "").strip() or None,
            },
        ).execute()
        return None
    except Exception as exc:
        return _rpc_error(exc)


def cancel_parking_allocation(client: SchemaClient, *, request_id: str) -> str | None:
    try:
        client.raw.rpc(
            "cancel_parking_allocation",
            {"p_request_id": request_id},
        ).execute()
        return None
    except Exception as exc:
        return _rpc_error(exc)


def load_my_parking_requests(client: SchemaClient, user_id: str) -> list[dict]:
    try:
        return (
            client.table("parking_requests")
            .select(
                "*, "
                "owner:profiles!parking_requests_owner_id_fkey"
                "(id, first_name, last_name, title, parking_number, parking_floor), "
                "requester:profiles!parking_requests_requester_id_fkey"
                "(id, first_name, last_name, title, phone, email, flat_number)"
            )
            .or_(f"owner_id.eq.{user_id},requester_id.eq.{user_id}")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        return []


def format_parking_terms(row: dict[str, Any]) -> str:
    mode = row.get("parking_share_mode")
    parts = [parking_share_label(mode)]
    duration = row.get("parking_availability_value")
    unit = row.get("parking_availability_unit")
    if duration and unit:
        unit_label = PARKING_UNIT_LABELS.get(unit, unit)
        parts.append(f"for {duration} {unit_label.lower()}")
    if mode == PARKING_SHARE_PAID:
        charges = row.get("parking_charges")
        if charges is not None:
            parts.append(f"Charges: {charges}")
    elif mode == PARKING_SHARE_FREE:
        parts.append("No charges")
    return " · ".join(parts)


def render_available_parking(client: SchemaClient, profile: dict) -> None:
    st.subheader("Available Parking")
    st.caption(
        "Parkings shared by residents (Free / Paid). "
        "Request allocation from the owner; they can approve only one request."
    )

    user_id = profile.get("id")
    listings, error = load_available_parking(client)
    if error:
        st.warning(error)
        return

    # Owner inbox / my requests
    my_requests = load_my_parking_requests(client, user_id) if user_id else []
    incoming = [
        r
        for r in my_requests
        if r.get("owner_id") == user_id and r.get("status") == STATUS_PENDING
    ]
    my_outgoing = [r for r in my_requests if r.get("requester_id") == user_id]
    my_active = [
        r
        for r in my_requests
        if r.get("status") == STATUS_APPROVED
        and (r.get("owner_id") == user_id or r.get("requester_id") == user_id)
    ]

    if my_active:
        st.markdown("**Active allocations**")
        for req in my_active:
            owner = req.get("owner") or {}
            requester = req.get("requester") or {}
            with st.container(border=True):
                st.write(
                    f"Parking **{owner.get('parking_number') or '—'}** "
                    f"(Floor: {owner.get('parking_floor') or '—'})"
                )
                st.caption(
                    f"Owner: {format_name(owner, 'Owner')} · "
                    f"Allocated to: {format_name(requester, 'Member')}"
                )
                if req.get("owner_comment"):
                    st.write(f"Comment: {req['owner_comment']}")
                if st.button(
                    "Cancel allocation",
                    key=f"cancel_parking_{req['id']}",
                ):
                    err = cancel_parking_allocation(client, request_id=req["id"])
                    if err:
                        st.error(err)
                    else:
                        st.success(
                            "Allocation cancelled. Parking is available again."
                        )
                        st.rerun()

    if incoming:
        st.markdown("**Requests for your parking**")
        for req in incoming:
            requester = req.get("requester") or {}
            with st.container(border=True):
                st.write(
                    f"**{format_name(requester, 'Member')}** "
                    f"(Flat: {requester.get('flat_number') or '—'})"
                )
                if requester.get("phone"):
                    st.caption(f"Phone: {requester['phone']}")
                if req.get("request_message"):
                    st.write(f"Message: {req['request_message']}")
                comment = st.text_area(
                    "Your comment (optional)",
                    key=f"parking_owner_comment_{req['id']}",
                )
                c1, c2 = st.columns(2)
                if c1.button(
                    "Approve",
                    key=f"parking_approve_{req['id']}",
                    type="primary",
                ):
                    err = respond_parking_request(
                        client,
                        request_id=req["id"],
                        approve=True,
                        comment=comment,
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success(
                            "Approved. Other pending requests for this parking "
                            "were rejected automatically."
                        )
                        st.rerun()
                if c2.button(
                    "Reject",
                    key=f"parking_reject_{req['id']}",
                ):
                    err = respond_parking_request(
                        client,
                        request_id=req["id"],
                        approve=False,
                        comment=comment,
                    )
                    if err:
                        st.error(err)
                    else:
                        st.info("Request rejected.")
                        st.rerun()

    if my_outgoing:
        with st.expander("My parking requests", expanded=False):
            for req in my_outgoing:
                owner = req.get("owner") or {}
                st.write(
                    f"**{owner.get('parking_number') or 'Parking'}** — "
                    f"{(req.get('status') or '').title()} · "
                    f"Owner: {format_name(owner, 'Owner')}"
                )
                if req.get("owner_comment"):
                    st.caption(f"Owner comment: {req['owner_comment']}")

    st.divider()
    st.markdown("**Browse available parking**")

    others = [row for row in listings if row.get("owner_id") != user_id]
    own = [row for row in listings if row.get("owner_id") == user_id]
    if own:
        st.caption(
            "Your shareable parking is listed for others while not allocated."
        )

    if not others:
        st.info("No available parking listings right now.")
        return

    for row in others:
        owner_name = format_name(
            {
                "first_name": row.get("owner_first_name"),
                "last_name": row.get("owner_last_name"),
                "title": row.get("owner_title"),
            },
            "Resident",
        )
        with st.container(border=True):
            st.markdown(
                f"**Parking {row.get('parking_number') or '—'}** "
                f"— Floor: {row.get('parking_floor') or '—'}"
            )
            st.caption(
                f"Owner: {owner_name}"
                + (
                    f" · Tower: {row['tower_name']}"
                    if row.get("tower_name")
                    else ""
                )
            )
            st.write(format_parking_terms(row))

            already_pending = any(
                r.get("owner_id") == row.get("owner_id")
                and r.get("status") == STATUS_PENDING
                for r in my_outgoing
            )
            if already_pending:
                st.caption("You already have a pending request for this parking.")
                continue

            msg = st.text_input(
                "Message to owner (optional)",
                key=f"parking_req_msg_{row['owner_id']}",
            )
            if st.button(
                "Request this parking",
                key=f"parking_req_btn_{row['owner_id']}",
                type="primary",
            ):
                err = submit_parking_request(
                    client,
                    owner_id=row["owner_id"],
                    message=msg,
                )
                if err:
                    st.error(err)
                else:
                    st.success("Request sent to the parking owner.")
                    st.rerun()
