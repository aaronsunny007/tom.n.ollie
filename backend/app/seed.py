"""Seed the database from the real Tom & Ollie product notes.

What gets seeded is exactly what the business supplied: category and product
names, transcribed. No prices, weights, allergens or descriptions are invented
here — every product lands as a draft and `GET /api/admin/readiness` lists what
each one still needs before it can go on sale.

    python -m app.seed                 # create tables and seed
    python -m app.seed --reset         # drop and recreate first
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal, create_all, engine
from .models import (
    AllergenStatus,
    Base,
    Category,
    LegacyPath,
    Product,
    ProductStatus,
)
from .parser import parse
from .utils import slugify, unique_slug

RAW_PRODUCTS = Path(__file__).resolve().parent.parent / "data" / "raw_products.txt"

# Paths recovered from search indexing in the requirements document (SS07).
# Every one of these still has ranking equity and must never return a 404.
LEGACY_PATHS: list[tuple[str, str, str | None]] = [
    ("/pages/about-us", "/about", None),
    ("/pages/contact-us", "/contact", None),
    ("/pages/events", "/markets", "Market schedule"),
    ("/pages/terms", "/terms", None),
    ("/pages/retail", "/trade", "Wholesale / trade audience"),
    ("/pages/delivery", "/delivery", None),
    (
        "/collections/spanish-cheese",
        "/shop",
        "REVIEW: needs a real target once the cheese range going online is decided",
    ),
    (
        "/collections/italian-cheese",
        "/shop",
        "REVIEW: needs a real target once the cheese range going online is decided",
    ),
    (
        "/collections/meat-seafood",
        "/shop",
        "REVIEW: needs a real target once charcuterie and seafood are ranged",
    ),
    (
        "/collections/accompaniments",
        "/shop",
        "REVIEW: closest live equivalent is the olives and mezze range",
    ),
]


def seed_products(raw_text: str) -> tuple[int, int, list[str]]:
    """Create categories and draft products. Returns (categories, products, ambiguities)."""
    records, ambiguities = parse(raw_text)
    if ambiguities:
        return 0, 0, [a.message for a in ambiguities]

    created_categories = 0
    created_products = 0

    with SessionLocal() as db:
        existing_categories = {c.slug: c for c in db.scalars(select(Category))}
        taken_slugs = set(db.scalars(select(Product.slug)))

        for position, record in enumerate(records):
            category_slug = slugify(record.category)
            category = existing_categories.get(category_slug)
            if category is None:
                category = Category(
                    slug=category_slug,
                    name=record.category,
                    position=len(existing_categories),
                )
                db.add(category)
                db.flush()
                existing_categories[category_slug] = category
                created_categories += 1

            candidate = slugify(f"{record.category} {record.product}")
            if candidate in taken_slugs:
                continue
            slug = unique_slug(candidate, taken_slugs)
            taken_slugs.add(slug)
            db.add(
                Product(
                    slug=slug,
                    name=record.product,
                    category_id=category.id,
                    position=position,
                    status=ProductStatus.draft,
                    allergen_status=AllergenStatus.unconfirmed,
                    source_line=record.line,
                )
            )
            created_products += 1

        db.commit()
    return created_categories, created_products, []


def seed_legacy_paths() -> int:
    created = 0
    with SessionLocal() as db:
        existing = set(db.scalars(select(LegacyPath.path)))
        for path, target, note in LEGACY_PATHS:
            if path in existing:
                continue
            db.add(LegacyPath(path=path, redirect_to=target, note=note))
            created += 1
        db.commit()
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    parser.add_argument("--input", default=str(RAW_PRODUCTS), help="raw product notes")
    args = parser.parse_args()

    if args.reset:
        Base.metadata.drop_all(engine)
    create_all()

    raw_text = Path(args.input).read_text(encoding="utf-8")
    categories, products, ambiguities = seed_products(raw_text)
    if ambiguities:
        print("Refusing to seed: the source notes are ambiguous and nothing was guessed.")
        for message in ambiguities:
            print(f"  - {message}")
        return 2

    redirects = seed_legacy_paths()
    print(f"Seeded {products} draft product(s) across {categories} new categor(ies).")
    print(f"Seeded {redirects} legacy redirect(s).")
    print(
        "\nEvery product is a DRAFT. Prices, weights and allergen data must be supplied by "
        "the business before anything can be published:\n"
        "  GET /api/admin/readiness"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
