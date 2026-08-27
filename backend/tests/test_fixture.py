"""The committed fixture is how a teammate gets a catalog, so a broken one means
a fresh clone silently shows nothing. These check the file itself rather than the
load path, which needs a database.
"""

import json
from pathlib import Path

import pytest

from app.jobs.fixture import FIXTURE_PATH, SCHEMA_VERSION
from app.jobs.ingest import is_in_scope
from app.models.enums import Category, MatchMethod


@pytest.fixture(scope="module")
def payload() -> dict:
    assert FIXTURE_PATH.exists(), f"no fixture at {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestFixtureFile:
    def test_schema_version_matches_the_loader(self, payload):
        assert payload["schema_version"] == SCHEMA_VERSION

    def test_has_products_and_retailers(self, payload):
        assert payload["products"], "fixture has no products"
        assert payload["retailers"], "fixture has no retailers"

    def test_records_when_it_was_generated(self, payload):
        # Prices in a fixture are stale by definition; undated stale prices are worse.
        assert payload.get("generated_at")

    def test_sorted_by_slug(self, payload):
        # Stable ordering is what keeps a re-dump reviewable as a diff.
        slugs = [p["slug"] for p in payload["products"]]
        assert slugs == sorted(slugs)

    def test_slugs_are_unique(self, payload):
        slugs = [p["slug"] for p in payload["products"]]
        assert len(slugs) == len(set(slugs))

    def test_barcodes_are_unique(self, payload):
        upcs = [p["upc"] for p in payload["products"] if p.get("upc")]
        assert len(upcs) == len(set(upcs)), "same GTIN on two products"


class TestFixtureContents:
    def test_every_product_has_an_image(self, payload):
        # The whole point of scraping live data is the images.
        missing = [p["slug"] for p in payload["products"] if not p.get("image_url")]
        assert not missing, f"products with no image: {missing}"

    def test_every_product_has_a_priced_listing(self, payload):
        for product in payload["products"]:
            listings = product.get("listings") or []
            assert listings, f"{product['slug']} has no listing"
            assert any(
                listing.get("price") is not None for listing in listings
            ), f"{product['slug']} has no priced listing"

    def test_listings_reference_declared_retailers(self, payload):
        known = {r["slug"] for r in payload["retailers"]}
        for product in payload["products"]:
            for listing in product["listings"]:
                assert listing["retailer"] in known, (
                    f"{product['slug']} references unknown retailer "
                    f"{listing['retailer']!r}"
                )

    def test_no_synthetic_retailers(self, payload):
        # Synthetic products already ship as seed_products.py.
        for retailer in payload["retailers"]:
            assert not retailer["scraper_key"].startswith("seed-")

    def test_categories_and_methods_are_valid_enums(self, payload):
        for product in payload["products"]:
            Category(product["category"])
            for listing in product["listings"]:
                MatchMethod(listing["match_method"])

    def test_everything_is_in_scope(self, payload):
        # A non-skincare product in the committed fixture would spread to every
        # clone, which is worse than one that only reached a local database.
        out = [
            p["slug"] for p in payload["products"] if not is_in_scope(None, p["name"])
        ]
        assert not out, f"out-of-scope products in fixture: {out}"

    def test_ingredient_lists_have_no_blanks_or_duplicates(self, payload):
        for product in payload["products"]:
            names = product.get("ingredients") or []
            assert all(n.strip() for n in names), f"{product['slug']} has a blank name"
            lowered = [n.lower() for n in names]
            assert len(lowered) == len(set(lowered)), f"{product['slug']} repeats an ingredient"

    def test_the_file_is_small_enough_to_review(self, payload):
        # A fixture is only better than a committed database while it stays
        # reviewable. If this trips, the answer is fewer products, not a bigger cap.
        size = Path(FIXTURE_PATH).stat().st_size
        assert size < 2_000_000, f"fixture is {size} bytes"
