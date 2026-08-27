"""Display currencies.

Prices are stored and compared in USD - one currency in the database means the
matcher, the scorer and the "cheapest retailer" logic never have to think about
conversion. This module exists only for presentation: it converts a stored USD
figure into what the viewer should see, and nothing upstream of it changes.

The rates are **fixed constants, not live FX.** They are good enough to show a
familiar figure alongside a product, and not good enough to transact on, which is
why `is_indicative` is part of the payload and the UI says so. If real rates are
ever needed, this is the one module to change.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = "USD"

# 1 USD buys this much of each currency.
RATES: dict[str, float] = {
    "USD": 1.0,
    "SGD": 1.27,
    "EUR": 0.87,
}

SYMBOLS: dict[str, str] = {
    "USD": "$",
    "SGD": "S$",
    "EUR": "€",
}

NAMES: dict[str, str] = {
    "USD": "US dollar",
    "SGD": "Singapore dollar",
    "EUR": "Euro",
}

SUPPORTED = tuple(RATES)


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    symbol: str
    name: str
    rate: float


def is_supported(code: str | None) -> bool:
    return bool(code) and code.upper() in RATES


def resolve(code: str | None) -> str:
    """Normalise a requested currency, falling back to USD.

    Unknown codes fall back rather than error: a stale value in someone's
    localStorage should show dollars, not break the page.
    """
    if code and code.upper() in RATES:
        return code.upper()
    return BASE


def get(code: str | None) -> Currency:
    resolved = resolve(code)
    return Currency(
        code=resolved,
        symbol=SYMBOLS[resolved],
        name=NAMES[resolved],
        rate=RATES[resolved],
    )


def convert(amount: float | None, code: str | None) -> float | None:
    """Convert a stored USD amount for display. None passes through."""
    if amount is None:
        return None
    return round(amount * RATES[resolve(code)], 2)


def format_amount(amount: float | None, code: str | None) -> str:
    """Render an amount the way the assistant should quote it."""
    if amount is None:
        return "unavailable"
    resolved = resolve(code)
    return f"{SYMBOLS[resolved]}{convert(amount, resolved):.2f}"


# --- region detection -------------------------------------------------------
#
# The frontend detects the viewer's region from their IANA time zone, which needs
# no permission prompt and no IP lookup. The mapping lives here so the backend
# can apply the same rule to a request that carries a time zone, and so there is
# one list to correct rather than two.

# The euro area proper, plus the microstates and overseas regions that use the
# euro. Deliberately excludes Europe/London, Europe/Zurich, Europe/Oslo,
# Europe/Stockholm, Europe/Copenhagen, Europe/Prague and Europe/Warsaw - being
# in Europe is not the same as being in the euro zone, and showing a Briton
# euros would be worse than showing them dollars.
EUROZONE_TIMEZONES = frozenset(
    {
        "Europe/Vienna", "Europe/Brussels", "Europe/Zagreb", "Asia/Nicosia",
        "Europe/Nicosia", "Europe/Tallinn", "Europe/Helsinki", "Europe/Paris",
        "Europe/Berlin", "Europe/Busingen", "Europe/Athens", "Europe/Dublin",
        "Europe/Rome", "Europe/Riga", "Europe/Vilnius", "Europe/Luxembourg",
        "Europe/Malta", "Europe/Amsterdam", "Europe/Lisbon", "Europe/Bratislava",
        "Europe/Ljubljana", "Europe/Madrid",
        # Euro-using microstates
        "Europe/Andorra", "Europe/Monaco", "Europe/San_Marino", "Europe/Vatican",
        # Outermost regions and island groups on the euro
        "Atlantic/Azores", "Atlantic/Madeira", "Atlantic/Canary",
    }
)

SINGAPORE_TIMEZONES = frozenset({"Asia/Singapore"})


def for_timezone(timezone: str | None) -> str:
    """Which currency to show someone in this time zone.

    Singapore gets SGD, the euro area gets EUR, everywhere else gets USD - which
    is also the fallback for an unrecognised or absent zone.
    """
    if not timezone:
        return BASE
    if timezone in SINGAPORE_TIMEZONES:
        return "SGD"
    if timezone in EUROZONE_TIMEZONES:
        return "EUR"
    return BASE


def catalogue() -> dict:
    """Everything the frontend needs to render and switch currencies."""
    return {
        "base": BASE,
        "is_indicative": True,
        "note": (
            "Prices are collected in US dollars and converted at a fixed rate "
            "for display. Treat converted figures as indicative."
        ),
        "currencies": [
            {
                "code": code,
                "symbol": SYMBOLS[code],
                "name": NAMES[code],
                "rate": RATES[code],
            }
            for code in SUPPORTED
        ],
    }
