"""Factory for creating AttachmentStorage instances."""

from attachment_storage.base import AttachmentStorage
from attachment_storage.filesystem import FilesystemAttachmentStorage
from config import get_attachment_storage_settings, get_logger

logger = get_logger(__name__)


def create_attachment_storage() -> AttachmentStorage:
    """
    Create an AttachmentStorage instance based on ATTACHMENT_STORAGE_TYPE.

    Supported types:
    - ``filesystem``: Local filesystem storage (default).
    """
    settings = get_attachment_storage_settings()
    storage_type = settings.type.lower()

    if storage_type == "filesystem":
        logger.info("Creating filesystem attachment storage at %s", settings.base_path)
        return FilesystemAttachmentStorage(base_path=settings.base_path)

    msg = f"Unknown attachment storage type: {storage_type!r}. Supported: 'filesystem'."
    raise ValueError(msg)
