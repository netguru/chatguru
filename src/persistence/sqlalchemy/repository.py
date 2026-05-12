"""
Infrastructure adapter: :class:`ChatHistoryRepository` backed by SQLAlchemy async.

Route handlers and other application-layer code must not import this module directly;
use :func:`persistence.get_chat_history_repository` instead.  Only the composition
root (:mod:`persistence.factory`) wires this adapter in.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from persistence.models import StoredChatMessage, StoredConversation
from persistence.repository import ChatHistoryRepository
from persistence.sqlalchemy.tables import chat_messages, conversations
from persistence.validation import validate_chat_message_role


def _as_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyChatHistoryRepository(ChatHistoryRepository):
    """
    SQLAlchemy-based adapter implementing the chat history repository port.

    One :class:`~sqlalchemy.ext.asyncio.AsyncEngine` per instance; swap URL/dialect
    via settings without changing call sites.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def connect(self) -> None:
        """Verify the engine works and the expected tables exist."""
        async with self._engine.connect() as conn:
            await conn.execute(select(chat_messages).limit(0))
            await conn.execute(select(conversations).limit(0))

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def _fetch_conversation(
        self, visitor_id: str, session_id: str
    ) -> StoredConversation | None:
        """Return the conversation row if it exists, else None."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(conversations).where(
                    and_(
                        conversations.c.visitor_id == visitor_id,
                        conversations.c.session_id == session_id,
                    )
                )
            )
            row = result.mappings().first()
        if row is None:
            return None
        return StoredConversation(
            id=str(row["id"]),
            visitor_id=str(row["visitor_id"]),
            session_id=str(row["session_id"]),
            title=str(row["title"]),
            created_at=_as_utc_datetime(row["created_at"]),
        )

    async def create_conversation(
        self,
        *,
        visitor_id: str,
        session_id: str,
        title: str,
    ) -> StoredConversation:
        """Create conversation; returns existing record if session_id already exists for visitor.

        Uses an optimistic INSERT: if a concurrent request races to insert the same
        (visitor_id, session_id), the unique constraint raises IntegrityError which is
        caught and resolved by re-fetching the winning row.
        """
        existing = await self._fetch_conversation(visitor_id, session_id)
        if existing is not None:
            return existing

        conv_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)
        try:
            async with self._engine.begin() as conn:
                await conn.execute(
                    conversations.insert().values(
                        id=conv_id,
                        visitor_id=visitor_id,
                        session_id=session_id,
                        title=title,
                        created_at=created_at,
                    )
                )
        except IntegrityError:
            # A concurrent request inserted the same (visitor_id, session_id) between
            # our check and our INSERT.  Re-fetch the winning row.
            # The RuntimeError below handles the theoretical case where the winning row
            # was concurrently deleted between the IntegrityError and the re-fetch —
            # vanishingly unlikely in practice (no delete path exists today), but
            # raising is safer than returning stale data.
            row = await self._fetch_conversation(visitor_id, session_id)
            if row is None:
                msg = "Conversation disappeared after IntegrityError — unexpected state"
                raise RuntimeError(msg) from None
            return row

        return StoredConversation(
            id=conv_id,
            visitor_id=visitor_id,
            session_id=session_id,
            title=title,
            created_at=created_at,
        )

    async def update_conversation_title(
        self,
        *,
        visitor_id: str,
        session_id: str,
        title: str,
    ) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                conversations.update()
                .where(
                    and_(
                        conversations.c.visitor_id == visitor_id,
                        conversations.c.session_id == session_id,
                    )
                )
                .values(title=title)
            )

    async def conversation_exists(
        self,
        *,
        visitor_id: str,
        session_id: str,
    ) -> bool:
        """Return True if a conversation row exists for the given visitor+session pair."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(conversations.c.id)
                .where(
                    and_(
                        conversations.c.visitor_id == visitor_id,
                        conversations.c.session_id == session_id,
                    )
                )
                .limit(1)
            )
            return result.first() is not None

    async def list_conversations(
        self,
        *,
        visitor_id: str,
    ) -> list[StoredConversation]:
        stmt = (
            select(conversations)
            .where(conversations.c.visitor_id == visitor_id)
            .order_by(conversations.c.created_at.desc())
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().all()
        return [
            StoredConversation(
                id=str(r["id"]),
                visitor_id=str(r["visitor_id"]),
                session_id=str(r["session_id"]),
                title=str(r["title"]),
                created_at=_as_utc_datetime(r["created_at"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def append_message(  # noqa: PLR0913
        self,
        *,
        visitor_id: str,
        session_id: str,
        role: str,
        content: str,
        trace_id: str | None = None,
        sources: str | None = None,
    ) -> None:
        validate_chat_message_role(role)
        message_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)
        async with self._engine.begin() as conn:
            await conn.execute(
                chat_messages.insert().values(
                    id=message_id,
                    visitor_id=visitor_id,
                    session_id=session_id,
                    role=role,
                    content=content,
                    created_at=created_at,
                    trace_id=trace_id,
                    sources=sources,
                )
            )

    async def list_messages(
        self,
        *,
        visitor_id: str,
        session_id: str,
    ) -> list[StoredChatMessage]:
        stmt = (
            select(chat_messages)
            .where(
                and_(
                    chat_messages.c.visitor_id == visitor_id,
                    chat_messages.c.session_id == session_id,
                )
            )
            .order_by(chat_messages.c.created_at.asc(), chat_messages.c.id.asc())
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().all()
        return [
            StoredChatMessage(
                id=str(r["id"]),
                visitor_id=str(r["visitor_id"]),
                session_id=str(r["session_id"]),
                role=str(r["role"]),
                content=str(r["content"]),
                created_at=_as_utc_datetime(r["created_at"]),
                trace_id=str(r["trace_id"]) if r["trace_id"] is not None else None,
                sources=str(r["sources"]) if r["sources"] is not None else None,
            )
            for r in rows
        ]

    async def trace_id_owned_by_visitor(
        self,
        *,
        trace_id: str,
        visitor_id: str,
    ) -> bool:
        """Return True if an assistant message with this trace_id belongs to visitor_id."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(chat_messages.c.id)
                .where(
                    and_(
                        chat_messages.c.trace_id == trace_id,
                        chat_messages.c.visitor_id == visitor_id,
                    )
                )
                .limit(1)
            )
            return result.first() is not None

    async def close(self) -> None:
        await self._engine.dispose()
