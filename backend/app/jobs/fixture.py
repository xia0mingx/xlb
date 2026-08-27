"""Share a live-scraped catalog through the repository.

`jobs/ingest.py` produces real products, but only on the machine that ran it -
`xlb.db` is gitignored, and it should stay that way. Without something like this,
a teammate cloning the repo gets an empty catalog (synthetic products are hidden
by default) and the only way to fill it is to re-scrape, which returns a
*different* set: the retailer's feed reorders, prices move, and INCIDecoder
coverage varies run to run.

So the catalog travels as a JSON fixture instead of a database file. It is text,
so it diffs and reviews like anything else; it is small; and loading it reproduces
one specific catalog exactly.

    python -m app.jobs.fixture dump     # DB  -> app/data/live_products.json
    python -m app.jobs.fixture load     # JSON -> DB

`load` reuses the same upsert helpers as the live ingest, so a fixture product and
a freshly scraped one end up identical in the database.

Prices in a fixture are a snapshot from when it was dumped, not live. `generated_at`
records when, because a price with no date is worse than no price.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import Base, SessionLocal, engine
from app.models import Listing, Product, Retailer
from app.models.enums import Category, MatchMethod
from app.scrapers.base import ScrapedProduct

logger = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "live_products.json"

# Only products with a real listing are worth sharing; the synthetic ones are
# already in the repo as seed_products.py.
SYNTHETIC_PREFIX = "seed-"

SCHEMA_VERSION = 1


def _category_value(category) -> str:
    return getattr(category, "value", str(category))


async def dump(path: Path = FIXTURE_PATH) -> dict:
    """Write every live product to a JSON fixture."""
    async with SessionLocal() as session:
        live_ids = set(
            (
                await session.execute(
                    select(Listing.product_id)
                    .join(Retailer, Retailer.id == Listing.retailer_id)
                    .where(Retailer.scraper_key.notlike(f"{SYNTHETIC_PREFIX}%"))
                )
            ).scalars()
        )
        if not live_ids:
            raise SystemExit(
                "no live products in the database - run app.jobs.ingest first"
            )

        products = list(
            (
                await session.execute(
                    select(Product)
                    .options(
                        selectinload(Product.brand),
                        selectinload(Product.ingredients),
                        selectinload(Product.concerns),
                        selectinload(Product.listings).selectinload(Listing.retailer),
                        selectinload(Product.listings).selectinload(Listing.snapshots),
                    )
                    .where(Product.id.in_(live_ids))
                )
            )
            .scalars()
            .unique()
        )

        # Ingredient and concern rows are reached through the link objects, which
        # need their own eager load to avoid a lazy fetch outside the async context.
        from app.models import Concern, Ingredient, ProductConcern, ProductIngredient

        ingredient_names = {
            row.id: row.inci_name
            for row in (await session.execute(select(Ingredient))).scalars()
        }
        concern_keys = {
            row.id: row.key for row in (await session.execute(select(Concern))).scalars()
        }

        retailers: dict[str, dict] = {}
        entries: list[dict] = []

        for product in products:
            listings = []
            for listing in product.listings:
                retailer = listing.retailer
                if retailer is None or retailer.scraper_key.startswith(SYNTHETIC_PREFIX):
                    continue

                retailers.setdefault(
                    retailer.slug,
                    {
                        "slug": retailer.slug,
                        "name": retailer.name,
                        "base_url": retailer.base_url,
                        "scraper_key": retailer.scraper_key,
                    },
                )

                # Newest snapshot only. Full history would multiply the file size
                # for data that is stale the moment it is committed.
                newest = max(
                    listing.snapshots, key=lambda s: s.scraped_at, default=None
                )
                listings.append(
                    {
                        "retailer": retailer.slug,
                        "sku": listing.retailer_sku,
                        "url": listing.url,
                        "title_raw": listing.title_raw,
                        "in_stock": bool(listing.in_stock),
                        "match_confidence": float(listing.match_confidence),
                        "match_method": _category_value(listing.match_method),
                        "price": float(newest.price) if newest and newest.price is not None else None,
                        "was_price": float(newest.was_price) if newest and newest.was_price else None,
                        "currency": newest.currency if newest else "USD",
                    }
                )

            if not listings:
                continue

            entries.append(
                {
                    "brand": product.brand.name if product.brand else "Unknown",
                    "name": product.name,
                    "slug": product.slug,
                    "category": _category_value(product.category),
                    "size_value": product.size_value,
                    "size_unit": product.size_unit,
                    "upc": product.upc,
                    "image_url": product.image_url,
                    "description": product.description,
                    "ingredients": [
                        ingredient_names[link.ingredient_id]
                        for link in sorted(product.ingredients, key=lambda x: x.position)
                        if link.ingredient_id in ingredient_names
                    ],
                    "concerns": {
                        concern_keys[link.concern_id]: round(float(link.weight), 3)
                        for link in product.concerns
                        if link.concern_id in concern_keys
                    },
                    "listings": sorted(listings, key=lambda x: x["retailer"]),
                }
            )

    # Sorted by slug so the file is stable across dumps and diffs stay readable.
    entries.sort(key=lambda e: e["slug"])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "note": (
            "Live catalog snapshot, produced by app.jobs.fixture dump. Prices were "
            "current when generated, not now. Load with: python -m app.jobs.fixture load"
        ),
        "retailers": [retailers[key] for key in sorted(retailers)],
        "products": entries,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    stats = {
        "products": len(entries),
        "retailers": len(retailers),
        "listings": sum(len(e["listings"]) for e in entries),
        "with_ingredients": sum(1 for e in entries if e["ingredients"]),
        "bytes": path.stat().st_size,
    }
    return stats


async def load(path: Path = FIXTURE_PATH, dry_run: bool = False) -> dict:
    """Read a JSON fixture into the database.

    Deliberately reuses ingest.py's upsert helpers rather than writing rows
    directly: a fixture product and a scraped one must be indistinguishable
    afterwards, and duplicating the upsert rules is how they drift apart.
    """
    from app.jobs.ingest import (
        attach_concerns,
        attach_ingredients,
        ensure_brand,
        ensure_reference_data,
        find_existing_product,
        upsert_listing,
    )

    if not path.exists():
        raise SystemExit(f"no fixture at {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SystemExit(
            f"fixture schema_version {version!r}, this code expects {SCHEMA_VERSION}"
        )

    logger.info(
        "loading %s products from fixture generated %s",
        len(payload.get("products", [])),
        payload.get("generated_at", "?"),
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    stats = {"created": 0, "updated": 0, "listings": 0, "snapshots": 0, "skipped": 0}

    async with SessionLocal() as session:
        ingredient_rows, concerns = await ensure_reference_data(session)
        from app.services.text import normalize_text

        cache = {normalize_text(name): row for name, row in ingredient_rows.items()}

        retailers: dict[str, Retailer] = {}
        for entry in payload.get("retailers", []):
            existing = (
                await session.execute(
                    select(Retailer).where(Retailer.scraper_key == entry["scraper_key"])
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = Retailer(
                    name=entry["name"],
                    slug=entry["slug"],
                    base_url=entry["base_url"],
                    scraper_key=entry["scraper_key"],
                    is_active=True,
                )
                session.add(existing)
                await session.flush()
            retailers[entry["slug"]] = existing

        brands: dict[str, object] = {}
        await session.commit()

        for entry in payload.get("products", []):
            brand = await ensure_brand(session, entry.get("brand"), brands)
            slug = entry["slug"]

            # find_existing_product matches on barcode then slug, exactly as the
            # live path does, so loading a fixture over a scraped catalog updates
            # rather than duplicates.
            probe = ScrapedProduct(
                sku=slug, url="", title=entry["name"], upc=entry.get("upc")
            )
            product = await find_existing_product(session, probe, slug)
            created = product is None
            if product is None:
                product = Product(brand_id=brand.id, name=entry["name"][:300], slug=slug)
                session.add(product)

            product.brand_id = brand.id
            product.name = entry["name"][:300]
            product.category = Category(entry["category"])
            product.size_value = entry.get("size_value")
            product.size_unit = entry.get("size_unit")
            product.upc = entry.get("upc")
            product.description = entry.get("description")
            product.image_url = (entry.get("image_url") or None)
            names = entry.get("ingredients") or []
            if names:
                product.ingredients_raw = ", ".join(names)
            await session.flush()

            stats["created" if created else "updated"] += 1

            if names:
                await attach_ingredients(session, product, names, cache)
                await attach_concerns(
                    session,
                    product,
                    {k: float(v) for k, v in (entry.get("concerns") or {}).items()},
                    concerns,
                )

            for listing_entry in entry.get("listings", []):
                retailer = retailers.get(listing_entry["retailer"])
                if retailer is None:
                    stats["skipped"] += 1
                    continue

                scraped = ScrapedProduct(
                    sku=listing_entry["sku"],
                    url=listing_entry["url"],
                    title=listing_entry.get("title_raw") or entry["name"],
                    price=listing_entry.get("price"),
                    was_price=listing_entry.get("was_price"),
                    currency=listing_entry.get("currency") or "USD",
                    in_stock=bool(listing_entry.get("in_stock", True)),
                    upc=entry.get("upc"),
                    image_url=entry.get("image_url"),
                )
                _, listing_created = await upsert_listing(
                    session,
                    product,
                    retailer,
                    scraped,
                    confidence=float(listing_entry.get("match_confidence", 1.0)),
                    method=MatchMethod(listing_entry.get("match_method") or "manual"),
                    threshold=0.0,  # the fixture already recorded the verdict
                )
                if listing_created:
                    stats["listings"] += 1
                if scraped.price is not None:
                    stats["snapshots"] += 1

            if not dry_run:
                await session.commit()

        if dry_run:
            await session.rollback()
            logger.info("dry run - rolled back, nothing written")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump or load the live catalog fixture.")
    parser.add_argument("action", choices=["dump", "load"])
    parser.add_argument("--path", type=Path, default=FIXTURE_PATH)
    parser.add_argument(
        "--dry-run", action="store_true", help="load only: read and report, write nothing"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.action == "dump":
        stats = asyncio.run(dump(args.path))
        print(f"\nwrote {args.path}")
    else:
        stats = asyncio.run(load(args.path, dry_run=args.dry_run))
        print("\nloaded fixture:")

    for key, value in stats.items():
        print(f"  {key:20} {value}")


if __name__ == "__main__":
    main()
