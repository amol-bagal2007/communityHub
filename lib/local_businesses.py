from __future__ import annotations

import math
from datetime import datetime, timezone

import streamlit as st

from lib.local_business_ratings import (
    find_my_rating,
    load_business_ratings,
    rating_caption,
    render_business_rating_form,
    render_business_reviews,
    summarize_business_ratings,
)
from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient
from lib.visibility import load_societies, load_towers

INFO_NOTE = (
    "This is only for information. Please contact the respective person "
    "on the given WhatsApp or personal mobile number."
)
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

PAGE_SIZE = 5
WEEK_DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_week_off(days: list[str]) -> str | None:
    selected = [d for d in WEEK_DAYS if d in days]
    return ", ".join(selected) if selected else None


def decode_week_off(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [d for d in WEEK_DAYS if d in parts]


def render_week_off_checkboxes(
    *,
    key_prefix: str,
    current: str | None = None,
) -> str | None:
    selected = decode_week_off(current)
    st.caption("Week off (select one or more days)")
    cols = st.columns(4)
    chosen: list[str] = []
    for index, day in enumerate(WEEK_DAYS):
        if cols[index % 4].checkbox(
            day,
            value=day in selected,
            key=f"{key_prefix}_week_off_{day}",
        ):
            chosen.append(day)
    return encode_week_off(chosen)


def _page_businesses(
    businesses: list[dict],
    *,
    key_prefix: str,
) -> list[dict]:
    total = len(businesses)
    if total == 0:
        st.info("No local businesses listed yet.")
        return []

    page_key = f"{key_prefix}_page"
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    current_page = int(st.session_state.get(page_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[page_key] = current_page

    start = (current_page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = businesses[start:end]

    if total > PAGE_SIZE:
        st.caption(
            f"Showing {start + 1}–{min(end, total)} of {total} "
            f"(page {current_page} of {total_pages})"
        )
        prev_col, mid_col, next_col = st.columns([1, 2, 1])
        if prev_col.button(
            "← Previous",
            key=f"{key_prefix}_prev",
            disabled=current_page <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page - 1
            st.rerun()
        mid_col.caption(f"Page {current_page} / {total_pages}")
        if next_col.button(
            "Next →",
            key=f"{key_prefix}_next",
            disabled=current_page >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = current_page + 1
            st.rerun()
    else:
        st.caption(f"{total} business{'es' if total != 1 else ''}")

    return page_items


def _validate_business_payload(
    *,
    business_name: str,
    first_name: str,
    last_name: str,
    society_id: str | None,
    tower_id: str | None,
    flat_number: str,
    whatsapp_group_link: str,
) -> list[str]:
    errors: list[str] = []
    if not business_name.strip():
        errors.append("Business name is required.")
    if not first_name.strip():
        errors.append("First name is required.")
    if not last_name.strip():
        errors.append("Last name is required.")
    if not society_id:
        errors.append("Select a society.")
    if not tower_id:
        errors.append("Select a tower.")
    if not flat_number.strip():
        errors.append("Flat / unit number is required.")
    link = (whatsapp_group_link or "").strip()
    if link and not (link.startswith("http://") or link.startswith("https://")):
        errors.append("WhatsApp group link should start with https://")
    return errors


def _render_society_tower(
    client: SchemaClient,
    societies: list[dict],
    *,
    key_prefix: str,
    current_society_id: str | None = None,
    current_tower_id: str | None = None,
) -> tuple[str | None, str | None]:
    soc_map = {s["name"]: s["id"] for s in societies}
    id_to_name = {s["id"]: s["name"] for s in societies}
    society_key = f"{key_prefix}_society"
    if society_key not in st.session_state:
        st.session_state[society_key] = id_to_name.get(current_society_id, "")
    society_name = st.selectbox(
        "Society *",
        options=[""] + list(soc_map.keys()),
        format_func=lambda value: "Select society..." if value == "" else value,
        key=society_key,
    )
    society_id = soc_map.get(society_name)
    towers = load_towers(
        client,
        society_id,
        enabled_only=True,
        include_id=current_tower_id if society_id == current_society_id else None,
    )
    tower_map = {t["name"]: t["id"] for t in towers}
    tower_id_to_name = {t["id"]: t["name"] for t in towers}
    tower_key = f"{key_prefix}_tower"
    if tower_key not in st.session_state:
        st.session_state[tower_key] = tower_id_to_name.get(current_tower_id, "")
    elif (
        st.session_state.get(tower_key)
        and st.session_state.get(tower_key) not in tower_map
    ):
        st.session_state[tower_key] = ""
    tower_name = st.selectbox(
        "Tower *",
        options=[""] + list(tower_map.keys()),
        format_func=lambda value: "Select tower..." if value == "" else value,
        key=tower_key,
        disabled=not society_id,
    )
    return society_id, tower_map.get(tower_name)


def render_local_businesses(
    client: SchemaClient,
    profile: dict,
    *,
    admin: bool = False,
    societies: list[dict] | None = None,
) -> None:
    """Shared Local Business UI for members and admin."""
    st.subheader("Local Business")
    st.info(INFO_NOTE)
    user_id = profile.get("id")
    key_prefix = "admin_local_biz" if admin else "user_local_biz"
    societies = societies or load_societies(client, enabled_only=not admin)

    with st.expander("Add a Local Business"):
        if not admin:
            st.caption("New businesses are sent to the admin for approval.")
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First Name *", key=f"{key_prefix}_add_first")
        last_name = c2.text_input("Last Name *", key=f"{key_prefix}_add_last")
        business_name = st.text_input("Business Name *", key=f"{key_prefix}_add_name")
        description = st.text_area("Business Description", key=f"{key_prefix}_add_desc")
        phone = st.text_input("Phone", key=f"{key_prefix}_add_phone")
        whatsapp_number = st.text_input(
            "Personal WhatsApp Number",
            key=f"{key_prefix}_add_wa",
            help="Include country code if possible, e.g. 9198xxxxxxxx",
        )
        add_society_id, add_tower_id = _render_society_tower(
            client,
            societies,
            key_prefix=f"{key_prefix}_add",
            current_society_id=profile.get("society_id"),
            current_tower_id=profile.get("tower_id"),
        )
        flat_number = st.text_input("Flat / Unit Number *", key=f"{key_prefix}_add_flat")
        whatsapp_group_link = st.text_input(
            "WhatsApp Group Link",
            key=f"{key_prefix}_add_wa_group",
            placeholder="https://chat.whatsapp.com/...",
        )
        timing = st.text_input(
            "Timing",
            key=f"{key_prefix}_add_timing",
            placeholder="e.g. 9:00 AM – 8:00 PM",
        )
        week_off = render_week_off_checkboxes(key_prefix=f"{key_prefix}_add")
        if st.button("Add Business", type="primary", key=f"{key_prefix}_add_btn"):
            errors = _validate_business_payload(
                business_name=business_name,
                first_name=first_name,
                last_name=last_name,
                society_id=add_society_id,
                tower_id=add_tower_id,
                flat_number=flat_number,
                whatsapp_group_link=whatsapp_group_link,
            )
            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    client.table("local_businesses").insert(
                        {
                            "business_name": business_name.strip(),
                            "first_name": first_name.strip(),
                            "last_name": last_name.strip(),
                            "description": description.strip() or None,
                            "phone": phone.strip() or None,
                            "whatsapp_number": whatsapp_number.strip() or None,
                            "whatsapp_group_link": whatsapp_group_link.strip() or None,
                            "timing": timing.strip() or None,
                            "week_off": week_off,
                            "society_id": add_society_id,
                            "tower_id": add_tower_id,
                            "flat_number": flat_number.strip(),
                            "added_by": user_id,
                            "status": STATUS_APPROVED if admin else STATUS_PENDING,
                        }
                    ).execute()
                    if admin:
                        st.success("Local business added.")
                    else:
                        st.success(
                            "Business submitted. It will appear after admin approval."
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not add business (run migration 030): {exc}")

    query = (
        client.table("local_businesses")
        .select("*, profiles(first_name, last_name), societies(name), towers(name)")
        .order("business_name")
    )
    if not admin and profile.get("society_id") and user_id:
        query = query.or_(
            f"and(society_id.eq.{profile['society_id']},status.eq.{STATUS_APPROVED}),"
            f"added_by.eq.{user_id}"
        )
    elif not admin and user_id:
        query = query.eq("added_by", user_id)
    businesses = query.execute().data or []

    page_items = _page_businesses(businesses, key_prefix=key_prefix)
    if not page_items:
        return

    business_ids = [b["id"] for b in page_items]
    try:
        ratings = load_business_ratings(client, business_ids)
        feedback = summarize_business_ratings(ratings)
    except Exception as exc:
        st.warning(
            f"Business ratings unavailable (run migration 026): {exc}"
        )
        ratings = []
        feedback = {}

    ratings_by_business: dict[str, list] = {}
    for row in ratings:
        ratings_by_business.setdefault(row["business_id"], []).append(row)

    for business in page_items:
        added_by = format_name(business.get("profiles"), "Member")
        can_edit = admin or business.get("added_by") == user_id
        open_key = f"{key_prefix}_open_{business['id']}"
        summary = feedback.get(business["id"])
        society_name = (business.get("societies") or {}).get("name")
        tower_name = (business.get("towers") or {}).get("name")
        status = (business.get("status") or STATUS_APPROVED).title()
        contact_name = format_name(business, "Contact")

        with st.container(border=True):
            summary_col, action_col = st.columns([5, 1])
            title = f"**{business.get('business_name') or 'Business'}**"
            if society_name:
                title += f" — {society_name}"
            summary_col.markdown(title)
            summary_col.caption(
                f"{rating_caption(summary)} · {status}"
                + (f" · {contact_name}" if business.get("first_name") else "")
            )
            if action_col.button(
                "Hide" if st.session_state.get(open_key) else "View",
                key=f"{key_prefix}_view_{business['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.caption(f"Added by {added_by} · Status: {status}")
            st.write(f"Contact: {contact_name}")
            st.write(
                f"Society: {society_name or '—'} · Tower: {tower_name or '—'} · "
                f"Flat: {business.get('flat_number') or '—'}"
            )
            if business.get("description"):
                st.write(business["description"])
            st.write(
                f"Phone: {business.get('phone') or '—'} · "
                f"WhatsApp: {business.get('whatsapp_number') or '—'}"
            )
            if business.get("whatsapp_group_link"):
                st.markdown(
                    f"[WhatsApp Group Link]({business['whatsapp_group_link']})"
                )
            if business.get("timing"):
                st.write(f"Timing: {business['timing']}")
            st.write(f"Week off: {business.get('week_off') or '—'}")

            if admin and business.get("status") == STATUS_PENDING:
                a1, a2 = st.columns(2)
                if a1.button(
                    "Approve",
                    key=f"{key_prefix}_approve_{business['id']}",
                    type="primary",
                ):
                    client.table("local_businesses").update(
                        {"status": STATUS_APPROVED, "updated_at": _utc_now_iso()}
                    ).eq("id", business["id"]).execute()
                    st.success("Business approved.")
                    st.rerun()
                if a2.button(
                    "Reject",
                    key=f"{key_prefix}_reject_{business['id']}",
                ):
                    client.table("local_businesses").update(
                        {"status": STATUS_REJECTED, "updated_at": _utc_now_iso()}
                    ).eq("id", business["id"]).execute()
                    st.warning("Business rejected.")
                    st.rerun()

            st.write(rating_caption(summary))
            biz_ratings = ratings_by_business.get(business["id"], [])
            render_business_reviews(biz_ratings)
            my_rating = find_my_rating(biz_ratings, user_id)
            render_business_rating_form(
                client,
                business_id=business["id"],
                user_id=user_id,
                existing=my_rating,
                key_prefix=f"{key_prefix}_{business['id']}",
            )

            if not can_edit:
                st.caption("Only the owner or an admin can edit this business.")
                continue

            st.markdown("**Edit business**")
            if not admin:
                st.caption("Saving changes sends this business back to the admin for approval.")
            e1, e2 = st.columns(2)
            edit_first = e1.text_input(
                "First Name *",
                value=business.get("first_name") or "",
                key=f"{key_prefix}_edit_first_{business['id']}",
            )
            edit_last = e2.text_input(
                "Last Name *",
                value=business.get("last_name") or "",
                key=f"{key_prefix}_edit_last_{business['id']}",
            )
            edit_name = st.text_input(
                "Business Name *",
                value=business.get("business_name") or "",
                key=f"{key_prefix}_edit_name_{business['id']}",
            )
            edit_desc = st.text_area(
                "Business Description",
                value=business.get("description") or "",
                key=f"{key_prefix}_edit_desc_{business['id']}",
            )
            edit_phone = st.text_input(
                "Phone",
                value=business.get("phone") or "",
                key=f"{key_prefix}_edit_phone_{business['id']}",
            )
            edit_wa = st.text_input(
                "Personal WhatsApp Number",
                value=business.get("whatsapp_number") or "",
                key=f"{key_prefix}_edit_wa_{business['id']}",
            )
            edit_society_id, edit_tower_id = _render_society_tower(
                client,
                societies,
                key_prefix=f"{key_prefix}_edit_{business['id']}",
                current_society_id=business.get("society_id"),
                current_tower_id=business.get("tower_id"),
            )
            edit_flat = st.text_input(
                "Flat / Unit Number *",
                value=business.get("flat_number") or "",
                key=f"{key_prefix}_edit_flat_{business['id']}",
            )
            edit_wa_group = st.text_input(
                "WhatsApp Group Link",
                value=business.get("whatsapp_group_link") or "",
                key=f"{key_prefix}_edit_wa_group_{business['id']}",
            )
            edit_timing = st.text_input(
                "Timing",
                value=business.get("timing") or "",
                key=f"{key_prefix}_edit_timing_{business['id']}",
            )
            edit_week_off = render_week_off_checkboxes(
                key_prefix=f"{key_prefix}_edit_{business['id']}",
                current=business.get("week_off"),
            )
            c1, c2 = st.columns(2)
            if c1.button(
                "Update",
                key=f"{key_prefix}_update_{business['id']}",
                type="primary",
            ):
                errors = _validate_business_payload(
                    business_name=edit_name,
                    first_name=edit_first,
                    last_name=edit_last,
                    society_id=edit_society_id,
                    tower_id=edit_tower_id,
                    flat_number=edit_flat,
                    whatsapp_group_link=edit_wa_group,
                )
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    payload = {
                        "business_name": edit_name.strip(),
                        "first_name": edit_first.strip(),
                        "last_name": edit_last.strip(),
                        "description": edit_desc.strip() or None,
                        "phone": edit_phone.strip() or None,
                        "whatsapp_number": edit_wa.strip() or None,
                        "whatsapp_group_link": edit_wa_group.strip() or None,
                        "timing": edit_timing.strip() or None,
                        "week_off": edit_week_off,
                        "society_id": edit_society_id,
                        "tower_id": edit_tower_id,
                        "flat_number": edit_flat.strip(),
                        "updated_at": _utc_now_iso(),
                    }
                    if not admin:
                        payload["status"] = STATUS_PENDING
                    try:
                        client.table("local_businesses").update(payload).eq(
                            "id", business["id"]
                        ).execute()
                        if admin:
                            st.success("Business updated.")
                        else:
                            st.success(
                                "Changes submitted for admin approval."
                            )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not update: {exc}")
            if c2.button(
                "Delete",
                key=f"{key_prefix}_delete_{business['id']}",
            ):
                try:
                    client.table("local_businesses").delete().eq(
                        "id", business["id"]
                    ).execute()
                    st.success("Business deleted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not delete: {exc}")
