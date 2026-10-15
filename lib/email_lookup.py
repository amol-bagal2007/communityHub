from __future__ import annotations

from lib.supabase_client import SchemaClient

EMAIL_NOT_REGISTERED_MSG = (
    "This email ID does not exist in CommunityHub. "
    "Please contact the Admin user (open the Contact tab) for help."
)


def email_exists(client: SchemaClient, email: str) -> bool | None:
    """
    Return True/False if the email is registered, or None if the check failed
    (e.g. migration 029 not applied yet).
    """
    clean = (email or "").strip().lower()
    if not clean or "@" not in clean:
        return False
    try:
        result = client.raw.rpc("email_exists", {"p_email": clean}).execute().data
        if isinstance(result, bool):
            return result
        if isinstance(result, list) and result:
            return bool(result[0])
        return bool(result)
    except Exception:
        try:
            rows = (
                client.table("profiles")
                .select("id")
                .eq("email", clean)
                .limit(1)
                .execute()
                .data
                or []
            )
            return bool(rows)
        except Exception:
            return None
