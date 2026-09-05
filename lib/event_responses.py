from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient

INTEREST_INTERESTED = "interested"
INTEREST_NOT_INTERESTED = "not_interested"
ROLE_CONTRIBUTOR = "contributor"
ROLE_VOLUNTEER = "volunteer"

PARTICIPATION_ROLES = [ROLE_CONTRIBUTOR, ROLE_VOLUNTEER]


def interest_label(interest: str | None) -> str:
    if interest == INTEREST_INTERESTED:
        return "Interested"
    if interest == INTEREST_NOT_INTERESTED:
        return "Not Interested"
    return "—"


def role_label(role: str | None) -> str:
    if role == ROLE_CONTRIBUTOR:
        return "Contributor"
    if role == ROLE_VOLUNTEER:
        return "Volunteer"
    return "—"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_event_responses(client: SchemaClient, event_id: str) -> list[dict]:
    return (
        client.table("event_responses")
        .select("*, profiles(first_name, last_name, title)")
        .eq("event_id", event_id)
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )


def load_my_event_response(
    client: SchemaClient, event_id: str, user_id: str
) -> dict | None:
    result = (
        client.table("event_responses")
        .select("*")
        .eq("event_id", event_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return result[0] if result else None


def upsert_event_response(
    client: SchemaClient,
    *,
    event_id: str,
    user_id: str,
    interest: str,
    participation_role: str | None,
) -> None:
    existing = load_my_event_response(client, event_id, user_id)
    if existing:
        client.table("event_responses").update(
            {
                "interest": interest,
                "participation_role": participation_role,
                "updated_at": _utc_now_iso(),
            }
        ).eq("id", existing["id"]).execute()
    else:
        client.table("event_responses").insert(
            {
                "event_id": event_id,
                "user_id": user_id,
                "interest": interest,
                "participation_role": participation_role,
            }
        ).execute()


def summarize_responses(responses: list[dict]) -> dict[str, list[str]]:
    interested: list[str] = []
    not_interested: list[str] = []
    contributors: list[str] = []
    volunteers: list[str] = []

    for response in responses:
        name = format_name(response.get("profiles"), "Member")
        if response.get("interest") == INTEREST_INTERESTED:
            interested.append(name)
            if response.get("participation_role") == ROLE_CONTRIBUTOR:
                contributors.append(name)
            elif response.get("participation_role") == ROLE_VOLUNTEER:
                volunteers.append(name)
        elif response.get("interest") == INTEREST_NOT_INTERESTED:
            not_interested.append(name)

    return {
        "interested": interested,
        "not_interested": not_interested,
        "contributors": contributors,
        "volunteers": volunteers,
    }


def interest_counts(responses: list[dict]) -> dict[str, int]:
    summary = summarize_responses(responses)
    return {
        "interested": len(summary["interested"]),
        "not_interested": len(summary["not_interested"]),
        "contributors": len(summary["contributors"]),
        "volunteers": len(summary["volunteers"]),
        "total": len(responses),
    }


def interest_counts_caption(responses: list[dict]) -> str:
    counts = interest_counts(responses)
    return (
        f"Interested: {counts['interested']} · "
        f"Not Interested: {counts['not_interested']}"
    )


def render_response_summary(responses: list[dict]) -> None:
    import streamlit as st

    summary = summarize_responses(responses)
    interested_count = len(summary["interested"])
    not_interested_count = len(summary["not_interested"])

    st.markdown("**Response summary**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Interested", interested_count)
    c2.metric("Not Interested", not_interested_count)
    c3.metric("Total responses", len(responses))

    if not responses:
        st.caption("No responses submitted yet.")
        return

    if summary["interested"]:
        st.write(f"**Interested ({interested_count}):** " + ", ".join(summary["interested"]))
    if summary["not_interested"]:
        st.write(
            f"**Not Interested ({not_interested_count}):** "
            + ", ".join(summary["not_interested"])
        )
    if summary["contributors"]:
        st.write(
            f"**Contributors ({len(summary['contributors'])}):** "
            + ", ".join(summary["contributors"])
        )
    if summary["volunteers"]:
        st.write(
            f"**Volunteers ({len(summary['volunteers'])}):** "
            + ", ".join(summary["volunteers"])
        )
