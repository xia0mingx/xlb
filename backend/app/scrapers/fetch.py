"""Shared HTTP layer for all scrapers.

Centralises the things every scraper would otherwise get wrong: per-domain rate
limiting, retry with backoff, robots.txt enforcement, and turning HTTP status codes
into the right exception type so the scheduler can tell "blocked" from "broken".
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections import defaultdict
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.scrapers.base import ProductNotFound, ScrapeBlocked, ScrapeFailed
from app.scrapers.robots import USER_AGENT_TOKEN, assert_allowed

logger = logging.getLogger(__name__)

# We identify honestly rather than spoofing a browser. Both target retailers serve
# us fine under this UA, and claiming to respect robots.txt while disguising
# ourselves as a human would be incoherent. A site that wants us gone can name it.
BOT_USER_AGENT = f"{USER_AGENT_TOKEN}/0.1 (+https://github.com/dewdrop/dewdrop; skincare price comparison)"

# Status codes that mean "the retailer refused us", not "something broke".
BLOCKED_STATUSES = {401, 403, 407, 429, 503}

_domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_last_request: dict[str, float] = {}


def default_headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": BOT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # Deliberately NOT setting Accept-Encoding: httpx advertises exactly the
        # codecs it can actually decode. Hardcoding "br" here yields raw brotli
        # bytes and a UnicodeDecodeError.
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }
    if referer:
        headers["Referer"] = referer
    return headers


async def _throttle(domain: str) -> None:
    """Keep at least `scrape_delay_seconds` between hits on the same domain."""
    settings = get_settings()
    loop = asyncio.get_running_loop()
    async with _domain_locks[domain]:
        last = _last_request.get(domain)
        if last is not None:
            elapsed = loop.time() - last
            wait = settings.scrape_delay_seconds - elapsed
            if wait > 0:
                # Jitter so we do not hammer on a fixed cadence.
                await asyncio.sleep(wait + random.uniform(0, 0.4))
        _last_request[domain] = loop.time()


async def fetch(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict | None = None,
    client: httpx.AsyncClient | None = None,
    check_robots: bool = True,
) -> httpx.Response:
    """GET a URL with robots enforcement, throttling, retries and clear exceptions.

    Raises RobotsDisallowed before any request goes out if the site forbids the path.
    """
    settings = get_settings()
    domain = urlparse(url).netloc

    if check_robots:
        await assert_allowed(url)

    merged = default_headers()
    if headers:
        merged.update(headers)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=settings.scrape_timeout,
            follow_redirects=True,
            http2=False,
        )

    try:
        last_error: Exception | None = None
        for attempt in range(settings.scrape_retries):
            await _throttle(domain)
            try:
                response = await client.get(url, headers=merged, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("fetch error %s (attempt %s): %s", url, attempt + 1, exc)
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code == 404:
                raise ProductNotFound(url)
            if response.status_code in BLOCKED_STATUSES:
                # Retrying a 403 with the same fingerprint rarely helps, but a
                # 429/503 often clears, so back off and try again.
                if attempt == settings.scrape_retries - 1:
                    raise ScrapeBlocked(f"{response.status_code} from {domain}")
                await asyncio.sleep(2 ** (attempt + 1))
                continue
            if response.status_code >= 400:
                last_error = ScrapeFailed(f"{response.status_code} from {url}")
                await asyncio.sleep(2**attempt)
                continue

            return response

        raise ScrapeFailed(f"giving up on {url}: {last_error}")
    finally:
        if owns_client:
            await client.aclose()


async def fetch_text(url: str, **kwargs) -> str:
    response = await fetch(url, **kwargs)
    return response.text


async def fetch_json(url: str, **kwargs) -> dict:
    response = await fetch(url, **kwargs)
    try:
        return response.json()
    except ValueError as exc:
        raise ScrapeFailed(f"non-JSON response from {url}") from exc
