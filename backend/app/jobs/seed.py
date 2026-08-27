"""Populate the database with synthetic development data.

Generates the whole graph: brands, products, ingredient links, concerns,
retailers, listings and 90 days of price history. Prices are randomized around a
base with per-retailer bias, occasional sales and realistic drift, so the price
comparison, history chart and "biggest drops" views all have something true to
show.

Deterministic: a fixed RNG seed means the same catalog every run, which keeps
screenshots and tests stable.

    python -m app.jobs.seed [--reset]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from slugify import slugify
from sqlalchemy import delete, select

from app.data.seed_products import SEED_PRODUCTS, SEED_RETAILERS
from app.db import Base, SessionLocal, engine
from app.models import (
    Brand,
    Concern,
    Ingredient,
    Listing,
    PriceSnapshot,
    Product,
    ProductConcern,
    ProductIngredient,
    Retailer,
)
from app.models.enums import Category, MatchMethod, ScrapeStatus
from app.services.analysis import config
from app.services.inci import ingredient_dictionary

logger = logging.getLogger(__name__)

RNG_SEED = 20260827
HISTORY_DAYS = 90
SNAPSHOT_EVERY_DAYS = 3

# How each retailer prices relative to the product's base price, and how likely
# it is to stock a given product at all.
RETAILER_BIAS = {
    "glowmart": (0.88, 0.95),
    "kbeauty-depot": (0.82, 0.85),
    "dermashop": (1.06, 0.75),
    "beautybazaar": (0.97, 0.80),
}


async def reset_tables() -> None:
    """Drop the seeded rows without touching the schema."""
    async with SessionLocal() as session:
        for model in (
            PriceSnapshot, Listing, ProductIngredient, ProductConcern,
            Product, Brand, Retailer, Ingredient, Concern,
        ):
            await session.execute(delete(model))
        await session.commit()


async def seed_ingredients(session) -> dict[str, Ingredient]:
    existing = {
        row.inci_name: row for row in (await session.execute(select(Ingredient))).scalars()
    }
    created: dict[str, Ingredient] = dict(existing)

    for key, entry in ingredient_dictionary().items():
        name = entry["inci_name"]
        if name in created:
            continue
        ingredient = Ingredient(
            inci_name=name,
            slug=slugify(name) or key,
            common_name=entry.get("common_name"),
            function=entry.get("function"),
            is_active=bool(entry.get("is_active")),
            is_irritant=bool(entry.get("is_irritant")),
            comedogenic_rating=entry.get("comedogenic_rating"),
            active_group=entry.get("active_group"),
            description=entry.get("description"),
        )
        session.add(ingredient)
        created[name] = ingredient

    await session.flush()
    return created


async def seed_concerns(session) -> dict[str, Concern]:
    existing = {row.key: row for row in (await session.execute(select(Concern))).scalars()}
    for entry in config()["concerns"]:
        if entry["key"] in existing:
            continue
        concern = Concern(
            key=entry["key"], label=entry["label"], description=entry.get("description")
        )
        session.add(concern)
        existing[entry["key"]] = concern
    await session.flush()
    return existing


async def seed_retailers(session) -> dict[str, Retailer]:
    existing = {row.slug: row for row in (await session.execute(select(Retailer))).scalars()}
    for name, slug, url in SEED_RETAILERS:
        if slug in existing:
            continue
        retailer = Retailer(
            name=name, slug=slug, base_url=url, scraper_key=f"seed-{slug}", is_active=True
        )
        session.add(retailer)
        existing[slug] = retailer
    await session.flush()
    return existing


def _price_series(rng: random.Random, base: float, bias: float) -> list[tuple[datetime, float, float | None]]:
    """Build a plausible price history ending at 'now'.

    Random walk with mild drift, plus occasional multi-week sales - which is what
    makes the history chart and the price-drop view worth looking at.
    """
    now = datetime.now(timezone.utc)
    anchor = round(base * bias * rng.uniform(0.97, 1.03), 2)
    price = anchor

    sale_until: datetime | None = None
    sale_depth = 1.0

    points: list[tuple[datetime, float, float | None]] = []
    for days_ago in range(HISTORY_DAYS, -1, -SNAPSHOT_EVERY_DAYS):
        when = now - timedelta(days=days_ago)

        # Drift back toward the anchor so the walk does not wander off.
        price += (anchor - price) * 0.25 + rng.uniform(-0.4, 0.4)
        price = max(round(price, 2), round(anchor * 0.7, 2))

        if sale_until and when > sale_until:
            sale_until, sale_depth = None, 1.0
        if sale_until is None and rng.random() < 0.07:
            sale_depth = rng.choice([0.85, 0.8, 0.75, 0.7])
            sale_until = when + timedelta(days=rng.choice([9, 12, 18]))

        if sale_until:
            effective = round(price * sale_depth, 2)
            points.append((when, effective, round(price, 2)))
        else:
            points.append((when, round(price, 2), None))

    return points


async def seed_catalog(session, ingredients, concerns, retailers) -> dict[str, int]:
    rng = random.Random(RNG_SEED)
    stats = {"brands": 0, "products": 0, "listings": 0, "snapshots": 0}

    brands: dict[str, Brand] = {
        row.name: row for row in (await session.execute(select(Brand))).scalars()
    }

    for entry in SEED_PRODUCTS:
        brand_name, name, category, size_value, size_unit, base_price, concern_map, inci = entry

        brand = brands.get(brand_name)
        if brand is None:
            brand = Brand(
                name=brand_name,
                slug=slugify(brand_name),
                normalized_name=brand_name.lower(),
            )
            session.add(brand)
            await session.flush()
            brands[brand_name] = brand
            stats["brands"] += 1

        slug = slugify(f"{brand_name} {name}")
        product = Product(
            brand_id=brand.id,
            name=name,
            slug=slug,
            category=Category(category),
            size_value=size_value,
            size_unit=size_unit,
            upc=f"{rng.randrange(10**12, 10**13 - 1)}",
            description=(
                f"{brand_name} {name} - a {category.replace('_', ' ')} "
                f"formulated with {', '.join(inci[:3])}."
            ),
            image_url=None,
            ingredients_raw=", ".join(inci),
        )
        session.add(product)
        await session.flush()
        stats["products"] += 1

        for position, inci_name in enumerate(inci, start=1):
            ingredient = ingredients.get(inci_name)
            if ingredient is None:
                continue
            session.add(
                ProductIngredient(
                    product_id=product.id,
                    ingredient_id=ingredient.id,
                    position=position,
                )
            )

        for concern_key, weight in concern_map.items():
            concern = concerns.get(concern_key)
            if concern is None:
                continue
            session.add(
                ProductConcern(
                    product_id=product.id, concern_id=concern.id, weight=float(weight)
                )
            )

        # Every product is carried by at least two retailers - a product with one
        # listing has nothing to compare, which defeats the point of the app.
        carriers = [
            slug_ for slug_, (_, stock_rate) in RETAILER_BIAS.items()
            if rng.random() < stock_rate
        ]
        if len(carriers) < 2:
            carriers = rng.sample(list(RETAILER_BIAS), 2)

        for retailer_slug in carriers:
            retailer = retailers[retailer_slug]
            bias = RETAILER_BIAS[retailer_slug][0]

            listing = Listing(
                product_id=product.id,
                retailer_id=retailer.id,
                retailer_sku=f"{retailer_slug[:3].upper()}-{product.id:05d}",
                url=f"{retailer.base_url}/products/{slug}",
                title_raw=f"{brand_name} {name} {int(size_value)}{size_unit}",
                in_stock=rng.random() > 0.08,
                last_scraped_at=datetime.now(timezone.utc),
                last_status=ScrapeStatus.OK,
                match_confidence=1.0,
                match_method=MatchMethod.UPC,
                needs_review=False,
            )
            session.add(listing)
            await session.flush()
            stats["listings"] += 1

            for when, price, was_price in _price_series(rng, base_price, bias):
                session.add(
                    PriceSnapshot(
                        listing_id=listing.id,
                        price=price,
                        was_price=was_price,
                        currency="USD",
                        in_stock=listing.in_stock,
                        scraped_at=when,
                    )
                )
                stats["snapshots"] += 1

    await session.commit()
    return stats


async def run(reset: bool = False) -> dict[str, int]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    if reset:
        await reset_tables()

    async with SessionLocal() as session:
        ingredients = await seed_ingredients(session)
        concerns = await seed_concerns(session)
        retailers = await seed_retailers(session)
        await session.commit()
        stats = await seed_catalog(session, ingredients, concerns, retailers)

    stats["ingredients"] = len(ingredients)
    stats["concerns"] = len(concerns)
    stats["retailers"] = len(retailers)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Dewdrop database")
    parser.add_argument("--reset", action="store_true", help="delete existing rows first")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stats = asyncio.run(run(reset=args.reset))
    logger.info("Seeded:")
    for key in ("brands", "products", "listings", "snapshots", "ingredients", "concerns", "retailers"):
        logger.info("  %-11s %s", key, stats.get(key, 0))


if __name__ == "__main__":
    main()
