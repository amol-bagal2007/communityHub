from __future__ import annotations

import math
import re
from datetime import date, datetime, time

import streamlit as st

from lib.password_reset_requests import whatsapp_chat_url
from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient
from lib.validation import MOBILE_HELP, MOBILE_PLACEHOLDER, validate_mobile_number

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
ROUTINES = ("daily", "weekly", "monthly")
RIDE_NOTE = (
    "Connect with the driver on the WhatsApp number to confirm the ride. "
    "Use Open WhatsApp next to the number."
)

_OFFER_COLUMNS_LEGACY = (
    "id, added_by, society_id, routine, week_days, month_day, from_place, to_place, "
    "travel_time, car_details, available_seats, charge_mode, charges, whatsapp_number, "
    "restrictions, pickup_point, drop_point, created_at"
)
_OFFER_COLUMNS = _OFFER_COLUMNS_LEGACY.replace(
    "whatsapp_number, ",
    "whatsapp_number, group_whatsapp_link, ",
)
_GROUP_LINK_RE = re.compile(
    r"^https?://(?:chat\.whatsapp\.com|wa\.me|whatsapp\.com)/[^\s]+$",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _parse_time(value: str | time | None) -> time | None:
    if isinstance(value, time):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _format_clock(value: str | time | None) -> str:
    parsed = _parse_time(value)
    if not parsed:
        return "—"
    return parsed.strftime("%I:%M %p").lstrip("0")


def _decode_days(value: str | None) -> list[str]:
    if not value:
        return []
    parts = {part.strip() for part in value.split(",")}
    return [day for day in WEEK_DAYS if day in parts]


def _encode_days(days: list[str]) -> str | None:
    selected = [day for day in WEEK_DAYS if day in days]
    return ", ".join(selected) if selected else None


def offer_runs_on(offer: dict, ride_day: date) -> bool:
    routine = offer.get("routine")
    if routine == "daily":
        return True
    if routine == "weekly":
        return WEEK_DAYS[ride_day.weekday()] in _decode_days(offer.get("week_days"))
    if routine == "monthly":
        try:
            return ride_day.day == int(offer.get("month_day") or 0)
        except (TypeError, ValueError):
            return False
    return False


def routine_label(offer: dict) -> str:
    routine = offer.get("routine") or ""
    if routine == "daily":
        return "Daily"
    if routine == "weekly":
        days = ", ".join(_decode_days(offer.get("week_days"))) or "—"
        return f"Weekly · {days}"
    if routine == "monthly":
        return f"Monthly · day {offer.get('month_day') or '—'}"
    return routine.title()


def charge_label(offer: dict) -> str:
    if offer.get("charge_mode") == "paid":
        amount = offer.get("charges")
        return f"Paid · {amount}" if amount is not None else "Paid"
    return "Free"


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _text_score(query: str, actual: str) -> float:
    left = _norm(query)
    right = _norm(actual)
    if not left:
        return 1.0
    if not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.85
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _time_score(prefer: time, actual: str | time | None) -> float:
    parsed = _parse_time(actual)
    if not parsed:
        return 0.0
    diff = abs(
        (prefer.hour * 60 + prefer.minute) - (parsed.hour * 60 + parsed.minute)
    )
    if diff <= 15:
        return 1.0
    if diff <= 30:
        return 0.8
    if diff <= 60:
        return 0.55
    if diff <= 120:
        return 0.25
    return 0.05


def _best_place_score(query: str, actuals: list[str]) -> float:
    return max(_text_score(query, actual) for actual in actuals)


def match_percent(
    offer: dict,
    *,
    from_query: str,
    to_query: str,
    pickup_query: str,
    drop_query: str,
    prefer_time: time | None = None,
) -> int | None:
    """Score From, To, pickup, drop, and travel time. Each filled place uses the closer matching field."""
    origin = [offer.get("from_place") or "", offer.get("pickup_point") or ""]
    destination = [offer.get("to_place") or "", offer.get("drop_point") or ""]
    scores: list[float] = []
    for query, actuals in (
        (from_query, origin),
        (pickup_query, origin),
        (to_query, destination),
        (drop_query, destination),
    ):
        if query.strip():
            scores.append(_best_place_score(query, actuals))
    if prefer_time is not None:
        scores.append(_time_score(prefer_time, offer.get("travel_time")))
    if not scores:
        return None
    return round(100 * sum(scores) / len(scores))


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
        f"(page {current} of {total_pages})"
    )
    if total_pages > 1:
        prev_col, next_col = st.columns(2)
        if prev_col.button(
            "← Previous",
            key=f"{key_prefix}_prev",
            disabled=current <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = current - 1
            st.rerun()
        if next_col.button(
            "Next →",
            key=f"{key_prefix}_next",
            disabled=current >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = current + 1
            st.rerun()
    return rows[start : start + PAGE_SIZE]


def _normalize_group_link(value: str) -> tuple[str | None, str | None]:
    text = value.strip()
    if not text:
        return None, None
    if not text.lower().startswith(("http://", "https://")):
        text = "https://" + text
    if not _GROUP_LINK_RE.match(text):
        return None, "Enter a WhatsApp group link, such as https://chat.whatsapp.com/..."
    return text, None


def _load_offers(client: SchemaClient, *, admin: bool, society_id: str | None) -> tuple[list[dict], str | None]:
    selects = [_OFFER_COLUMNS, _OFFER_COLUMNS_LEGACY]
    if admin:
        selects = [
            columns
            + ", profiles(first_name, last_name, title, phone, email, flat_number, societies(name), towers(name))"
            for columns in selects
        ] + selects
    last_error = "Could not load rides."
    for columns in selects:
        try:
            query = client.table("ride_offers").select(columns)
            if not admin and society_id:
                query = query.eq("society_id", society_id)
            rows = query.order("created_at", desc=True).execute().data or []
            return rows, None
        except Exception as exc:
            last_error = str(exc)
            lowered = last_error.lower()
            if "group_whatsapp_link" in lowered:
                continue
            if "ride_offers" in lowered and (
                "does not exist" in lowered
                or "schema cache" in lowered
                or "pgrst205" in lowered
            ):
                return [], "Share a Ride is unavailable. Run Supabase migration 038, then refresh."
    return [], f"Could not load rides: {last_error}"


def _load_requests_for_offers(client: SchemaClient, offer_ids: list[str]) -> list[dict]:
    if not offer_ids:
        return []
    try:
        return (
            client.table("ride_requests")
            .select(
                "id, offer_id, requester_id, ride_date, status, "
                "profiles!ride_requests_requester_id_fkey(first_name, last_name, title)"
            )
            .in_("offer_id", offer_ids)
            .execute()
            .data
            or []
        )
    except Exception:
        try:
            return (
                client.table("ride_requests")
                .select("id, offer_id, requester_id, ride_date, status")
                .in_("offer_id", offer_ids)
                .execute()
                .data
                or []
            )
        except Exception:
            return []


def _whatsapp_line(number: str | None, *, show_link: bool = False) -> None:
    text = (number or "").strip()
    if not text:
        st.write("WhatsApp: —")
        return
    if not show_link:
        st.write(f"WhatsApp: {text}")
        return
    url = whatsapp_chat_url(text)
    label_col, link_col = st.columns([2, 1])
    label_col.write(f"WhatsApp: {text}")
    if url.endswith("/") or not url.rsplit("/", 1)[-1]:
        link_col.caption("Add a valid number")
        return
    link_col.link_button("Open WhatsApp", url, use_container_width=True)


def _group_link_line(link: str | None, *, show_join: bool) -> None:
    text = (link or "").strip()
    if not text:
        return
    if not show_join:
        st.write(f"Group WhatsApp: {text}")
        return
    label_col, link_col = st.columns([2, 1])
    label_col.write(f"Group WhatsApp: {text}")
    link_col.link_button("Join group", text, use_container_width=True)


def _offer_summary(offer: dict, *, percent: int | None = None) -> None:
    route = f"{offer.get('from_place') or '—'} → {offer.get('to_place') or '—'}"
    if percent is None:
        st.markdown(f"**{route}**")
    else:
        st.markdown(f"**{route}** · Match {percent}%")
    st.caption(
        f"{routine_label(offer)} · Departs {_format_clock(offer.get('travel_time'))} · "
        f"{charge_label(offer)} · Seats {offer.get('available_seats') or '—'}"
    )
    st.write(f"Car: {offer.get('car_details') or '—'}")
    st.write(
        f"Pickup: {offer.get('pickup_point') or '—'} · "
        f"Drop: {offer.get('drop_point') or '—'}"
    )
    if offer.get("restrictions"):
        st.write(f"Restrictions: {offer['restrictions']}")


def _delete_offer(client: SchemaClient, offer_id: str) -> None:
    try:
        deleted = (
            client.table("ride_offers").delete().eq("id", offer_id).execute().data or []
        )
        if not deleted:
            still_there = (
                client.table("ride_offers")
                .select("id")
                .eq("id", offer_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if still_there:
                st.error(
                    "This ride was not deleted. Run Supabase migration 040, then try again."
                )
                return
        st.success("Ride offer deleted.")
        st.rerun()
    except Exception as exc:
        text = str(exc).lower()
        if "ride_requests" in text or "row-level security" in text:
            st.error(
                "Could not delete this ride. Run Supabase migration 040, then try again."
            )
            return
        st.error(f"Could not delete this ride: {exc}")


def _render_offer_form(client: SchemaClient, profile: dict) -> None:
    st.markdown("**Offer a ride**")
    st.caption("Add the routine you drive. Other members can request a seat for a specific day.")
    routine = st.selectbox(
        "How often",
        ROUTINES,
        format_func=lambda value: value.title(),
        key="share_ride_routine",
    )
    week_days: list[str] = []
    month_day = None
    if routine == "weekly":
        st.caption("Travel days")
        chosen: list[str] = []
        cols = st.columns(2)
        for index, day in enumerate(WEEK_DAYS):
            if cols[index % 2].checkbox(day, key=f"share_ride_day_{day}"):
                chosen.append(day)
        week_days = chosen
    elif routine == "monthly":
        month_day = int(
            st.number_input(
                "Day of the month",
                min_value=1,
                max_value=31,
                value=1,
                step=1,
                key="share_ride_month_day",
            )
        )

    from_place = st.text_input("From", key="share_ride_from", placeholder="Starting area")
    to_place = st.text_input("To", key="share_ride_to", placeholder="Destination")
    travel_time = st.time_input("Travel time", value=time(8, 0), key="share_ride_time")
    pickup_point = st.text_input("Pickup point", key="share_ride_pickup")
    drop_point = st.text_input("Drop point", key="share_ride_drop")
    car_details = st.text_input(
        "Car details",
        key="share_ride_car",
        placeholder="Example: White Swift, MH12 AB 1234",
    )
    seats = int(
        st.number_input(
            "Available seats",
            min_value=1,
            max_value=8,
            value=1,
            step=1,
            key="share_ride_seats",
        )
    )
    charge_mode = st.radio(
        "Ride charges",
        ("free", "paid"),
        format_func=lambda value: "Free" if value == "free" else "Charges",
        horizontal=True,
        key="share_ride_charge_mode",
    )
    charges = None
    if charge_mode == "paid":
        charges = st.number_input(
            "Charges",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="share_ride_charges",
        )
    whatsapp = st.text_input(
        "WhatsApp number",
        key="share_ride_whatsapp",
        placeholder=MOBILE_PLACEHOLDER,
        help=MOBILE_HELP,
    )
    group_link = st.text_input(
        "Group WhatsApp link",
        key="share_ride_group_link",
        placeholder="https://chat.whatsapp.com/...",
        help="Optional. Passengers can open this link to join the ride group.",
    )
    restrictions = st.text_area(
        "Any restriction in the car",
        key="share_ride_restrictions",
        placeholder="Example: No smoking, one bag each",
    )
    if st.button("Save ride offer", type="primary", key="share_ride_save"):
        errors: list[str] = []
        if routine == "weekly" and not week_days:
            errors.append("Select at least one travel day.")
        if not from_place.strip() or not to_place.strip():
            errors.append("From and To are required.")
        if not pickup_point.strip() or not drop_point.strip():
            errors.append("Pickup point and drop point are required.")
        if not car_details.strip():
            errors.append("Car details are required.")
        if charge_mode == "paid" and (charges is None or float(charges) <= 0):
            errors.append("Enter the ride charges.")
        whatsapp_error = validate_mobile_number(
            whatsapp, required=True, label="WhatsApp number"
        )
        if whatsapp_error:
            errors.append(whatsapp_error)
        group_url, group_error = _normalize_group_link(group_link)
        if group_error:
            errors.append(group_error)
        if not profile.get("society_id"):
            errors.append("Your profile needs a society before you can offer a ride.")
        if errors:
            for err in errors:
                st.error(err)
            return
        try:
            client.table("ride_offers").insert(
                {
                    "added_by": profile["id"],
                    "society_id": profile.get("society_id"),
                    "routine": routine,
                    "week_days": _encode_days(week_days),
                    "month_day": month_day,
                    "from_place": from_place.strip(),
                    "to_place": to_place.strip(),
                    "travel_time": travel_time.strftime("%H:%M:%S"),
                    "car_details": car_details.strip(),
                    "available_seats": seats,
                    "charge_mode": charge_mode,
                    "charges": float(charges) if charge_mode == "paid" else None,
                    "whatsapp_number": whatsapp.strip(),
                    "group_whatsapp_link": group_url,
                    "restrictions": restrictions.strip() or None,
                    "pickup_point": pickup_point.strip(),
                    "drop_point": drop_point.strip(),
                }
            ).execute()
            st.success("Ride offer saved. It is now visible under Share a Ride.")
            st.rerun()
        except Exception as exc:
            hint = ""
            if "group_whatsapp_link" in str(exc):
                hint = " Run Supabase migration 039, then try again."
            st.error(f"Could not save the ride:{hint} {exc}")


def _render_my_offers(
    client: SchemaClient,
    offers: list[dict],
    requests: list[dict],
    *,
    admin: bool,
) -> None:
    st.markdown("**Your offered rides**" if not admin else "**Offered rides**")
    grouped: dict[str, list[dict]] = {}
    for row in requests:
        grouped.setdefault(row.get("offer_id"), []).append(row)
    for offer in _page(
        offers,
        key_prefix="share_ride_mine" if not admin else "share_ride_admin",
        empty="No ride offers yet." if admin else "You have not offered a ride yet.",
    ):
        with st.container(border=True):
            _offer_summary(offer)
            _whatsapp_line(offer.get("whatsapp_number"))
            _group_link_line(offer.get("group_whatsapp_link"), show_join=False)
            if admin:
                driver = offer.get("profiles") or {}
                society = (driver.get("societies") or {}).get("name") if isinstance(driver, dict) else None
                tower = (driver.get("towers") or {}).get("name") if isinstance(driver, dict) else None
                st.markdown(
                    f"**Driver:** {format_name(driver if isinstance(driver, dict) else None, 'Member')}  \n"
                    f"**Phone:** {(driver.get('phone') if isinstance(driver, dict) else None) or '—'}  \n"
                    f"**Email:** {(driver.get('email') if isinstance(driver, dict) else None) or '—'}  \n"
                    f"**Society:** {society or '—'} · **Tower:** {tower or '—'} · "
                    f"**Flat:** {(driver.get('flat_number') if isinstance(driver, dict) else None) or '—'}"
                )
            if st.button("Delete", key=f"share_ride_delete_{offer['id']}"):
                _delete_offer(client, offer["id"])
            related = sorted(
                grouped.get(offer["id"], []),
                key=lambda row: str(row.get("ride_date") or ""),
            )
            if related:
                st.markdown("**Seat requests**")
                for req in related:
                    passenger = req.get("profiles") or {}
                    name = format_name(
                        passenger if isinstance(passenger, dict) else None,
                        "Passenger",
                    )
                    status = str(req.get("status") or "pending").title()
                    st.write(f"{name} · {req.get('ride_date')} · {status}")
                    if req.get("status") != "pending":
                        continue
                    accept_col, reject_col = st.columns(2)
                    if accept_col.button(
                        "Accept",
                        key=f"share_ride_accept_{req['id']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        _respond(client, req["id"], "approved")
                    if reject_col.button(
                        "Reject",
                        key=f"share_ride_reject_{req['id']}",
                        use_container_width=True,
                    ):
                        _respond(client, req["id"], "rejected")


def _respond(client: SchemaClient, request_id: str, status: str) -> None:
    try:
        client.table("ride_requests").update(
            {"status": status, "updated_at": _utc_now_iso()}
        ).eq("id", request_id).execute()
        st.success("Request accepted." if status == "approved" else "Request rejected.")
        st.rerun()
    except Exception as exc:
        text = str(exc)
        if "No seats left" in text:
            st.error("No seats left for that day.")
        else:
            st.error(f"Could not update the request: {exc}")


def _request_seat(
    client: SchemaClient,
    *,
    offer_id: str,
    user_id: str,
    ride_day: date,
    existing: dict | None,
) -> None:
    try:
        if existing and existing.get("status") == "rejected":
            client.table("ride_requests").update(
                {"status": "pending", "updated_at": _utc_now_iso()}
            ).eq("id", existing["id"]).execute()
        elif existing:
            st.info(f"You already have a {existing.get('status')} request for this day.")
            return
        else:
            client.table("ride_requests").insert(
                {
                    "offer_id": offer_id,
                    "requester_id": user_id,
                    "ride_date": ride_day.isoformat(),
                    "status": "pending",
                }
            ).execute()
        st.success("Request sent. The driver can accept or reject it.")
        st.rerun()
    except Exception as exc:
        text = str(exc)
        if "does not run" in text:
            st.error("This ride does not operate on the selected day.")
        elif "No seats left" in text:
            st.error("No seats left for that day.")
        elif "own ride" in text:
            st.error("You cannot request your own ride.")
        else:
            st.error(f"Could not send the request: {exc}")


def _render_find(
    client: SchemaClient,
    profile: dict,
    offers: list[dict],
) -> None:
    st.markdown("**Find a ride**")
    st.info(RIDE_NOTE)
    with st.form("share_ride_find"):
        filter_day = st.checkbox("Search a specific day", key="share_ride_filter_day")
        ride_day = st.date_input("Day", key="share_ride_filter_date")
        from_query = st.text_input("From", key="share_ride_filter_from")
        pickup_query = st.text_input("Pickup point", key="share_ride_filter_pickup")
        to_query = st.text_input("To", key="share_ride_filter_to")
        drop_query = st.text_input("Drop point", key="share_ride_filter_drop")
        use_time = st.checkbox(
            "Include travel time in the match",
            key="share_ride_filter_use_time",
        )
        prefer_time = st.time_input(
            "Preferred travel time",
            value=time(8, 0),
            key="share_ride_filter_time",
        )
        searched = st.form_submit_button(
            "Search rides",
            type="primary",
            use_container_width=True,
        )

    if searched:
        st.session_state["share_ride_filters"] = {
            "day": ride_day.isoformat() if filter_day and isinstance(ride_day, date) else None,
            "from": from_query.strip(),
            "pickup": pickup_query.strip(),
            "to": to_query.strip(),
            "drop": drop_query.strip(),
            "time": prefer_time.strftime("%H:%M:%S") if use_time else None,
        }
        st.session_state["share_ride_find_page"] = 1

    filters = st.session_state.get("share_ride_filters") or {}
    day_value = filters.get("day")
    selected_day = date.fromisoformat(day_value) if day_value else None
    prefer = _parse_time(filters.get("time"))
    user_id = profile.get("id")
    visible = [offer for offer in offers if offer.get("added_by") != user_id]
    if selected_day:
        visible = [offer for offer in visible if offer_runs_on(offer, selected_day)]

    scored: list[tuple[int | None, dict]] = []
    for offer in visible:
        percent = match_percent(
            offer,
            from_query=filters.get("from") or "",
            to_query=filters.get("to") or "",
            pickup_query=filters.get("pickup") or "",
            drop_query=filters.get("drop") or "",
            prefer_time=prefer,
        )
        scored.append((percent, offer))
    if any(percent is not None for percent, _offer in scored):
        scored.sort(
            key=lambda item: (
                -(item[0] or 0),
                -(_time_score(prefer, item[1].get("travel_time")) if prefer else 0),
                str(item[1].get("travel_time") or ""),
            )
        )
        st.caption(
            "Rides are sorted by how closely From, To, pickup point, drop point, and travel time match your search."
        )

    page_rows = _page(
        [offer for _percent, offer in scored],
        key_prefix="share_ride_find",
        empty="No rides match this search.",
    )
    percent_by_id = {offer["id"]: percent for percent, offer in scored}
    mine = {
        (row.get("offer_id"), str(row.get("ride_date"))): row
        for row in _load_requests_for_offers(client, [offer["id"] for offer in page_rows])
        if row.get("requester_id") == user_id
    }
    for offer in page_rows:
        with st.container(border=True):
            _offer_summary(offer, percent=percent_by_id.get(offer["id"]))
            _whatsapp_line(offer.get("whatsapp_number"), show_link=True)
            _group_link_line(offer.get("group_whatsapp_link"), show_join=True)
            request_day = selected_day or date.today()
            if not selected_day:
                request_day = st.date_input(
                    "Request date",
                    value=date.today(),
                    key=f"share_ride_req_date_{offer['id']}",
                )
            if not offer_runs_on(offer, request_day):
                st.caption("This ride does not run on the selected day.")
                continue
            existing = mine.get((offer["id"], request_day.isoformat()))
            if existing and existing.get("status") != "rejected":
                st.caption(f"Your request: {str(existing.get('status')).title()}")
            elif st.button(
                "Request this day",
                key=f"share_ride_request_{offer['id']}_{request_day.isoformat()}",
                use_container_width=True,
            ):
                _request_seat(
                    client,
                    offer_id=offer["id"],
                    user_id=user_id,
                    ride_day=request_day,
                    existing=existing,
                )


def render_share_ride(client: SchemaClient, profile: dict, *, admin: bool = False) -> None:
    st.subheader("Share a Ride")
    offers, error = _load_offers(
        client,
        admin=admin,
        society_id=profile.get("society_id"),
    )
    if error:
        st.warning(error)
        return

    user_id = profile.get("id")
    mine = offers if admin else [offer for offer in offers if offer.get("added_by") == user_id]
    requests = _load_requests_for_offers(client, [offer["id"] for offer in mine]) if mine else []
    _render_my_offers(client, mine, requests, admin=admin)

    if admin:
        return

    st.divider()
    choice = st.radio(
        "Share a Ride options",
        ("Offer a ride", "Find a ride"),
        horizontal=True,
        key="share_ride_choice",
    )
    if choice == "Offer a ride":
        _render_offer_form(client, profile)
    else:
        _render_find(client, profile, offers)
