from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta

import streamlit as st

from lib.admin_contacts import load_admin_contacts
from lib.contact_privacy import HIDDEN_CONTACT, format_visible_contact
from lib.auth import is_admin
from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient

PAGE_SIZE = 5
DROP_CORRIDOR = "Sierra - 1102 flat corridor"
FOOD_SAFETY_NOTE = (
    "**Strict Food Safety Guidelines:** To eliminate spillage or spoilage risks, "
    "no cooked food, quick-perishables, or junk food will be accepted. Only dry staple "
    "ingredients with a long shelf life—such as un-sprouted raw grains, rice, wheat, or "
    "pulses/dal (held safely for 1–2 weeks)—will be accepted. Food items will be handed "
    "over to beneficiaries immediately/as collected rather than held long-term."
)
RECYCLABLE_NOTE = (
    "Electric items, carton boxes, and other recyclable or scrap items are welcome. "
    "Proceeds from scrap dealers can support school children in Maan village for clothes, "
    "bags, or basic needs."
)
HANDOFF_PICKUP = "pickup"
HANDOFF_CORRIDOR = "drop_corridor"

_OFFER_COLUMNS = (
    "id, added_by, society_id, items, includes_recyclables, handoff_mode, pickup_at, "
    "remarks, drive_id, in_queue, status, admin_reason, reviewed_at, created_at, "
    "donation_drives(id, title, drive_date, location_text, visibility_days, is_published)"
)
_OFFER_COLUMNS_ADMIN = (
    _OFFER_COLUMNS
    + ", profiles(first_name, last_name, title, phone, email, flat_number, "
    "societies(name), towers(name))"
)


def _utc_now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_dt(value: str | datetime | None) -> str:
    parsed = _parse_dt(value)
    if not parsed:
        return "—"
    return parsed.strftime("%d %b %Y, %I:%M %p").lstrip("0")


def _format_day(value: str | date | None) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    if not value:
        return "—"
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(value)


def _page(rows: list[dict], *, key_prefix: str, empty: str) -> list[dict]:
    total = len(rows)
    if total == 0:
        st.info(empty)
        return []
    page_key = f"{key_prefix}_page"
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    current = int(st.session_state.get(page_key, 1) or 1)
    current = max(1, min(current, total_pages))
    st.session_state[page_key] = current
    start = (current - 1) * PAGE_SIZE
    st.caption(
        f"Showing {start + 1}–{min(start + PAGE_SIZE, total)} of {total} "
        f"(page {current} of {total_pages}, {PAGE_SIZE} per page)"
    )
    if total_pages > 1:
        prev_col, mid_col, next_col = st.columns([1, 2, 1])
        if prev_col.button(
            "← Previous",
            key=f"{key_prefix}_prev",
            disabled=current <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = current - 1
            st.rerun()
        mid_col.caption(f"Page {current} / {total_pages}")
        if next_col.button(
            "Next →",
            key=f"{key_prefix}_next",
            disabled=current >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = current + 1
            st.rerun()
    return rows[start : start + PAGE_SIZE]


def _drive_visible(drive: dict | None) -> bool:
    if not drive or not drive.get("is_published"):
        return False
    try:
        drive_day = date.fromisoformat(str(drive.get("drive_date"))[:10])
    except (TypeError, ValueError):
        return False
    days = int(drive.get("visibility_days") or 14)
    return date.today() <= drive_day + timedelta(days=days)


def _load_drives(client: SchemaClient, *, admin: bool) -> tuple[list[dict], str | None]:
    try:
        query = (
            client.table("donation_drives")
            .select(
                "id, title, location_text, drive_date, notes, visibility_days, "
                "is_published, created_at"
            )
            .order("drive_date", desc=True)
        )
        if not admin:
            query = query.eq("is_published", True)
        rows = query.execute().data or []
        return rows, None
    except Exception as exc:
        lowered = str(exc).lower()
        if "donation_drives" in lowered and (
            "does not exist" in lowered
            or "schema cache" in lowered
            or "pgrst205" in lowered
        ):
            return [], "Give Away / Donation is unavailable. Run Supabase migration 041, then refresh."
        return [], f"Could not load donation drives: {exc}"


def _load_offers(client: SchemaClient, *, admin: bool) -> tuple[list[dict], str | None]:
    columns = _OFFER_COLUMNS_ADMIN if admin else _OFFER_COLUMNS
    try:
        rows = (
            client.table("donation_offers")
            .select(columns)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return rows, None
    except Exception as exc:
        lowered = str(exc).lower()
        if "donation_offers" in lowered and (
            "does not exist" in lowered
            or "schema cache" in lowered
            or "pgrst205" in lowered
        ):
            return [], "Give Away / Donation is unavailable. Run Supabase migration 041, then refresh."
        if admin and "profiles" in lowered:
            try:
                rows = (
                    client.table("donation_offers")
                    .select(_OFFER_COLUMNS)
                    .order("created_at", desc=True)
                    .execute()
                    .data
                    or []
                )
                return rows, None
            except Exception as inner:
                return [], f"Could not load donations: {inner}"
        return [], f"Could not load donations: {exc}"


def _render_admin_notify_block(client: SchemaClient) -> None:
    st.markdown("**Notify the app owner**")
    admins, error = load_admin_contacts(client)
    if error:
        st.caption(error)
        return
    if not admins:
        st.caption("No admin contact is available yet. Open Contact from the left menu later.")
        return
    for admin in admins:
        name = format_name(admin, "App owner")
        phone = format_visible_contact(
            admin.get("phone"),
            masked=bool(admin.get("mask_phone")),
            viewer_is_admin=is_admin(),
        )
        email = (admin.get("email") or "").strip() or "—"
        raw_phone = (admin.get("phone") or "").strip()
        parts = [f"**{name}**"]
        if phone == HIDDEN_CONTACT or not raw_phone:
            parts.append(f"Mobile: {phone or '—'}")
        else:
            parts.append(f"Mobile: [{phone}](tel:{raw_phone})")
        if email != "—":
            parts.append(f"Email: [{email}](mailto:{email})")
        else:
            parts.append("Email: —")
        st.markdown(" · ".join(parts))


def _render_drives_banner(drives: list[dict], *, admin: bool) -> None:
    visible = drives if admin else [d for d in drives if _drive_visible(d)]
    st.markdown("**Upcoming / active donation drives**")
    if not visible:
        st.info("No donation drive is published yet. Watch this space for the next drive date.")
        return
    for drive in visible[:5]:
        with st.container(border=True):
            st.markdown(
                f"**{drive.get('title') or 'Donation drive'}** · "
                f"{_format_day(drive.get('drive_date'))}"
            )
            st.write(f"Where: {drive.get('location_text') or '—'}")
            if drive.get("notes"):
                st.caption(drive["notes"])
            st.caption(
                f"Offers stay visible for {drive.get('visibility_days') or 14} day(s) after the drive date."
            )


def _handoff_label(offer: dict) -> str:
    if offer.get("handoff_mode") == HANDOFF_PICKUP:
        return f"Pickup from flat · {_format_dt(offer.get('pickup_at'))}"
    return f"Drop at {DROP_CORRIDOR}"


def _status_label(offer: dict) -> str:
    status = str(offer.get("status") or "pending").title()
    if offer.get("status") == "approved":
        if offer.get("in_queue"):
            return f"{status} · In queue"
        drive = offer.get("donation_drives") or {}
        if isinstance(drive, dict) and drive.get("title"):
            return f"{status} · Linked to {drive.get('title')}"
    return status


def _render_offer_card(offer: dict, *, admin: bool, profile: dict) -> None:
    with st.container(border=True):
        st.markdown(f"**Donation items**")
        st.write(offer.get("items") or "—")
        st.caption(_status_label(offer))
        st.write(_handoff_label(offer))
        if offer.get("includes_recyclables"):
            st.write("Includes recyclable / scrap / electric items or carton boxes.")
        if offer.get("remarks"):
            st.write(f"Remark for school children: {offer['remarks']}")
        if offer.get("admin_reason"):
            st.write(f"Admin note: {offer['admin_reason']}")
        st.caption(f"Submitted {_format_dt(offer.get('created_at'))}")

        if admin:
            donor = offer.get("profiles") or {}
            if isinstance(donor, dict):
                society = (donor.get("societies") or {}).get("name")
                tower = (donor.get("towers") or {}).get("name")
                st.markdown(
                    f"**Donor:** {format_name(donor, 'Member')}  \n"
                    f"**Phone:** {donor.get('phone') or '—'} · "
                    f"**Email:** {donor.get('email') or '—'}  \n"
                    f"**Society:** {society or '—'} · **Tower:** {tower or '—'} · "
                    f"**Flat:** {donor.get('flat_number') or '—'}"
                )


def _render_offer_form(client: SchemaClient, profile: dict) -> None:
    st.markdown("**Submit a donation**")
    st.info(RECYCLABLE_NOTE)
    items = st.text_area(
        "Donation items",
        key="donation_items",
        placeholder="List the items you want to give away",
        height=120,
    )
    st.markdown(FOOD_SAFETY_NOTE)
    includes_recyclables = st.checkbox(
        "This includes electric items, carton boxes, or other recyclable / scrap items",
        key="donation_recyclables",
    )
    handoff = st.radio(
        "How will the items reach the app owner?",
        (
            "Request the app owner to pick up from my flat",
            f"I will keep the items at {DROP_CORRIDOR} and notify the app owner",
        ),
        key="donation_handoff",
    )
    pickup_at = None
    if handoff.startswith("Request"):
        day = st.date_input("Preferred pickup date", min_value=date.today(), key="donation_pickup_day")
        clock = st.time_input("Preferred pickup time", value=time(10, 0), key="donation_pickup_time")
        pickup_at = datetime.combine(day, clock).astimezone()
    else:
        st.caption(f"Please place the items safely at {DROP_CORRIDOR}, then notify the app owner.")
        _render_admin_notify_block(client)

    remarks = st.text_area(
        "Donation comment / remark",
        key="donation_remarks",
        placeholder=(
            "Any specific request to donate to school children (except money/cash). "
            "This notifies the app owner."
        ),
        height=90,
    )
    if st.button("Submit donation request", type="primary", key="donation_submit"):
        errors: list[str] = []
        if not (items or "").strip():
            errors.append("Donation items are required.")
        if handoff.startswith("Request") and pickup_at is None:
            errors.append("Choose a pickup date and time.")
        if not profile.get("society_id"):
            errors.append("Your profile needs a society before you can donate.")
        if errors:
            for err in errors:
                st.error(err)
            return
        try:
            client.table("donation_offers").insert(
                {
                    "added_by": profile["id"],
                    "society_id": profile.get("society_id"),
                    "items": items.strip(),
                    "includes_recyclables": bool(includes_recyclables),
                    "handoff_mode": HANDOFF_PICKUP if handoff.startswith("Request") else HANDOFF_CORRIDOR,
                    "pickup_at": pickup_at.isoformat() if pickup_at else None,
                    "remarks": remarks.strip() or None,
                    "in_queue": True,
                    "status": "pending",
                }
            ).execute()
            st.success("Donation request submitted. An admin will approve or reject it.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not submit the donation (run migration 041): {exc}")


def _admin_review_offer(
    client: SchemaClient,
    offer: dict,
    drives: list[dict],
    *,
    admin_id: str | None,
) -> None:
    if offer.get("status") != "pending":
        with st.expander("Update placement"):
            placement = st.radio(
                "Placement",
                ("Keep in queue", "Link to a donation drive"),
                key=f"donation_place_mode_{offer['id']}",
                index=0 if offer.get("in_queue") else 1,
            )
            drive_id = None
            if placement.startswith("Link"):
                options = {f"{d.get('title')} · {_format_day(d.get('drive_date'))}": d["id"] for d in drives}
                if not options:
                    st.warning("Create a donation drive first.")
                else:
                    chosen = st.selectbox(
                        "Donation drive",
                        list(options.keys()),
                        key=f"donation_place_drive_{offer['id']}",
                    )
                    drive_id = options[chosen]
            if st.button("Save placement", key=f"donation_place_save_{offer['id']}"):
                try:
                    client.table("donation_offers").update(
                        {
                            "in_queue": placement.startswith("Keep"),
                            "drive_id": None if placement.startswith("Keep") else drive_id,
                            "updated_at": _utc_now_iso(),
                        }
                    ).eq("id", offer["id"]).execute()
                    st.success("Placement updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update placement: {exc}")
        return

    reason = st.text_input("Reason / note", key=f"donation_reason_{offer['id']}")
    placement = st.radio(
        "If approved, place the offer",
        ("In queue", "Link to a donation drive"),
        key=f"donation_approve_place_{offer['id']}",
        horizontal=True,
    )
    drive_id = None
    if placement.startswith("Link"):
        options = {f"{d.get('title')} · {_format_day(d.get('drive_date'))}": d["id"] for d in drives}
        if not options:
            st.warning("Create a donation drive first, or keep the offer in queue.")
        else:
            chosen = st.selectbox(
                "Donation drive",
                list(options.keys()),
                key=f"donation_approve_drive_{offer['id']}",
            )
            drive_id = options[chosen]
    accept_col, reject_col, delete_col = st.columns(3)
    if accept_col.button(
        "Approve",
        key=f"donation_approve_{offer['id']}",
        type="primary",
        use_container_width=True,
    ):
        if placement.startswith("Link") and not drive_id:
            st.error("Choose a donation drive, or keep the offer in queue.")
            return
        try:
            client.table("donation_offers").update(
                {
                    "status": "approved",
                    "admin_reason": reason.strip() or None,
                    "in_queue": placement.startswith("In"),
                    "drive_id": None if placement.startswith("In") else drive_id,
                    "reviewed_by": admin_id,
                    "reviewed_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", offer["id"]).execute()
            st.success("Donation approved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not approve: {exc}")
    if reject_col.button(
        "Reject",
        key=f"donation_reject_{offer['id']}",
        use_container_width=True,
    ):
        if not reason.strip():
            st.error("Enter a reason when rejecting.")
            return
        try:
            client.table("donation_offers").update(
                {
                    "status": "rejected",
                    "admin_reason": reason.strip(),
                    "reviewed_by": admin_id,
                    "reviewed_at": _utc_now_iso(),
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", offer["id"]).execute()
            st.success("Donation rejected.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not reject: {exc}")
    if delete_col.button(
        "Delete",
        key=f"donation_delete_{offer['id']}",
        use_container_width=True,
    ):
        try:
            client.table("donation_offers").delete().eq("id", offer["id"]).execute()
            st.success("Donation deleted.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not delete: {exc}")


def _render_admin_drives(client: SchemaClient, profile: dict, drives: list[dict]) -> None:
    st.markdown("**Donation drives**")
    st.caption(
        "Set a drive date for the society or any location. Members see published drives on this tab. "
        "Visibility days control how long linked donations stay on the page after the drive date."
    )
    with st.form("donation_drive_form"):
        title = st.text_input("Drive title", placeholder="Example: Winter clothes drive")
        location = st.text_input(
            "Location",
            placeholder="Society name, tower lobby, or any place",
        )
        drive_day = st.date_input("Drive date", value=date.today())
        visibility_days = int(
            st.number_input(
                "Keep linked donations visible for (days after drive date)",
                min_value=1,
                max_value=365,
                value=14,
                step=1,
            )
        )
        notes = st.text_area("Notes for members", placeholder="Optional details")
        published = st.checkbox("Publish for members", value=True)
        saved = st.form_submit_button("Add donation drive", type="primary")
    if saved:
        if not title.strip() or not location.strip():
            st.error("Title and location are required.")
        else:
            try:
                client.table("donation_drives").insert(
                    {
                        "title": title.strip(),
                        "location_text": location.strip(),
                        "drive_date": drive_day.isoformat(),
                        "notes": notes.strip() or None,
                        "visibility_days": visibility_days,
                        "is_published": bool(published),
                        "created_by": profile.get("id"),
                    }
                ).execute()
                st.success("Donation drive saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save the drive (run migration 041): {exc}")

    for drive in _page(drives, key_prefix="donation_drive_admin", empty="No donation drives yet."):
        with st.container(border=True):
            st.markdown(
                f"**{drive.get('title')}** · {_format_day(drive.get('drive_date'))} · "
                f"{'Published' if drive.get('is_published') else 'Hidden'}"
            )
            st.write(f"Where: {drive.get('location_text') or '—'}")
            st.caption(
                f"Visibility after drive: {drive.get('visibility_days') or 14} day(s)"
            )
            if drive.get("notes"):
                st.write(drive["notes"])
            pub_col, del_col = st.columns(2)
            if pub_col.button(
                "Hide" if drive.get("is_published") else "Publish",
                key=f"donation_drive_toggle_{drive['id']}",
                use_container_width=True,
            ):
                try:
                    client.table("donation_drives").update(
                        {
                            "is_published": not bool(drive.get("is_published")),
                            "updated_at": _utc_now_iso(),
                        }
                    ).eq("id", drive["id"]).execute()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update the drive: {exc}")
            if del_col.button(
                "Delete drive",
                key=f"donation_drive_delete_{drive['id']}",
                use_container_width=True,
            ):
                try:
                    client.table("donation_drives").delete().eq("id", drive["id"]).execute()
                    st.success("Drive deleted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not delete the drive: {exc}")


def render_donations(client: SchemaClient, profile: dict, *, admin: bool = False) -> None:
    st.subheader("Give Away / Donation")
    drives, drive_error = _load_drives(client, admin=admin)
    if drive_error:
        st.warning(drive_error)
        return
    offers, offer_error = _load_offers(client, admin=admin)
    if offer_error:
        st.warning(offer_error)
        return

    _render_drives_banner(drives, admin=admin)
    st.divider()

    if admin:
        _render_admin_drives(client, profile, drives)
        st.divider()
        st.markdown("**Donation requests**")
        pending = [row for row in offers if row.get("status") == "pending"]
        others = [row for row in offers if row.get("status") != "pending"]
        ordered = pending + others
        for offer in _page(
            ordered,
            key_prefix="donation_admin_offers",
            empty="No donation requests yet.",
        ):
            _render_offer_card(offer, admin=True, profile=profile)
            _admin_review_offer(client, offer, drives, admin_id=profile.get("id"))
        return

    mine = [row for row in offers if row.get("added_by") == profile.get("id")]
    community = [
        row
        for row in offers
        if row.get("added_by") != profile.get("id") and row.get("status") == "approved"
    ]

    st.markdown("**Your donation requests**")
    for offer in _page(
        mine,
        key_prefix="donation_mine",
        empty="You have not submitted a donation yet.",
    ):
        _render_offer_card(offer, admin=False, profile=profile)
        if offer.get("status") == "pending" and st.button(
            "Delete request",
            key=f"donation_user_delete_{offer['id']}",
        ):
            try:
                client.table("donation_offers").delete().eq("id", offer["id"]).execute()
                st.success("Donation request deleted.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not delete: {exc}")

    st.divider()
    _render_offer_form(client, profile)
    st.divider()
    st.markdown("**Community donations**")
    for offer in _page(
        community,
        key_prefix="donation_community",
        empty="No approved donations are visible right now.",
    ):
        _render_offer_card(offer, admin=False, profile=profile)
