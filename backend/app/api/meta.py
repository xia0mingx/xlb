"""Reference data the frontend needs but that is not about a specific product."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import currency as currency_service
from app.services.provenance import DESCRIPTIONS, LABELS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/currencies")
async def currencies(
    timezone: str | None = Query(
        None,
        description=(
            "The viewer's IANA time zone, e.g. Asia/Singapore. When given, the "
            "response names the currency to default to."
        ),
    ),
) -> dict:
    payload = currency_service.catalogue()
    payload["suggested"] = currency_service.for_timezone(timezone)
    return payload


@router.get("/ingredient-sources")
async def ingredient_sources() -> dict:
    """The provenance vocabulary, so the UI does not hardcode the labels."""
    return {
        "sources": [
            {"key": key, "label": LABELS[key], "description": DESCRIPTIONS[key]}
            for key in LABELS
        ],
        "note": (
            "Origin only. It is not a safety or quality ranking, and it does not "
            "affect recommendations - several of the most common contact allergens "
            "are natural, and several of the gentlest ingredients are synthetic."
        ),
    }
