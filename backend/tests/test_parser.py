"""Parser tests against the real Tom & Ollie product list.

Real data holds the awkward cases that invented test data tidies away: the
trailing space after `Hummus`, the double space after one bullet, the leading
space before the `Sweet Pepper Drops` bullets, and the `Garlicy` spelling.
"""

from __future__ import annotations

from app.parser import Ambiguity, categories, parse, validate_rows

EXPECTED = [
    ("Hummus", "Traditional Hummus"),
    ("Hummus", "Beetroot Hummus"),
    ("Hummus", "Chilli Basil Garlic Hummus"),
    ("Hummus", "Vegan Chilli Basil Garlic Hummus"),
    ("Hummus", "Caramelised Onion Hummus"),
    ("Hummus", "Red Pepper Hummus"),
    ("Pesto", "Smoked Tomato Pesto"),
    ("Pesto", "Vegan Basil"),
    ("Pesto", "Basil"),
    ("Pesto", "Lyness Basil"),
    ("Olives", "Pitted Green Olives"),
    ("Olives", "Pitted Kalamata"),
    ("Olives", "Italian Mixed"),
    ("Olives", "House Mix"),
    ("Olives", "Global Mix"),
    ("Olives", "Chilli Basil Garlic Green Olives"),
    ("Olives", "Garlicy Green Olives"),
    ("Sweet Pepper Drops", "Red"),
    ("Sweet Pepper Drops", "Mixed"),
    ("Sweet Pepper Drops", "Yellow"),
]


def test_real_list_parses_exactly(raw_products):
    records, ambiguities = parse(raw_products)
    assert ambiguities == []
    assert [record.as_row() for record in records] == EXPECTED


def test_real_list_has_twenty_products_in_four_categories(raw_products):
    records, _ = parse(raw_products)
    assert len(records) == 20
    assert categories(records) == ["Hummus", "Pesto", "Olives", "Sweet Pepper Drops"]


def test_misspelling_is_preserved(raw_products):
    """`Garlicy` is the product name. Correcting it would be relabelling food."""
    records, _ = parse(raw_products)
    assert ("Olives", "Garlicy Green Olives") in [r.as_row() for r in records]
    assert not any("Garlicky" in r.product for r in records)


def test_shorthand_is_not_expanded(raw_products):
    """Under `Sweet Pepper Drops` the product is `Red`, not `Red Sweet Pepper Drops`."""
    records, _ = parse(raw_products)
    drops = [r.product for r in records if r.category == "Sweet Pepper Drops"]
    assert drops == ["Red", "Mixed", "Yellow"]


def test_double_space_after_bullet_is_stripped(raw_products):
    records, _ = parse(raw_products)
    products = [r.product for r in records]
    assert "Garlicy Green Olives" in products
    assert not any(product.startswith(" ") for product in products)


def test_trailing_space_on_heading_is_trimmed(raw_products):
    records, _ = parse(raw_products)
    assert all(record.category == record.category.strip() for record in records)
    assert "Hummus" in categories(records)


def test_leading_space_before_bullets_is_not_treated_as_nesting(raw_products):
    """The `Sweet Pepper Drops` bullets are all indented by one space together."""
    records, ambiguities = parse(raw_products)
    assert [a for a in ambiguities if a.kind == "nested_bullet"] == []
    assert sum(1 for r in records if r.category == "Sweet Pepper Drops") == 3


def test_line_numbers_point_at_the_source():
    text = "Hummus\n- Traditional Hummus\n\nPesto\n- Basil\n"
    records, _ = parse(text)
    assert [(r.product, r.line) for r in records] == [("Traditional Hummus", 2), ("Basil", 5)]


def test_product_before_any_heading_is_ambiguous():
    records, ambiguities = parse("- Orphan Olives\nOlives\n- Pitted Kalamata\n")
    assert [r.product for r in records] == ["Pitted Kalamata"]
    assert [a.kind for a in ambiguities] == ["orphan_product"]
    assert ambiguities[0].line == 1


def test_empty_category_is_ambiguous():
    _, ambiguities = parse("Hummus\nPesto\n- Basil\n")
    kinds = [a.kind for a in ambiguities]
    assert "empty_category" in kinds


def test_trailing_empty_category_is_ambiguous():
    _, ambiguities = parse("Pesto\n- Basil\nOlives\n")
    assert [a.kind for a in ambiguities] == ["empty_category"]


def test_bullet_with_no_text_is_ambiguous():
    records, ambiguities = parse("Olives\n-\n- House Mix\n")
    assert [r.product for r in records] == ["House Mix"]
    assert [a.kind for a in ambiguities] == ["empty_bullet"]


def test_nested_bullet_is_reported_not_guessed():
    records, ambiguities = parse("Olives\n- House Mix\n    - Extra Garlic\n")
    assert [r.product for r in records] == ["House Mix"]
    assert [a.kind for a in ambiguities] == ["nested_bullet"]


def test_numbered_items_are_ambiguous():
    _, ambiguities = parse("Method\n1. Blend the chickpeas\n")
    assert any(a.kind == "numbered_item" for a in ambiguities)


def test_duplicate_product_in_one_category_is_reported():
    records, ambiguities = parse("Olives\n- House Mix\n- House Mix\n")
    assert len(records) == 1
    assert [a.kind for a in ambiguities] == ["duplicate_product"]


def test_repeated_heading_is_reported():
    _, ambiguities = parse("Olives\n- House Mix\nPesto\n- Basil\nOlives\n- Global Mix\n")
    assert [a.kind for a in ambiguities] == ["repeated_category"]


def test_same_product_in_two_categories_is_allowed():
    """`Basil` under Pesto and under Olives are different products, not a duplicate."""
    records, ambiguities = parse("Pesto\n- Basil\nOlives\n- Basil\n")
    assert len(records) == 2
    assert ambiguities == []


def test_all_bullet_markers_are_recognised():
    text = "Olives\n- One\n* Two\n• Three\n– Four\n— Five\n"
    records, ambiguities = parse(text)
    assert [r.product for r in records] == ["One", "Two", "Three", "Four", "Five"]
    assert ambiguities == []


def test_empty_input_yields_nothing():
    assert parse("") == ([], [])
    assert parse("\n\n   \n") == ([], [])


def test_nothing_is_invented(raw_products):
    """Every output name appears verbatim in the source text."""
    records, _ = parse(raw_products)
    for record in records:
        assert record.product in raw_products
        assert record.category in raw_products


def test_validate_rows_rejects_empty_cells():
    problems = validate_rows([("Hummus", "Beetroot Hummus"), ("", "Orphan"), ("Pesto", "  ")])
    assert len(problems) == 2
    assert "row 2" in problems[0]
    assert "row 3" in problems[1]


def test_ambiguity_carries_a_line_number():
    _, ambiguities = parse("- Orphan\n")
    assert isinstance(ambiguities[0], Ambiguity)
    assert ambiguities[0].line == 1
