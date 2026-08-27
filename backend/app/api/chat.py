"""Chat assistant endpoint.

Stateless by design: the client holds the transcript and the avoid-list and
replays them each turn, exactly as the skin profile already works. There are no
user accounts in v1, so there is nowhere on the server for a conversation to
live, and putting one there would mean storing what people tell us about their
skin - which we would rather not hold.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.loop import ChatUnavailable, run_turn
from app.config import get_settings
from app.db import get_session
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/status")
async def chat_status() -> dict:
    """Whether the assistant is configured, so the UI can hide the widget."""
    return {"enabled": get_settings().chat_enabled}


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, session: AsyncSession = Depends(get_session)
) -> ChatResponse:
    try:
        result = await run_turn(
            session=session,
            message=payload.message,
            history=[m.model_dump() for m in payload.history],
            avoid=payload.avoid,
            currency=payload.currency,
        )
    except ChatUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return ChatResponse(
        reply=result.reply,
        avoid=result.avoid_terms,
        tool_calls=result.tool_calls,
    )
