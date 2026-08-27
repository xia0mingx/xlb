"""The agentic loop for one chat turn.

Talks to an OpenAI-compatible chat-completions endpoint (OpenCode). The shape is
the same one used in lunch-uncle: send the message list plus tool definitions,
run any tool the model asks for, append the results, and call again until the
model answers without requesting a tool.

The loop is bounded in three ways on purpose - a round cap, a request timeout,
and a trimmed history - because an unbounded agentic loop against a paid
endpoint is a billing incident waiting to happen.
"""

from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.allergens import resolve
from app.chat.prompt import build_system_prompt
from app.chat.tools import TOOL_DEFINITIONS, ChatContext, execute_tool
from app.services import currency as currency_service
from app.config import get_settings

logger = logging.getLogger(__name__)


class ChatUnavailable(RuntimeError):
    """The assistant is not configured, or the provider could not be reached."""


class ChatResult:
    """What one turn produced."""

    def __init__(self, reply: str, avoid_terms: list[str], tool_calls: list[str], rounds: int):
        self.reply = reply
        self.avoid_terms = avoid_terms
        self.tool_calls = tool_calls
        self.rounds = rounds


def _parse_args(raw: str | None) -> dict:
    """Tool arguments arrive as a JSON string and are not always valid."""
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        logger.warning("could not parse tool arguments: %r", raw)
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _call_model(client: httpx.AsyncClient, messages: list[dict], settings) -> dict:
    """One request to the provider. Returns the assistant message."""
    try:
        response = await client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {settings.opencode_api_key}",
            },
            json={
                "model": settings.llm_model,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
            },
        )
    except httpx.TimeoutException as exc:
        raise ChatUnavailable("The assistant timed out. Please try again.") from exc
    except httpx.HTTPError as exc:
        raise ChatUnavailable(f"Could not reach the assistant: {exc}") from exc

    if response.status_code >= 400:
        # Deliberately not echoing the provider body to the client - it can
        # carry key hints. It goes to the log instead.
        logger.error("LLM returned %s: %s", response.status_code, response.text[:500])
        raise ChatUnavailable(f"The assistant returned an error ({response.status_code}).")

    try:
        payload = response.json()
        return payload["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as exc:
        logger.error("unexpected LLM response shape: %s", response.text[:500])
        raise ChatUnavailable("The assistant returned an unreadable response.") from exc


async def run_turn(
    session: AsyncSession,
    message: str,
    history: list[dict] | None = None,
    avoid: list[str] | None = None,
    currency: str | None = None,
) -> ChatResult:
    """Run one user turn to a final answer.

    `avoid` is the allergen list the client has stored. It is resolved before the
    first model call, so filtering is already active on the very first tool
    result - not only after the model thinks to ask about it.
    """
    settings = get_settings()
    if not settings.chat_enabled:
        raise ChatUnavailable(
            "The assistant is not configured. Set LLM_BASE_URL, LLM_MODEL and "
            "OPENCODE_API_KEY in the backend environment."
        )

    ctx = ChatContext(
        session=session,
        avoid_terms=list(avoid or []),
        currency=currency_service.resolve(currency),
    )
    ctx.allergens = resolve(ctx.avoid_terms)

    trimmed = (history or [])[-settings.chat_max_history :]
    messages: list[dict] = [
        {
            "role": "system",
            "content": build_system_prompt(ctx.allergens.labels(), ctx.currency),
        },
        *trimmed,
        {"role": "user", "content": message},
    ]

    called: list[str] = []

    async with httpx.AsyncClient(timeout=settings.chat_timeout_seconds) as client:
        for round_number in range(settings.chat_max_rounds):
            assistant = await _call_model(client, messages, settings)
            messages.append(assistant)

            tool_calls = assistant.get("tool_calls") or []
            if not tool_calls:
                return ChatResult(
                    reply=(assistant.get("content") or "").strip(),
                    avoid_terms=ctx.avoid_terms,
                    tool_calls=called,
                    rounds=round_number + 1,
                )

            for call in tool_calls:
                name = call.get("function", {}).get("name", "")
                args = _parse_args(call.get("function", {}).get("arguments"))
                logger.info("chat round %s: %s(%s)", round_number, name, args)
                called.append(name)

                result = await execute_tool(name, args, ctx)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(result, default=str),
                    }
                )

            # An allergy recorded mid-turn changes what the model should be told
            # it is filtering on, so refresh the standing instruction.
            if "record_allergy" in called:
                messages[0] = {
                    "role": "system",
                    "content": build_system_prompt(ctx.allergens.labels(), ctx.currency),
                }

    return ChatResult(
        reply=(
            "I was not able to complete that request within the allowed number of "
            "steps. Please try asking for one thing at a time."
        ),
        avoid_terms=ctx.avoid_terms,
        tool_calls=called,
        rounds=settings.chat_max_rounds,
    )
