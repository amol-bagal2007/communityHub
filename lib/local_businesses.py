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
    whatsapp_number: str,
    whatsapp_group_link: str,
) -> list[str]:
    errors: list[str] = []
    if not business_name.strip():
        errors.append("Business name is required.")
    link = (whatsapp_group_link or "").strip()
    if link and not (link.startswith("http://") or link.startswith("https://")):
        errors.append("WhatsApp group link should start with https://")
    _ = whatsapp_number  # optional free text
    return errors


def render_local_businesses(
    client: SchemaClient,
    profile: dict,
    *,
    admin: bool = False,
    societies: list[dict] | None = None,
) -> None:
    """Shared Local Business UI for members and admin."""
    st.subheader("Local Business")
    society_id = profile.get("society_id")
    user_id = profile.get("id")
    key_prefix = "admin_local_biz" if admin else "user_local_biz"

    if admin:
        soc_map = {s["name"]: s["id"] for s in (societies or [])}
    elif not society_id:
        st.info("No society linked to your profile.")
        return
    else:
        soc_map = {}

    with st.expander("Add a Local Business"):
        add_society_id = society_id
        if admin:
            society_name = st.selectbox(
                "Society *",
                options=[""] + list(soc_map.keys()),
                format_func=lambda value: "Select society..." if value == "" else value,
                key=f"{key_prefix}_add_society",
            )
            add_society_id = soc_map.get(society_name)

        business_name = st.text_input("Business Name *", key=f"{key_prefix}_add_name")
        description = st.text_area("Business Description", key=f"{key_prefix}_add_desc")
        whatsapp_number = st.text_input(
            "Personal WhatsApp Number",
            key=f"{key_prefix}_add_wa",
            help="Include country code if possible, e.g. 9198xxxxxxxx",
        )
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
                whatsapp_number=whatsapp_number,
                whatsapp_group_link=whatsapp_group_link,
            )
            if admin and not add_society_id:
                errors.append("Select a society.")
            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    client.table("local_businesses").insert(
                        {
                            "business_name": business_name.strip(),
                            "description": description.strip() or None,
                            "whatsapp_number": whatsapp_number.strip() or None,
                            "whatsapp_group_link": whatsapp_group_link.strip() or None,
                            "timing": timing.strip() or None,
                            "week_off": week_off,
                            "society_id": add_society_id,
                            "added_by": user_id,
                        }
                    ).execute()
                    st.success("Local business added.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not add business (run migration 026): {exc}")

    query = (
        client.table("local_businesses")
        .select("*, profiles(first_name, last_name), societies(name)")
        .order("business_name")
    )
    if not admin:
        query = query.eq("society_id", society_id)
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

        with st.container(border=True):
            summary_col, action_col = st.columns([5, 1])
            title = f"**{business.get('business_name') or 'Business'}**"
            if admin and society_name:
                title += f" — {society_name}"
            summary_col.markdown(title)
            summary_col.caption(rating_caption(summary))
            if action_col.button(
                "Hide" if st.session_state.get(open_key) else "View",
                key=f"{key_prefix}_view_{business['id']}",
                use_container_width=True,
            ):
                st.session_state[open_key] = not st.session_state.get(open_key, False)
                st.rerun()

            if not st.session_state.get(open_key):
                continue

            st.caption(f"Added by {added_by}")
            if business.get("description"):
                st.write(business["description"])
            if business.get("whatsapp_number"):
                st.write(f"WhatsApp: {business['whatsapp_number']}")
            if business.get("whatsapp_group_link"):
                st.markdown(
                    f"[WhatsApp Group Link]({business['whatsapp_group_link']})"
                )
            if business.get("timing"):
                st.write(f"Timing: {business['timing']}")
            if business.get("week_off"):
                st.write(f"Week off: {business['week_off']}")
            else:
                st.write("Week off: —")

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
            edit_wa = st.text_input(
                "Personal WhatsApp Number",
                value=business.get("whatsapp_number") or "",
                key=f"{key_prefix}_edit_wa_{business['id']}",
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
                    whatsapp_number=edit_wa,
                    whatsapp_group_link=edit_wa_group,
                )
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    try:
                        client.table("local_businesses").update(
                            {
                                "business_name": edit_name.strip(),
                                "description": edit_desc.strip() or None,
                                "whatsapp_number": edit_wa.strip() or None,
                                "whatsapp_group_link": edit_wa_group.strip() or None,
                                "timing": edit_timing.strip() or None,
                                "week_off": edit_week_off,
                                "updated_at": _utc_now_iso(),
                            }
                        ).eq("id", business["id"]).execute()
                        st.success("Business updated.")
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
