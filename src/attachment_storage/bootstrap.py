"""Process-wide attachment storage singleton (FastAPI app lifespan)."""

from attachment_storage.base import AttachmentStorage
from attachment_storage.factory import create_attachment_storage
from config import get_logger

logger = get_logger(__name__)

_attachment_storage: AttachmentStorage | None = None


async def init_attachment_storage() -> None:
    """Initialize the process-wide attachment storage (call once at startup)."""
    global _attachment_storage  # noqa: PLW0603
    if _attachment_storage is not None:
        return
    storage = create_attachment_storage()
    healthy = await storage.is_healthy()
    if not healthy:
        logger.warning("Attachment storage health check failed — uploads may not work")
    else:
        logger.info("Attachment storage initialized")
    _attachment_storage = storage


async def shutdown_attachment_storage() -> None:
    """Release attachment storage resources (call at shutdown)."""
    global _attachment_storage  # noqa: PLW0603
    _attachment_storage = None
    logger.info("Attachment storage shut down")


def is_attachment_storage_enabled() -> bool:
    """Return True when attachment storage has been initialized."""
    return _attachment_storage is not None


def get_attachment_storage() -> AttachmentStorage:
    """
    Return the process-wide AttachmentStorage instance.

    Raises:
        RuntimeError: If ``init_attachment_storage`` has not been called.
    """
    if _attachment_storage is None:
        msg = "Attachment storage is not initialized — call init_attachment_storage() at startup"
        raise RuntimeError(msg)
    return _attachment_storage
