"""Tool definitions and implementations for the chat assistant.

Following the convention from lunch-uncle: each tool is split into a function
that does IO and a pure function that shapes the result for the model. The pure
ones are what the tests cover.

Everything the model can reach goes through a service the web UI already uses -
the same scorer, the same ingredient analysis, the same conflict rules. The chat
surface is a different way to ask, not a second implementation, so the two
cannot drift apart or disagree about a product.

Payloads are deliberately lean. The model needs a slug, a name, a price and a
reason; sending it a full product record would spend context on fields it never
mentions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import build_analysis, latest_prices, price_history, product_query, to_summary
from app.chat.allergens import ResolvedAllergens, blocked_reason, resolve
from app.services.provenance import classify, summarise
from app.models import Brand, Concern, Product, ProductConcern
from app.models.enums import CATEGORY_LABELS
from app.services import currency as currency_service
from app.services.analysis import Analysis, detect_conflicts
from app.services.dupes import find_dupes
from app.services.recommend import SkinProfile, rank, score_product

logger = logging.getLogger(__name__)

# How many products any one tool may return. Enough to choose from, small enough
# that the model does not drown in options or the context in tokens.
MAX_RESULTS = 6

# Every price in the catalog is USD today; the snapshot rows carry the currency
# so the assistant is told rather than left to infer it.
DEFAULT_CURRENCY = "USD"


def _currency_of(price_rows: list[dict]) -> str:
    for row in price_rows:
        if row.get("currency"):
            return row["currency"]
    return DEFAULT_CURRENCY


@dataclass(slots=True)
class ChatContext:
    """Per-request state shared by every tool call in one turn."""

    session: AsyncSession
    avoid_terms: list[str] = field(default_factory=list)
    allergens: ResolvedAllergens = field(default_factory=ResolvedAllergens)
    # What the viewer sees on the page. Prices are stored in USD and converted
    # here so the assistant never quotes a different currency to the one beside it.
    currency: str = currency_service.BASE

    def add_allergens(self, terms: list[str]) -> ResolvedAllergens:
        """Register newly stated allergens and re-resolve the whole set."""
        for term in terms:
            cleaned = (term or "").strip()
            if cleaned and cleaned.lower() not in {t.lower() for t in self.avoid_terms}:
                self.avoid_terms.append(cleaned)
        self.allergens = resolve(self.avoid_terms)
        return self.allergens


# ---------------------------------------------------------------------------
# Definitions sent to the model
# ---------------------------------------------------------------------------

_CATEGORY_ENUM = sorted(CATEGORY_LABELS)

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "record_allergy",
            "description": (
                "Record an ingredient, ingredient class or sensitivity the user "
                "wants to avoid. Call this as soon as an allergy or sensitivity is "
                "mentioned. Products containing recorded allergens are then removed "
                "from every later tool result automatically. Accepts specific "
                "ingredients ('salicylic acid', 'vitamin C') and classes "
                "('fragrance', 'essential oils', 'alcohol')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ingredients or classes to avoid, in the user's own words.",
                    }
                },
                "required": ["terms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search the catalog by free text over brand and product name. Use "
                "when the user names something specific. Returns slug, brand, name, "
                "category, size, best price and how many retailers stock it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Brand or product name."},
                    "category": {
                        "type": "string",
                        "enum": _CATEGORY_ENUM,
                        "description": "Optional category filter.",
                    },
                    "max_price": {"type": "number", "description": "Optional price ceiling."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_products",
            "description": (
                "Recommend products for a skin type and set of concerns, scored by "
                "ingredient. Use for open questions like 'what should I use for dry "
                "skin'. Returns each product with the specific ingredients that "
                "earned it the recommendation, plus any warnings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skin_type": {
                        "type": "string",
                        "enum": ["dry", "oily", "combination", "normal", "sensitive"],
                    },
                    "concerns": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "acne",
                                "dryness",
                                "dark_spots",
                                "aging",
                                "redness",
                                "texture",
                                "oiliness",
                                "dullness",
                                "barrier",
                            ],
                        },
                        "description": "What the user wants to address.",
                    },
                    "sensitive": {"type": "boolean", "description": "Skin reacts easily."},
                    "fragrance_free": {"type": "boolean"},
                    "budget_max": {"type": "number", "description": "Most they want to spend."},
                    "category": {
                        "type": "string",
                        "enum": _CATEGORY_ENUM,
                        "description": "Restrict to one product category.",
                    },
                },
                "required": ["skin_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Full ingredient list for one product in INCI order, with actives, "
                "irritants, comedogenic rating and fragrance/alcohol/essential-oil "
                "flags. Use when asked what is in something or whether it suits someone."
            ),
            "parameters": {
                "type": "object",
                "properties": {"slug": {"type": "string", "description": "Product slug."}},
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_prices",
            "description": (
                "Every retailer stocking one product, with current price, stock "
                "status, staleness and the 90-day low. Use for 'where is this cheapest'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"slug": {"type": "string", "description": "Product slug."}},
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_cheaper_dupes",
            "description": (
                "Cheaper products with a comparable ingredient profile. Use for "
                "'is there anything cheaper like this'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"slug": {"type": "string", "description": "Product slug."}},
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_routine_conflicts",
            "description": (
                "Check whether several products conflict when used in one routine - "
                "for example a retinoid layered with an acid. Returns severity, an "
                "explanation and what to do instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slugs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Two or more product slugs.",
                    }
                },
                "required": ["slugs"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Pure formatters - these are the tested half
# ---------------------------------------------------------------------------


def format_summary(
    summary,
    reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    currency: str | None = None,
) -> dict:
    """One product, trimmed to the fields the model actually uses.

    `currency` is always sent alongside a price. Without it the model has to
    guess a symbol, and it guesses wrong - an observed run rendered USD prices
    with a pound sign, which is a correct number reported as the wrong money.
    """
    display = currency_service.resolve(currency)
    out: dict = {
        "slug": summary.slug,
        "brand": summary.brand,
        "name": summary.name,
        "category": summary.category,
        "size": summary.size_label,
        "best_price": currency_service.convert(summary.best_price, display),
        "currency": display,
        "price_display": currency_service.format_amount(summary.best_price, display),
        "retailers": summary.retailer_count,
        "on_sale": summary.on_sale,
    }
    if summary.key_actives:
        out["key_actives"] = summary.key_actives
    if reasons:
        out["reasons"] = reasons
    if warnings:
        out["warnings"] = warnings
    return out


def format_ingredients(analysis: Analysis, limit: int = 40) -> dict:
    """Ingredient analysis as the model needs it: order, actives, flags."""
    return {
        "count": len(analysis.ingredients),
        "inci_order": [i.inci_name for i in analysis.ingredients[:limit]],
        "actives": [
            {"name": i.common_name or i.inci_name, "position": i.position, "group": i.active_group}
            for i in analysis.actives
        ],
        "provenance": summarise([classify(i.inci_name) for i in analysis.ingredients]),
        "irritants": [i.common_name or i.inci_name for i in analysis.irritants],
        "max_comedogenic": analysis.max_comedogenic,
        "has_fragrance": analysis.has_fragrance,
        "has_alcohol": analysis.has_alcohol,
        "has_essential_oil": analysis.has_essential_oil,
        "unknown_ingredients": analysis.unknown_count,
    }


def format_prices(
    prices: list[dict], history_low: float | None = None, currency: str | None = None
) -> dict:
    """Retailer prices, cheapest first, with the fields a shopper asks about."""
    display = currency_service.resolve(currency)
    rows = [
        {
            "retailer": p["retailer"],
            "price": currency_service.convert(p["price"], display),
            "price_display": currency_service.format_amount(p["price"], display),
            "in_stock": p["in_stock"],
            "on_sale": bool(p.get("was_price")),
            "stale": bool(p.get("is_stale")),
        }
        for p in prices
        if p.get("price") is not None
    ]
    rows.sort(key=lambda r: r["price"])
    out: dict = {"retailers": rows, "currency": display}
    if rows:
        out["cheapest"] = rows[0]["retailer"]
        out["spread"] = round(rows[-1]["price"] - rows[0]["price"], 2)
    if history_low is not None:
        out["ninety_day_low"] = currency_service.convert(history_low, display)
    return out


def format_conflicts(findings: list[dict]) -> dict:
    """Conflict findings, already severity-ordered by the service."""
    return {
        "conflicts": [
            {
                "severity": f["severity"],
                "title": f["title"],
                "explanation": f["explanation"],
                "guidance": f["guidance"],
                "products": f["products"],
            }
            for f in findings
        ]
    }


def format_allergen_state(resolved: ResolvedAllergens) -> dict:
    """What is being filtered, and what we failed to understand."""
    out: dict = {"avoiding": resolved.labels()}
    if resolved.unresolved:
        out["not_recognised"] = resolved.unresolved
        out["note"] = (
            "These were not found in the ingredient dictionary and are NOT being "
            "filtered. Ask the user to give the name as printed on the label."
        )
    return out


def apply_allergen_filter(
    rows: list[tuple[object, Analysis, dict]], resolved: ResolvedAllergens
) -> dict:
    """Drop products containing a recorded allergen.

    Takes (key, analysis, payload) triples and returns the payloads that
    survived plus a count and reasons for those that did not. Called by the
    dispatcher on every product-returning tool, so no tool can skip it.
    """
    kept: list[dict] = []
    skipped: list[dict] = []

    for _key, analysis, payload in rows:
        reason = blocked_reason(analysis, resolved)
        if reason is None:
            kept.append(payload)
        else:
            skipped.append({"name": f"{payload.get('brand', '')} {payload.get('name', '')}".strip(), "reason": reason})

    result: dict = {"products": kept}
    if skipped:
        result["skipped_for_allergens"] = len(skipped)
        result["skipped"] = skipped[:5]
    return result


# ---------------------------------------------------------------------------
# IO halves
# ---------------------------------------------------------------------------


async def _load_products(ctx: ChatContext, stmt) -> list[Product]:
    return list((await ctx.session.execute(stmt)).scalars().unique())


async def _summarise(
    ctx: ChatContext, products: list[Product]
) -> list[tuple[Product, Analysis, object, str]]:
    prices = await latest_prices(ctx.session, [p.id for p in products])
    out = []
    for product in products:
        analysis = build_analysis(product)
        rows = prices.get(product.id, [])
        out.append(
            (product, analysis, to_summary(product, rows, analysis), _currency_of(rows))
        )
    return out


async def _find_one(ctx: ChatContext, slug: str) -> Product | None:
    stmt = product_query().where(Product.slug == slug)
    found = await _load_products(ctx, stmt)
    return found[0] if found else None


async def search_products(ctx: ChatContext, query: str, category: str | None = None,
                          max_price: float | None = None) -> dict:
    pattern = f"%{(query or '').strip()}%"
    stmt = (
        product_query()
        .join(Brand, Brand.id == Product.brand_id)
        .where(or_(Product.name.ilike(pattern), Brand.name.ilike(pattern)))
    )
    if category:
        stmt = stmt.where(Product.category == category)

    rows = await _summarise(ctx, await _load_products(ctx, stmt))

    triples = []
    for product, analysis, summary, currency in rows:
        if max_price is not None and (summary.best_price is None or summary.best_price > max_price):
            continue
        triples.append((product.id, analysis, format_summary(summary, currency=ctx.currency)))

    filtered = apply_allergen_filter(triples, ctx.allergens)
    filtered["products"] = filtered["products"][:MAX_RESULTS]
    if not filtered["products"] and not filtered.get("skipped_for_allergens"):
        filtered["note"] = "No products matched that search."
    return filtered


async def recommend_products(
    ctx: ChatContext,
    skin_type: str = "normal",
    concerns: list[str] | None = None,
    sensitive: bool = False,
    fragrance_free: bool = False,
    budget_max: float | None = None,
    category: str | None = None,
) -> dict:
    concerns = concerns or []

    stmt = product_query()
    if category:
        stmt = stmt.where(Product.category == category)

    products = await _load_products(ctx, stmt)
    prices = await latest_prices(ctx.session, [p.id for p in products])
    concern_labels = {
        c.key: c.label for c in (await ctx.session.execute(select(Concern))).scalars()
    }

    profile = SkinProfile(
        skin_type=skin_type,
        concerns=concerns,
        sensitive=sensitive or skin_type == "sensitive",
        acne_prone="acne" in concerns,
        fragrance_free=fragrance_free or "fragrance" in ctx.allergens.groups,
        budget_max=budget_max,
        categories=[category] if category else [],
    )

    analyses: dict[int, Analysis] = {}
    summaries: dict[int, object] = {}
    scored = []
    for product in products:
        analysis = build_analysis(product)
        summary = to_summary(product, prices.get(product.id, []), analysis)
        analyses[product.id] = analysis
        summaries[product.id] = summary
        listing_prices = prices.get(product.id, [])
        scored.append(
            score_product(
                product_id=product.id,
                analysis=analysis,
                profile=profile,
                price=summary.best_price,
                in_stock=any(p["in_stock"] for p in listing_prices) or not listing_prices,
                concern_labels=concern_labels,
            )
        )

    # Rank generously, then filter for allergens, so an allergen-heavy top of
    # the list does not leave the user with nothing.
    top = rank(scored, limit=MAX_RESULTS * 3)
    triples = [
        (
            s.product_id,
            analyses[s.product_id],
            format_summary(
                summaries[s.product_id],
                reasons=s.reasons,
                warnings=s.warnings,
                currency=ctx.currency,
            ),
        )
        for s in top
    ]

    filtered = apply_allergen_filter(triples, ctx.allergens)
    filtered["products"] = filtered["products"][:MAX_RESULTS]
    if not filtered["products"] and not filtered.get("skipped_for_allergens"):
        filtered["note"] = "Nothing in the catalog scored well enough for that profile."
    return filtered


async def get_product_details(ctx: ChatContext, slug: str) -> dict:
    product = await _find_one(ctx, slug)
    if product is None:
        return {"error": f"No product with slug {slug!r}."}

    analysis = build_analysis(product)
    prices = await latest_prices(ctx.session, [product.id])
    summary = to_summary(product, prices.get(product.id, []), analysis)

    payload = format_summary(summary, currency=ctx.currency)
    payload["ingredients"] = format_ingredients(analysis)

    reason = blocked_reason(analysis, ctx.allergens)
    if reason is not None:
        payload["unsuitable"] = f"This product {reason}, which the user is avoiding."
    return payload


async def compare_prices(ctx: ChatContext, slug: str) -> dict:
    product = await _find_one(ctx, slug)
    if product is None:
        return {"error": f"No product with slug {slug!r}."}

    prices = await latest_prices(ctx.session, [product.id])
    history = await price_history(ctx.session, product.id, days=90)
    lows = [p.price for series in history for p in series.points]

    rows = prices.get(product.id, [])
    out = format_prices(rows, min(lows) if lows else None, currency=ctx.currency)
    out["product"] = f"{product.brand.name} {product.name}" if product.brand else product.name
    return out


async def find_cheaper_dupes(ctx: ChatContext, slug: str) -> dict:
    product = await _find_one(ctx, slug)
    if product is None:
        return {"error": f"No product with slug {slug!r}."}

    rows = await _summarise(ctx, await _load_products(ctx, product_query()))
    analyses = {p.id: a for p, a, _, _ in rows}
    summaries = {p.id: s for p, _, s, _ in rows}
    currencies = {p.id: c for p, _, _, c in rows}

    target = summaries[product.id]
    scores = find_dupes(
        target_id=product.id,
        target=analyses[product.id],
        target_price=target.best_price,
        target_category=target.category,
        candidates=[
            (p.id, analyses[p.id], summaries[p.id].best_price, summaries[p.id].category)
            for p, _, _, _ in rows
        ],
    )

    triples = []
    for score in scores[: MAX_RESULTS * 2]:
        summary = summaries.get(score.product_id)
        if summary is None:
            continue
        payload = format_summary(summary, currency=ctx.currency)
        payload["similarity"] = round(score.similarity, 3)
        payload["shared_actives"] = score.shared_actives
        if score.savings is not None:
            payload["saves"] = round(score.savings, 2)
        triples.append((score.product_id, analyses[score.product_id], payload))

    filtered = apply_allergen_filter(triples, ctx.allergens)
    filtered["products"] = filtered["products"][:MAX_RESULTS]
    if not filtered["products"] and not filtered.get("skipped_for_allergens"):
        filtered["note"] = "No cheaper product with a comparable ingredient profile."
    return filtered


async def check_routine_conflicts(ctx: ChatContext, slugs: list[str]) -> dict:
    if not slugs or len(slugs) < 2:
        return {"error": "Need at least two product slugs to check for conflicts."}

    products = await _load_products(ctx, product_query().where(Product.slug.in_(slugs)))
    if len(products) < 2:
        return {"error": "Could not find at least two of those products."}

    pairs = [(p.name, build_analysis(p)) for p in products]
    return format_conflicts(detect_conflicts(pairs))


async def record_allergy(ctx: ChatContext, terms: list[str]) -> dict:
    if not terms:
        return {"error": "No terms given."}
    resolved = ctx.add_allergens(terms)
    return format_allergen_state(resolved)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "record_allergy": record_allergy,
    "search_products": search_products,
    "recommend_products": recommend_products,
    "get_product_details": get_product_details,
    "compare_prices": compare_prices,
    "find_cheaper_dupes": find_cheaper_dupes,
    "check_routine_conflicts": check_routine_conflicts,
}


async def execute_tool(name: str, args: dict, ctx: ChatContext) -> dict:
    """Run one tool call. Never raises - the model gets an error payload instead.

    A tool that throws would end the turn with a stack trace and no reply. An
    error the model can read lets it apologise or try a different approach.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool {name!r}."}

    try:
        return await handler(ctx, **(args or {}))
    except TypeError as exc:
        logger.warning("bad arguments for %s: %s", name, exc)
        return {"error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("tool %s failed", name)
        return {"error": f"{name} failed: {exc}"}
