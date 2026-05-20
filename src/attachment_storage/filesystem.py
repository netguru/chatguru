"""Local filesystem implementation of AttachmentStorage."""

import asyncio
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

from attachment_storage.base import AttachmentStorage

_CHUNK_SIZE = 256 * 1024  # 256 KB

# Standard UUID v4 lowercase hex — only callers that generate via uuid.uuid4() are valid.
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class FilesystemAttachmentStorage(AttachmentStorage):
    """
    Stores attachment files under a configurable base directory.

    Layout: ``{base_path}/{attachment_id[:2]}/{attachment_id}``

    The two-character prefix shard avoids placing thousands of files in a
    single directory on systems with slow directory enumeration.
    """

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def _file_path(self, attachment_id: str) -> Path:
        if not _UUID_RE.match(attachment_id):
            msg = f"attachment_id must be a lowercase UUID, got {attachment_id!r}"
            raise ValueError(msg)
        shard = attachment_id[:2]
        return self._base / shard / attachment_id

    async def store(self, data: bytes, attachment_id: str) -> str:
        path = self._file_path(attachment_id)
        loop = asyncio.get_running_loop()

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await loop.run_in_executor(None, _write)
        # Storage key is the relative path from base_path.
        return f"{attachment_id[:2]}/{attachment_id}"

    async def retrieve(self, storage_key: str) -> AsyncIterator[bytes]:
        resolved = (self._base / storage_key).resolve()
        if not resolved.is_relative_to(self._base.resolve()):
            msg = f"Storage key escapes base path: {storage_key!r}"
            raise ValueError(msg)
        path = resolved
        loop = asyncio.get_running_loop()

        async def _stream() -> AsyncIterator[bytes]:
            def _open_file() -> BinaryIO:
                try:
                    return path.open("rb")
                except OSError as exc:
                    msg = f"Attachment not found: {storage_key}"
                    raise FileNotFoundError(msg) from exc

            f = await loop.run_in_executor(None, _open_file)
            try:
                while True:
                    chunk = await loop.run_in_executor(None, f.read, _CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await loop.run_in_executor(None, f.close)

        return _stream()

    async def is_healthy(self) -> bool:
        loop = asyncio.get_running_loop()

        def _check() -> bool:
            try:
                self._base.mkdir(parents=True, exist_ok=True)
                probe = self._base / ".health"
                probe.write_text("ok")
                probe.unlink()
            except OSError:
                return False
            return True

        return await loop.run_in_executor(None, _check)
