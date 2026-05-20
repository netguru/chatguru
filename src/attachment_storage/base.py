"""Abstract interface for attachment binary storage."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AttachmentStorage(ABC):
    """
    Port for storing and retrieving binary attachment data.

    Implementations:
    - FilesystemAttachmentStorage: Stores files on the local filesystem.
    - (Future) AzureBlobAttachmentStorage, S3AttachmentStorage, etc.

    The storage layer handles only binary I/O; metadata (name, mime_type,
    visitor ownership) lives in the database via ChatHistoryRepository.
    """

    @abstractmethod
    async def store(self, data: bytes, attachment_id: str) -> str:
        """
        Persist raw bytes and return an opaque storage key.

        The key is stored in the database and later passed to ``retrieve``.
        Implementations MUST be idempotent for the same attachment_id.

        Args:
            data: Raw file bytes.
            attachment_id: Stable UUID chosen by the caller; used to derive
                the storage key so re-uploads of the same ID overwrite cleanly.

        Returns:
            An opaque storage key (e.g. a relative path or blob name).
        """
        ...

    @abstractmethod
    async def retrieve(self, storage_key: str) -> AsyncIterator[bytes]:
        """
        Stream the stored bytes identified by *storage_key*.

        Yields chunks of bytes.  Raises ``FileNotFoundError`` when the key
        does not exist.
        """
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Return True when the underlying storage is reachable and writable."""
        ...
