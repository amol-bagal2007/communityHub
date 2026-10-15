from __future__ import annotations

import re
from datetime import datetime, timezone

from lib.admin_password_reset import admin_reset_user_password
from lib.email_lookup import EMAIL_NOT_REGISTERED_MSG, email_exists
from lib.supabase_client import SchemaClient


STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


def normalize_whatsapp_number(value: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", (value or "").strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


def validate_whatsapp_number(value: str) -> str | None:
    cleaned = normalize_whatsapp_number(value)
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 10:
        return "Enter a valid WhatsApp mobile number (at least 10 digits)."
    if len(digits) > 15:
        return "WhatsApp number is too long."
    return None


def submit_password_reset_request(
    client: SchemaClient,
    *,
    email: str,
    whatsapp_number: str,
) -> str | None:
    """Create a pending admin password-reset request. Returns error or None."""
    email_clean = (email or "").strip().lower()
    if not email_clean or "@" not in email_clean:
        return "A valid email is required."
    wa_error = validate_whatsapp_number(whatsapp_number)
    if wa_error:
        return wa_error
    wa_clean = normalize_whatsapp_number(whatsapp_number)

    exists = email_exists(client, email_clean)
    if exists is False:
        return EMAIL_NOT_REGISTERED_MSG

    try:
        # SECURITY DEFINER RPC avoids anon RLS blocks on direct table insert.
        client.raw.rpc(
            "submit_password_reset_request",
            {
                "p_email": email_clean,
                "p_whatsapp": wa_clean,
            },
        ).execute()
    except Exception as exc:
        msg = str(exc)
        if "EMAIL_NOT_REGISTERED" in msg:
            return EMAIL_NOT_REGISTERED_MSG
        return f"Could not submit request: {exc}"
    return None


def load_pending_password_reset_requests(client: SchemaClient) -> list[dict]:
    return (
        client.table("password_reset_requests")
        .select(
            "*, profiles!password_reset_requests_profile_id_fkey"
            "(id, first_name, last_name, email, title)"
        )
        .eq("status", STATUS_PENDING)
        .order("created_at")
        .execute()
        .data
        or []
    )


def complete_password_reset_request(
    client: SchemaClient,
    *,
    request: dict,
    new_password: str,
    admin_id: str,
) -> str | None:
    """
    Reset Auth password for the matched user (or by email lookup) and mark request completed.
    """
    profile = request.get("profiles") or {}
    user_id = request.get("profile_id") or profile.get("id")
    email = (request.get("email") or "").strip().lower()

    if not user_id and email:
        rows = (
            client.table("profiles")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            user_id = rows[0]["id"]

    if not user_id:
        return (
            "No matching user found for this email. "
            "Confirm the email exists under Users, then try again."
        )

    err = admin_reset_user_password(user_id, new_password)
    if err:
        return err

    try:
        client.table("password_reset_requests").update(
            {
                "status": STATUS_COMPLETED,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "completed_by": admin_id,
                "profile_id": user_id,
            }
        ).eq("id", request["id"]).execute()
    except Exception as exc:
        return (
            f"Password was reset, but the request could not be marked completed: {exc}"
        )
    return None


def cancel_password_reset_request(
    client: SchemaClient,
    *,
    request_id: str,
    admin_id: str,
) -> str | None:
    try:
        client.table("password_reset_requests").update(
            {
                "status": STATUS_CANCELLED,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "completed_by": admin_id,
            }
        ).eq("id", request_id).execute()
    except Exception as exc:
        return f"Could not cancel request: {exc}"
    return None


def whatsapp_chat_url(whatsapp_number: str) -> str:
    digits = re.sub(r"\D", "", normalize_whatsapp_number(whatsapp_number))
    return f"https://wa.me/{digits}"
