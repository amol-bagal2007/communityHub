from __future__ import annotations

from datetime import datetime, timezone
from collections import defaultdict

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
        errors.append("Vendor Rating is required (1 = Poor … 5 = Excellent).")
    if not (review or "").strip():
        errors.append("Vendor Review is required when adding a rating.")
    return errors


def load_vendor_ratings(client: SchemaClient, vendor_ids: list[str]) -> list[dict]:
    if not vendor_ids:
        return []
    return (
        client.table("vendor_ratings")
        .select("*, profiles(first_name, last_name, title)")
        .in_("vendor_id", vendor_ids)
        .order("updated_at", desc=True)
        .execute()
        .data
        or []
    )


def load_vendor_recommendations(client: SchemaClient, vendor_ids: list[str]) -> list[dict]:
    if not vendor_ids:
        return []
    return (
        client.table("vendor_recommendations")
        .select("vendor_id, user_id")
        .in_("vendor_id", vendor_ids)
        .execute()
        .data
        or []
    )


def summarize_vendor_feedback(
    ratings: list[dict],
    recommendations: list[dict],
) -> dict[str, dict]:
    by_vendor: dict[str, dict] = defaultdict(
        lambda: {
            "ratings": [],
            "avg": None,
            "rating_count": 0,
            "recommend_count": 0,
            "recommender_ids": set(),
        }
    )
    for row in ratings:
        vendor_id = row.get("vendor_id")
        if not vendor_id:
            continue
        by_vendor[vendor_id]["ratings"].append(row)
    for vendor_id, data in by_vendor.items():
        scores = [int(r["rating"]) for r in data["ratings"] if r.get("rating") is not None]
        data["rating_count"] = len(scores)
        data["avg"] = round(sum(scores) / len(scores), 1) if scores else None

    for row in recommendations:
        vendor_id = row.get("vendor_id")
        user_id = row.get("user_id")
        if not vendor_id:
            continue
        by_vendor[vendor_id]["recommender_ids"].add(user_id)
        by_vendor[vendor_id]["recommend_count"] = len(
            by_vendor[vendor_id]["recommender_ids"]
        )
    return by_vendor


def feedback_caption(summary: dict | None) -> str:
    if not summary:
        return "⭐ No ratings yet · Recommended by 0 users"
    avg = summary.get("avg")
    rating_count = summary.get("rating_count") or 0
    recommend_count = summary.get("recommend_count") or 0
    if avg is None:
        rating_part = "⭐ No ratings yet"
    else:
        rating_part = f"⭐ {avg}/5 ({rating_count} review{'s' if rating_count != 1 else ''})"
    return f"{rating_part} · Recommended by {recommend_count} user{'s' if recommend_count != 1 else ''}"


def upsert_vendor_rating(
    client: SchemaClient,
    *,
    vendor_id: str,
    user_id: str,
    rating: int,
    review: str,
) -> str | None:
    errors = validate_rating_review(rating, review)
    if errors:
        return "; ".join(errors)
    review_clean = review.strip()
    existing = (
        client.table("vendor_ratings")
        .select("id")
        .eq("vendor_id", vendor_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    try:
        if existing:
            client.table("vendor_ratings").update(
                {
                    "rating": int(rating),
                    "review": review_clean,
                    "updated_at": _utc_now_iso(),
                }
            ).eq("id", existing[0]["id"]).execute()
        else:
            client.table("vendor_ratings").insert(
                {
                    "vendor_id": vendor_id,
                    "user_id": user_id,
                    "rating": int(rating),
                    "review": review_clean,
                }
            ).execute()
    except Exception as exc:
        return f"Could not save rating: {exc}"
    return None


def ensure_vendor_recommendation(
    client: SchemaClient,
    *,
    vendor_id: str,
    user_id: str,
) -> str | None:
    try:
        existing = (
            client.table("vendor_recommendations")
            .select("id")
            .eq("vendor_id", vendor_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            return None
        client.table("vendor_recommendations").insert(
            {"vendor_id": vendor_id, "user_id": user_id}
        ).execute()
    except Exception as exc:
        return f"Could not save recommendation: {exc}"
    return None


def user_has_recommended(
    summary: dict | None,
    user_id: str,
) -> bool:
    if not summary:
        return False
    return user_id in (summary.get("recommender_ids") or set())


def find_my_rating(ratings: list[dict], user_id: str) -> dict | None:
    for row in ratings:
        if row.get("user_id") == user_id:
            return row
    return None


def render_vendor_reviews(ratings: list[dict]) -> None:
    if not ratings:
        st.caption("No reviews yet.")
        return
    st.markdown("**Reviews**")
    for row in ratings:
        name = format_name(row.get("profiles"), "Member")
        st.write(f"**{name}** — {row.get('rating')}/5")
        st.write(row.get("review") or "")
        st.caption(str(row.get("updated_at") or row.get("created_at") or "")[:19])


def render_rating_form(
    client: SchemaClient,
    *,
    vendor_id: str,
    user_id: str,
    existing: dict | None,
    key_prefix: str,
) -> None:
    st.markdown("**Rate this vendor**")
    with st.form(f"{key_prefix}_rating_form"):
        current_rating = int(existing["rating"]) if existing and existing.get("rating") else 5
        rating = st.selectbox(
            "Vendor Rating *",
            RATING_OPTIONS,
            index=RATING_OPTIONS.index(current_rating),
            format_func=lambda value: RATING_LABELS[value],
            help="1 = Poor, 5 = Excellent",
        )
        review = st.text_area(
            "Vendor Review *",
            value=(existing.get("review") if existing else "") or "",
            help="Required when submitting a rating.",
        )
        submitted = st.form_submit_button("Submit Rating & Review", type="primary")
    if submitted:
        err = upsert_vendor_rating(
            client,
            vendor_id=vendor_id,
            user_id=user_id,
            rating=rating,
            review=review,
        )
        if err:
            st.error(err)
        else:
            st.success("Thank you — rating and review saved.")
            st.rerun()
