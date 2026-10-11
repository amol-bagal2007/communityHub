from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

import streamlit as st

from lib.profile_utils import format_name
from lib.supabase_client import SchemaClient

RATING_OPTIONS = [1, 2, 3, 4, 5]
RATING_LABELS = {
    1: "1 — Poor",
    2: "2 — Fair",
    3: "3 — Average",
    4: "4 — Good",
    5: "5 — Excellent",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_rating_review(rating: int | None, review: str) -> list[str]:
    errors: list[str] = []
    if rating is None or rating not in RATING_OPTIONS:
        errors.append("Business rating is required (1 = Poor … 5 = Excellent).")
    if not (review or "").strip():
        errors.append("Review is required when adding a rating.")
    return errors


def load_business_ratings(client: SchemaClient, business_ids: list[str]) -> list[dict]:
    if not business_ids:
        return []
    return (
        client.table("local_business_ratings")
        .select("*, profiles(first_name, last_name, title)")
        .in_("business_id", business_ids)
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )


def summarize_business_ratings(ratings: list[dict]) -> dict[str, dict]:
    by_business: dict[str, dict] = defaultdict(
        lambda: {"ratings": [], "avg": None, "rating_count": 0}
    )
    for row in ratings:
        business_id = row.get("business_id")
        if not business_id:
            continue
        by_business[business_id]["ratings"].append(row)
    for business_id, data in by_business.items():
        scores = [
            int(r["rating"]) for r in data["ratings"] if r.get("rating") is not None
        ]
        data["rating_count"] = len(scores)
        data["avg"] = round(sum(scores) / len(scores), 1) if scores else None
    return by_business


def rating_caption(summary: dict | None) -> str:
    if not summary or summary.get("avg") is None:
        return "⭐ No ratings yet"
    count = summary.get("rating_count") or 0
    return (
        f"⭐ {summary['avg']}/5 "
        f"({count} review{'s' if count != 1 else ''})"
    )


def upsert_business_rating(
    client: SchemaClient,
    *,
    business_id: str,
    user_id: str,
    rating: int,
    review: str,
) -> str | None:
    errors = validate_rating_review(rating, review)
    if errors:
        return "; ".join(errors)
    review_clean = review.strip()
    existing = (
        client.table("local_business_ratings")
        .select("id")
        .eq("business_id", business_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    try:
        if existing:
            client.table("local_business_ratings").update(
                {
                    "rating": int(rating),
                    "review": review_clean,
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", existing[0]["id"]).execute()
        else:
            client.table("local_business_ratings").insert(
                {
                    "business_id": business_id,
                    "user_id": user_id,
                    "rating": int(rating),
                    "review": review_clean,
                }
            ).execute()
    except Exception as exc:
        return f"Could not save rating: {exc}"
    return None


def find_my_rating(ratings: list[dict], user_id: str) -> dict | None:
    for row in ratings:
        if row.get("user_id") == user_id:
            return row
    return None


def render_business_reviews(ratings: list[dict]) -> None:
    if not ratings:
        st.caption("No reviews yet.")
        return
    st.markdown("**Reviews**")
    for row in ratings:
        name = format_name(row.get("profiles"), "Member")
        st.write(f"**{name}** — {row.get('rating')}/5")
        st.write(row.get("review") or "")
        st.caption(str(row.get("updated_at") or row.get("created_at") or "")[:19])


def render_business_rating_form(
    client: SchemaClient,
    *,
    business_id: str,
    user_id: str,
    existing: dict | None,
    key_prefix: str,
) -> None:
    st.markdown("**Rate this business**")
    with st.form(f"{key_prefix}_rating_form"):
        current_rating = (
            int(existing["rating"]) if existing and existing.get("rating") else 5
        )
        rating = st.selectbox(
            "Rating *",
            RATING_OPTIONS,
            index=RATING_OPTIONS.index(current_rating),
            format_func=lambda value: RATING_LABELS[value],
            help="1 = Poor, 5 = Excellent",
        )
        review = st.text_area(
            "Review *",
            value=(existing.get("review") if existing else "") or "",
            help="Required when submitting a rating.",
        )
        submitted = st.form_submit_button("Submit Rating & Review", type="primary")
    if submitted:
        err = upsert_business_rating(
            client,
            business_id=business_id,
            user_id=user_id,
            rating=rating,
            review=review,
        )
        if err:
            st.error(err)
        else:
            st.success("Thank you — rating and review saved.")
            st.rerun()
