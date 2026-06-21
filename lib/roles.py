from __future__ import annotations

# Stored in DB as `resident`; displayed in the UI as "Owner".
ROLE_OWNER = "resident"
ROLE_TENANT = "tenant"

SIGNUP_ROLES = [ROLE_OWNER, ROLE_TENANT]


def role_label(role: str | None) -> str:
    if role == ROLE_OWNER:
        return "Owner"
    if role == ROLE_TENANT:
        return "Tenant"
    if role == "admin":
        return "Admin"
    return (role or "").replace("_", " ").title()


def is_owner(role: str | None) -> bool:
    return role == ROLE_OWNER
