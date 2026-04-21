"""API error types and exceptions."""

from enum import StrEnum


class WebSocketErrorType(StrEnum):
    """Machine-readable error categories sent to WebSocket clients."""

    INVALID_JSON = "invalid_json"
    INVALID_MESSAGE_FORMAT = "invalid_message_format"
    VALIDATION_ERROR = "validation_error"
    PERSISTENCE_WRITE_FAILED = "persistence_write_failed"
    MISSING_VISITOR_ID = "missing_visitor_id"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INTERNAL_ERROR = "internal_error"


class WebSocketClientError(Exception):
    """Base exception for predictable client-facing WebSocket errors."""

    def __init__(self, *, error_type: WebSocketErrorType, content: str) -> None:
        self.error_type = error_type
        self.content = content
        super().__init__(content)


class InvalidMessageFormatError(WebSocketClientError):
    """Raised when message data is not in the expected format (must be a JSON object)."""

    def __init__(
        self, content: str = "Invalid message format or validation failed"
    ) -> None:
        super().__init__(
            error_type=WebSocketErrorType.INVALID_MESSAGE_FORMAT,
            content=content,
        )


class InvalidJSONError(WebSocketClientError):
    """Raised when a WebSocket payload is not valid JSON."""

    def __init__(self) -> None:
        super().__init__(
            error_type=WebSocketErrorType.INVALID_JSON,
            content="Invalid JSON format",
        )


class ValidationFailedError(WebSocketClientError):
    """Raised when payload schema validation fails."""

    def __init__(self) -> None:
        super().__init__(
            error_type=WebSocketErrorType.VALIDATION_ERROR,
            content="Invalid message format or validation failed",
        )
