"""robots.txt enforcement.

Checked before every outbound request. A retailer that disallows a path does not
get fetched - the request never leaves the process. This is what keeps adding a
new scraper safe by default rather than by remembering to check.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

# Identify honestly. If a site wants to exclude us, this is the name to exclude.
USER_AGENT_TOKEN = "DewdropSkincareBot"

_cache: dict[str, RobotFileParser | None] = {}
_locks: dict[str, asyncio.Lock] = {}


class RobotsDisallowed(Exception):
    """The target site's robots.txt forbids this path."""


def _lock_for(origin: str) -> asyncio.Lock:
    if origin not in _locks:
        _locks[origin] = asyncio.Lock()
    return _locks[origin]


async def _load(origin: str) -> RobotFileParser | None:
    """Fetch and parse one origin's robots.txt. None means 'no rules published'."""
    async with _lock_for(origin):
        if origin in _cache:
            return _cache[origin]

        parser: RobotFileParser | None = None
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{origin}/robots.txt",
                    headers={"User-Agent": USER_AGENT_TOKEN},
                )
            if response.status_code == 200:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
            else:
                # No robots.txt published - nothing is disallowed.
                logger.info("no robots.txt at %s (status %s)", origin, response.status_code)
        except httpx.HTTPError as exc:
            # Fail open on a network error, but say so. Failing closed here would
            # make an unrelated outage look like a permissions problem.
            logger.warning("could not read robots.txt for %s: %s", origin, exc)

        _cache[origin] = parser
        return parser


async def is_allowed(url: str, user_agent: str = USER_AGENT_TOKEN) -> bool:
    parts = urlparse(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    parser = await _load(origin)
    if parser is None:
        return True
    return parser.can_fetch(user_agent, url)


async def assert_allowed(url: str, user_agent: str = USER_AGENT_TOKEN) -> None:
    if not await is_allowed(url, user_agent):
        raise RobotsDisallowed(f"robots.txt disallows {url}")


def clear_cache() -> None:
    """Test hook."""
    _cache.clear()
