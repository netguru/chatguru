"""Tests for the attachment_storage module."""

import asyncio
from pathlib import Path

import pytest

from attachment_storage.filesystem import FilesystemAttachmentStorage


# ─── Test UUIDs ──────────────────────────────────────────────────────────────

_ID_A = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
_ID_B = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
_ID_C = "cccccccc-cccc-4ccc-cccc-cccccccccccc"
_ID_D = "dddddddd-dddd-4ddd-dddd-dddddddddddd"
_ID_E = "eeeeeeee-eeee-4eee-eeee-eeeeeeeeeeee"
_ID_F = "ffffffff-ffff-4fff-ffff-ffffffffffff"
_ID_G = "00000001-0000-4000-a000-000000000001"
_ID_H = "00000002-0000-4000-a000-000000000002"
_ID_I = "00000003-0000-4000-a000-000000000003"
_ID_LARGE = "10000000-0000-4000-a000-000000000000"
_ID_SHARD1 = "ab000001-0000-4000-a000-000000000001"
_ID_SHARD2 = "ab000002-0000-4000-a000-000000000002"

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def storage(tmp_path: Path) -> FilesystemAttachmentStorage:
    return FilesystemAttachmentStorage(base_path=str(tmp_path))


# ─── UUID validation ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_rejects_non_uuid_id(storage: FilesystemAttachmentStorage) -> None:
    with pytest.raises(ValueError, match="UUID"):
        await storage.store(b"data", "not-a-uuid")


@pytest.mark.asyncio
async def test_store_rejects_uppercase_uuid(
    storage: FilesystemAttachmentStorage,
) -> None:
    with pytest.raises(ValueError, match="UUID"):
        await storage.store(b"data", "AAAAAAAA-AAAA-4AAA-AAAA-AAAAAAAAAAAA")


# ─── Core round-trip ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_returns_storage_key(storage: FilesystemAttachmentStorage) -> None:
    key = await storage.store(b"hello world", _ID_A)
    # Key should be "aa/<uuid>" (shard = first two chars of UUID).
    assert key == f"aa/{_ID_A}"


@pytest.mark.asyncio
async def test_store_creates_file(
    storage: FilesystemAttachmentStorage, tmp_path: Path
) -> None:
    await storage.store(b"content", _ID_B)
    assert (tmp_path / "bb" / _ID_B).read_bytes() == b"content"


@pytest.mark.asyncio
async def test_retrieve_streams_content(storage: FilesystemAttachmentStorage) -> None:
    data = b"binary data here"
    key = await storage.store(data, _ID_C)
    stream = await storage.retrieve(key)
    chunks = [chunk async for chunk in stream]
    assert b"".join(chunks) == data


@pytest.mark.asyncio
async def test_retrieve_raises_for_missing_key(
    storage: FilesystemAttachmentStorage,
) -> None:
    with pytest.raises(FileNotFoundError):
        stream = await storage.retrieve("xx/nonexistent")
        async for _ in stream:
            pass


@pytest.mark.asyncio
async def test_store_is_idempotent(storage: FilesystemAttachmentStorage) -> None:
    await storage.store(b"first", _ID_D)
    await storage.store(b"second", _ID_D)  # overwrite
    key = f"dd/{_ID_D}"
    stream = await storage.retrieve(key)
    result = b"".join([chunk async for chunk in stream])
    assert result == b"second"


@pytest.mark.asyncio
async def test_is_healthy_returns_true(storage: FilesystemAttachmentStorage) -> None:
    assert await storage.is_healthy() is True


@pytest.mark.asyncio
async def test_is_healthy_returns_false_for_unwritable_path() -> None:
    storage = FilesystemAttachmentStorage(base_path="/proc/nonexistent_readonly_path")
    assert await storage.is_healthy() is False


@pytest.mark.asyncio
async def test_concurrent_stores_do_not_interfere(
    storage: FilesystemAttachmentStorage,
) -> None:
    """Concurrent uploads for different IDs must not corrupt each other."""

    async def upload(attachment_id: str, payload: bytes) -> bytes:
        key = await storage.store(payload, attachment_id)
        stream = await storage.retrieve(key)
        return b"".join([chunk async for chunk in stream])

    results = await asyncio.gather(
        upload(_ID_G, b"data-for-g"),
        upload(_ID_H, b"data-for-h"),
        upload(_ID_I, b"data-for-i"),
    )
    assert results[0] == b"data-for-g"
    assert results[1] == b"data-for-h"
    assert results[2] == b"data-for-i"


@pytest.mark.asyncio
async def test_store_large_payload(storage: FilesystemAttachmentStorage) -> None:
    large = b"x" * (1024 * 1024)  # 1 MB
    key = await storage.store(large, _ID_LARGE)
    stream = await storage.retrieve(key)
    result = b"".join([chunk async for chunk in stream])
    assert result == large
    assert len(result) == 1024 * 1024


@pytest.mark.asyncio
async def test_shard_prefix_separates_files(
    storage: FilesystemAttachmentStorage, tmp_path: Path
) -> None:
    """Two attachments starting with the same 2-char prefix land in the same shard dir."""
    await storage.store(b"a", _ID_SHARD1)
    await storage.store(b"b", _ID_SHARD2)
    shard = tmp_path / "ab"
    assert shard.is_dir()
    assert (shard / _ID_SHARD1).exists()
    assert (shard / _ID_SHARD2).exists()
