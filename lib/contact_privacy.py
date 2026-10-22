from __future__ import annotations

HIDDEN_CONTACT = "Hidden"


def format_visible_contact(
    value: str | None,
    *,
    masked: bool = False,
    viewer_is_admin: bool = False,
    viewer_is_owner: bool = False,
) -> str:
    """Show a phone or WhatsApp number, or hide it from other members."""
    text = (value or "").strip()
    if viewer_is_admin or viewer_is_owner:
        if text and masked and viewer_is_admin and not viewer_is_owner:
            return f"{text} (hidden from other members)"
        return text or "—"
    if masked and text:
        return HIDDEN_CONTACT
    return text or "—"
