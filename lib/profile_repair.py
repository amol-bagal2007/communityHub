from __future__ import annotations

from typing import Any

from lib.supabase_client import SchemaClient, get_service_client


def _is_already_registered_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "already registered" in lowered
        or "user already exists" in lowered
        or "user_already_exists" in lowered
        or "email address is already registered" in lowered
    )


def try_repair_orphan_profile(
    client: SchemaClient,
    email: str,
    metadata: dict[str, Any],
) -> bool:
    """
    If auth user exists but profile row is missing, create the profile.
    Requires SUPABASE_SERVICE_ROLE_KEY on the server.
    """
    try:
        svc = get_service_client()
    except Exception:
        return False

    normalized_email = email.strip().lower()
    try:
        users = svc.raw.auth.admin.list_users()
        user_list = getattr(users, "users", None) or users
        auth_user = next(
            (
                u
                for u in user_list
                if (getattr(u, "email", "") or "").lower() == normalized_email
            ),
            None,
        )
        if not auth_user:
            return False

        user_id = auth_user.id
        existing = (
            svc.table("profiles").select("id").eq("id", user_id).limit(1).execute().data or []
        )
        if existing:
            return False

        role = metadata.get("role", "resident")
        profile = {
            "id": user_id,
            "email": email.strip(),
            "title": metadata.get("title", "Mr."),
            "first_name": metadata.get("first_name", ""),
            "last_name": metadata.get("last_name", ""),
            "sex": metadata.get("sex", "Male"),
            "age": int(metadata.get("age") or 18),
            "member_group_id": metadata.get("member_group_id"),
            "member_sub_group_id": metadata.get("member_sub_group_id"),
            "phone": metadata.get("phone"),
            "personal_whatsapp": metadata.get("personal_whatsapp"),
            "role": role,
            "society_id": metadata.get("society_id"),
            "tower_id": metadata.get("tower_id"),
            "flat_number": metadata.get("flat_number"),
            "status": "pending",
            "staying_within_society": bool(metadata.get("staying_within_society")),
            "tenant_expiry_date": metadata.get("tenant_expiry_date"),
            "parking_number": metadata.get("parking_number"),
            "parking_floor": metadata.get("parking_floor"),
            "parking_share_mode": metadata.get("parking_share_mode"),
            "parking_availability_value": metadata.get("parking_availability_value"),
            "parking_availability_unit": metadata.get("parking_availability_unit"),
            "parking_charges": metadata.get("parking_charges"),
            "bio": metadata.get("bio"),
            "group_interests": metadata.get("group_interests"),
            "disclaimer_accepted": bool(metadata.get("disclaimer_accepted")),
            "disclaimer_accepted_at": metadata.get("disclaimer_accepted_at"),
            "disclaimer_version": metadata.get("disclaimer_version"),
        }
        if profile.get("disclaimer_accepted") and not profile.get("disclaimer_accepted_at"):
            from datetime import datetime, timezone

            profile["disclaimer_accepted_at"] = datetime.now(timezone.utc).isoformat()
        svc.table("profiles").insert(profile).execute()
        return True
    except Exception:
        return False


def registration_error_message(exc: Exception, *, repaired: bool = False) -> str:
    if repaired:
        return (
            "Your account existed in authentication but was missing a profile. "
            "It has been repaired. Please log in with your email and password."
        )

    msg = str(exc)
    if _is_already_registered_error(msg):
        return (
            "This email is already registered. Try logging in, or use Forgot Password "
            "to reset your password. If you still cannot access your account, "
            "contact your society admin."
        )
    if "Email signups are disabled" in msg or "email_provider_disabled" in msg:
        return (
            "Registration is temporarily disabled on the server. "
            "Ask your society admin to enable email sign-ups in Supabase "
            "(Authentication → Providers → Email)."
        )
    if "Password should contain" in msg or "WeakPasswordError" in msg:
        return (
            "Password does not meet Supabase security rules. Use at least 7 characters "
            "with uppercase, lowercase, a number, and a symbol (e.g. `Pass@123`). "
            "Or ask your admin to relax rules under "
            "Authentication → Sign In / Providers → Email → Password settings."
        )
    if "title is required" in msg:
        return "Please select a title."
    if "staying_within_society" in msg:
        return "Owners must confirm that they are staying within the society."
    if "tenant_expiry_date" in msg:
        return "Tenant expiry date is required for tenant registrations."
    return f"Registration failed: {exc}"
