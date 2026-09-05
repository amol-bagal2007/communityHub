from __future__ import annotations

from lib.supabase_client import SchemaClient, get_service_client
from lib.validation import validate_password


def admin_reset_user_password(user_id: str, new_password: str) -> str | None:
    """
    Set a new password for a user via the service-role Admin API.
    Returns an error message, or None on success.
    """
    pwd_error = validate_password(new_password)
    if pwd_error:
        return pwd_error
    if not user_id:
        return "User id is required."

    try:
        svc = get_service_client()
        svc.raw.auth.admin.update_user_by_id(
            user_id,
            {"password": new_password},
        )
    except Exception as exc:
        return f"Could not reset password: {exc}"
    return None
