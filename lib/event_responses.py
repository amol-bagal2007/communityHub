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


def render_response_summary(responses: list[dict]) -> None:
    import streamlit as st

    summary = summarize_responses(responses)
    st.markdown("**Society responses**")
    st.caption(
        f"Interested: {len(summary['interested'])} · "
        f"Not Interested: {len(summary['not_interested'])} · "
        f"Contributors: {len(summary['contributors'])} · "
        f"Volunteers: {len(summary['volunteers'])}"
    )
    if summary["contributors"]:
        st.write("Contributors: " + ", ".join(summary["contributors"]))
    if summary["volunteers"]:
        st.write("Volunteers: " + ", ".join(summary["volunteers"]))
    if summary["not_interested"]:
        st.write("Not Interested: " + ", ".join(summary["not_interested"]))
    if not responses:
        st.caption("No responses yet.")
