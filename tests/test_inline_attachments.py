"""Inline image attachments on the chat turn (the no-storage route).

Covers the validation rules on `InlineAttachment` / `ChatMessage` and the merge in
`_build_transcript`. The size caps are monkeypatched down rather than exercised
with real 4 MB payloads: the boundary logic is what matters, and building
multi-megabyte base64 strings in a unit test buys nothing but runtime.
"""

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from api.routes import chat as chat_routes
from api.routes.chat import ChatMessage, HistoryMessage, InlineAttachment

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"pixels"
PNG_B64 = base64.b64encode(PNG_BYTES).decode()


def _turn(**last_kwargs: Any) -> ChatMessage:
    """A minimal valid turn whose last user message is customisable."""
    return ChatMessage(
        session_id="s-1",
        visitor_id="v-1",
        messages=[
            HistoryMessage(role="user", content="earlier"),
            HistoryMessage(role="assistant", content="answer"),
            HistoryMessage(role="user", content="what is this?", **last_kwargs),
        ],
    )


def _inline(
    name: str = "shot.png", mime: str = "image/png", data: str = PNG_B64
) -> dict[str, str]:
    return {"name": name, "mime_type": mime, "data": data}


class TestInlineAttachmentValidation:
    def test_accepts_a_supported_image(self) -> None:
        turn = _turn(attachments=[_inline()])
        assert turn.messages[-1].attachments is not None
        assert turn.messages[-1].attachments[0].name == "shot.png"

    @pytest.mark.parametrize("mime", ["application/pdf", "text/plain", "image/svg+xml"])
    def test_rejects_an_unsupported_media_type(self, mime: str) -> None:
        with pytest.raises(ValidationError, match="Unsupported inline attachment type"):
            InlineAttachment(name="f", mime_type=mime, data=PNG_B64)

    def test_rejects_data_that_is_not_base64(self) -> None:
        with pytest.raises(ValidationError, match="not valid base64"):
            InlineAttachment(name="shot.png", mime_type="image/png", data="not!base64")

    def test_rejects_an_image_over_the_per_image_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(chat_routes, "_MAX_IMAGE_BYTES_FOR_LLM", 4)
        with pytest.raises(ValidationError, match="over the 4 byte limit"):
            InlineAttachment(name="shot.png", mime_type="image/png", data=PNG_B64)

    def test_rejects_attachments_on_an_earlier_message(self) -> None:
        with pytest.raises(ValidationError, match="Only the last"):
            ChatMessage(
                session_id="s-1",
                visitor_id="v-1",
                messages=[
                    HistoryMessage(
                        role="user", content="earlier", attachments=[_inline()]
                    ),
                    HistoryMessage(role="user", content="now"),
                ],
            )

    def test_the_per_message_limit_is_shared_with_stored_attachments(self) -> None:
        # Three of each is six images on one turn — under the cap for either kind
        # alone, over it combined, which is the point of the shared limit.
        with pytest.raises(ValidationError, match="At most 5 attachments"):
            _turn(
                attachment_ids=["a", "b", "c"],
                attachments=[_inline(name=f"{i}.png") for i in range(3)],
            )

    def test_rejects_a_turn_over_the_total_base64_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            chat_routes, "_MAX_INLINE_ATTACHMENT_TOTAL_B64", len(PNG_B64)
        )
        with pytest.raises(ValidationError, match="over the .* per-turn limit"):
            _turn(attachments=[_inline(name="a.png"), _inline(name="b.png")])

    def test_allows_empty_text_when_only_inline_attachments_are_present(self) -> None:
        turn = ChatMessage(
            session_id="s-1",
            visitor_id="v-1",
            messages=[HistoryMessage(role="user", content="", attachments=[_inline()])],
        )
        assert turn.messages[-1].content == ""


class TestBuildTranscriptMerge:
    @pytest.mark.asyncio
    async def test_inline_attachments_reach_the_current_entry(self) -> None:
        transcript = await chat_routes._build_transcript(
            _turn(attachments=[_inline()]), visitor_id="v-1", repo=None
        )
        assert transcript[-1]["attachments"] == [
            {"name": "shot.png", "mime_type": "image/png", "data": PNG_B64}
        ]
        # Earlier turns stay plain — the agent only renders images on the current one.
        assert "attachments" not in transcript[0]

    @pytest.mark.asyncio
    async def test_stored_and_inline_attachments_are_both_carried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stored = {"name": "stored.png", "mime_type": "image/png", "data": "c3RvcmVk"}
        monkeypatch.setattr(
            chat_routes, "_load_image_attachments", AsyncMock(return_value=[stored])
        )
        transcript = await chat_routes._build_transcript(
            _turn(attachment_ids=["att-1"], attachments=[_inline()]),
            visitor_id="v-1",
            repo=MagicMock(),
        )
        assert [a["name"] for a in transcript[-1]["attachments"]] == [
            "stored.png",
            "shot.png",
        ]

    @pytest.mark.asyncio
    async def test_no_attachments_key_when_the_turn_has_none(self) -> None:
        transcript = await chat_routes._build_transcript(
            _turn(), visitor_id="v-1", repo=None
        )
        assert "attachments" not in transcript[-1]

    @pytest.mark.asyncio
    async def test_inline_attachments_are_never_persisted(self) -> None:
        repo = MagicMock()
        await chat_routes._build_transcript(
            _turn(attachments=[_inline()]), visitor_id="v-1", repo=repo
        )
        repo.save_attachment.assert_not_called()
        repo.link_attachments_to_message.assert_not_called()
