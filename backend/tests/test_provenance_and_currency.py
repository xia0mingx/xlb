"""Tests for ingredient provenance and display currencies.

Both are presentation concerns, but both are easy to get quietly wrong: a
misclassified ingredient is a factual error on the product page, and a currency
that converts in the wrong direction shows a plausible number that is simply not
the price.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import currency
from app.services.provenance import (
    NATURAL,
    NATURE_IDENTICAL,
    SYNTHETIC,
    classify,
    summarise,
)

DICTIONARY = json.loads(
    (Path(__file__).resolve().parent.parent / "app" / "data" / "ingredients.json").read_text()
)


# --- provenance -------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        # Botanicals and minerals
        ("Centella Asiatica Extract", NATURAL),
        ("Butyrospermum Parkii Butter", NATURAL),
        ("Melaleuca Alternifolia Leaf Oil", NATURAL),
        ("Zinc Oxide", NATURAL),
        ("Snail Secretion Filtrate", NATURAL),
        ("Galactomyces Ferment Filtrate", NATURAL),
        # Manufactured, but the same molecule nature makes
        ("Squalane", NATURE_IDENTICAL),
        ("Glycerin", NATURE_IDENTICAL),
        ("Niacinamide", NATURE_IDENTICAL),
        ("Hyaluronic Acid", NATURE_IDENTICAL),
        ("Ascorbic Acid", NATURE_IDENTICAL),
        ("Salicylic Acid", NATURE_IDENTICAL),
        # No natural counterpart
        ("Dimethicone", SYNTHETIC),
        ("Phenoxyethanol", SYNTHETIC),
        ("Avobenzone", SYNTHETIC),
        ("Sodium Lauryl Sulfate", SYNTHETIC),
        ("3-O-Ethyl Ascorbic Acid", SYNTHETIC),
        ("Retinyl Palmitate", SYNTHETIC),
        ("Petrolatum", SYNTHETIC),
    ],
)
def test_known_ingredients_classify_as_expected(name, expected):
    assert classify(name) == expected


def test_undisclosed_fragrance_is_not_guessed():
    """`Fragrance` is a mixture that may be either; saying so beats picking one."""
    assert classify("Fragrance") is None
    assert classify("Parfum") is None


def test_classification_is_case_and_spacing_insensitive():
    assert classify("centella  asiatica extract") == NATURAL
    assert classify("  DIMETHICONE ") == SYNTHETIC


def test_unknown_ingredient_returns_none():
    assert classify("Unobtainium Extractum") is None
    assert classify("") is None


def test_botanical_fallback_covers_ingredients_added_later():
    """Upstream extends ingredients.json; a binomial shape should still classify."""
    assert classify("Rosmarinus Officinalis Leaf Extract") == NATURAL
    assert classify("Hibiscus Sabdariffa Flower Extract") == NATURAL


def test_fallback_does_not_claim_two_word_chemicals():
    """A two-word chemical name must not be mistaken for a Latin binomial."""
    assert classify("Sodium Hydroxide") == SYNTHETIC  # explicit, not fallback
    assert classify("Butylene Glycol") == SYNTHETIC


def test_dictionary_is_almost_fully_classified():
    """Coverage guard: a big drop means the dictionary grew past the tables."""
    classified = sum(1 for e in DICTIONARY if classify(e["inci_name"]) is not None)
    coverage = classified / len(DICTIONARY)
    assert coverage > 0.95, f"only {coverage:.0%} of ingredients classified"


def test_summarise_counts_every_bucket_including_unknown():
    counts = summarise([NATURAL, NATURAL, SYNTHETIC, None])
    assert counts == {NATURAL: 2, NATURE_IDENTICAL: 0, SYNTHETIC: 1, "unknown": 1}


def test_summarise_totals_match_the_input_length():
    sources = [classify(e["inci_name"]) for e in DICTIONARY]
    assert sum(summarise(sources).values()) == len(DICTIONARY)


# --- currency ---------------------------------------------------------------


def test_rates_are_the_agreed_constants():
    assert currency.RATES["USD"] == 1.0
    assert currency.RATES["SGD"] == 1.27
    assert currency.RATES["EUR"] == 0.87


def test_conversion_multiplies_from_usd():
    # Direction matters: dividing instead of multiplying gives a plausible but
    # wrong figure, which is the failure this pins.
    assert currency.convert(100.0, "SGD") == 127.0
    assert currency.convert(100.0, "EUR") == 87.0
    assert currency.convert(100.0, "USD") == 100.0


def test_usd_conversion_is_the_identity():
    for amount in (0.0, 9.99, 12.64, 1234.56):
        assert currency.convert(amount, "USD") == amount


def test_none_passes_through_unconverted():
    assert currency.convert(None, "SGD") is None


def test_unknown_currency_falls_back_to_usd():
    assert currency.resolve("XYZ") == "USD"
    assert currency.resolve(None) == "USD"
    assert currency.convert(10.0, "XYZ") == 10.0


def test_lowercase_codes_are_accepted():
    assert currency.resolve("sgd") == "SGD"
    assert currency.convert(100.0, "eur") == 87.0


def test_formatting_uses_the_right_symbol():
    assert currency.format_amount(12.64, "USD") == "$12.64"
    assert currency.format_amount(12.64, "SGD") == "S$16.05"
    assert currency.format_amount(12.64, "EUR") == "€11.00"
    assert currency.format_amount(None, "SGD") == "unavailable"


@pytest.mark.parametrize(
    "timezone,expected",
    [
        ("Asia/Singapore", "SGD"),
        ("Europe/Paris", "EUR"),
        ("Europe/Berlin", "EUR"),
        ("Europe/Dublin", "EUR"),
        ("Atlantic/Canary", "EUR"),
        # In Europe, but not in the euro area.
        ("Europe/London", "USD"),
        ("Europe/Zurich", "USD"),
        ("Europe/Oslo", "USD"),
        ("Europe/Stockholm", "USD"),
        ("Europe/Warsaw", "USD"),
        ("Europe/Prague", "USD"),
        # Everywhere else.
        ("America/New_York", "USD"),
        ("Asia/Tokyo", "USD"),
        ("Asia/Kuala_Lumpur", "USD"),
        (None, "USD"),
        ("Not/AZone", "USD"),
    ],
)
def test_region_maps_to_currency(timezone, expected):
    assert currency.for_timezone(timezone) == expected


def test_catalogue_exposes_all_three_and_admits_the_rates_are_fixed():
    payload = currency.catalogue()
    assert {c["code"] for c in payload["currencies"]} == {"USD", "SGD", "EUR"}
    assert payload["base"] == "USD"
    assert payload["is_indicative"] is True
    for entry in payload["currencies"]:
        assert entry["symbol"] and entry["name"] and entry["rate"] > 0
