"""Shared validation for persisted chat messages (used by all repository adapters)."""

_VALID_CHAT_ROLES = frozenset({"user", "assistant"})


def validate_chat_message_role(role: str) -> None:
    """
    Ensure ``role`` is allowed for stored chat messages.

    Raises:
        ValueError: If ``role`` is not ``user`` or ``assistant``.
    """
    if role not in _VALID_CHAT_ROLES:
        msg = f"Invalid role: {role!r}"
        raise ValueError(msg)
