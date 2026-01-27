"""API error exceptions."""


class InvalidMessageFormatError(Exception):
    """Raised when message data is not in the expected format (must be a JSON object)."""
