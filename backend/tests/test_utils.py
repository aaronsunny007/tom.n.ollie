"""Unit tests for the small helpers in app.utils.

These are relied on throughout parsing, seeding and checkout, but had no
direct test coverage of their own.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.utils import make_sku, order_number, slugify, unique_slug


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Chilli Basil Garlic Hummus") == "chilli-basil-garlic-hummus"


def test_slugify_strips_accents_and_punctuation():
    assert slugify("Crème Fraîche & Co.") == "creme-fraiche-co"


def test_slugify_falls_back_to_item_for_empty_input():
    assert slugify("") == "item"
    assert slugify("!!!") == "item"


def test_unique_slug_returns_base_when_available():
    assert unique_slug("Basil Pesto", taken=set()) == "basil-pesto"


def test_unique_slug_appends_suffix_on_collision():
    taken = {"basil-pesto"}
    assert unique_slug("Basil Pesto", taken) == "basil-pesto-2"


def test_unique_slug_finds_next_free_suffix():
    taken = {"basil-pesto", "basil-pesto-2", "basil-pesto-3"}
    assert unique_slug("Basil Pesto", taken) == "basil-pesto-4"


def test_make_sku_combines_truncated_uppercased_parts():
    sku = make_sku("Hummus", "Traditional Hummus", "200g")
    assert sku == "HUM-TRADITIO-200G"


def test_make_sku_falls_back_to_item_for_blank_category():
    # slugify() never returns an empty string, so a blank category still
    # contributes a part rather than being dropped.
    sku = make_sku("", "Traditional Hummus", "200g")
    assert sku == "ITE-TRADITIO-200G"


def test_order_number_format():
    fixed = datetime(2025, 3, 4, tzinfo=timezone.utc)
    number = order_number(fixed)
    assert re.fullmatch(r"TO-250304-[0-9A-F]{6}", number)
