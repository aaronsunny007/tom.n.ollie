"""Seeding the real catalogue, end to end."""

from __future__ import annotations

from pathlib import Path

from app import seed
from app.models import Category, LegacyPath, Product, ProductStatus


def _seed_into(monkeypatch, db_session, raw_products):
    """Point the seeder's session factory at the test database."""

    class _SessionProxy:
        def __enter__(self):
            return db_session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(seed, "SessionLocal", lambda: _SessionProxy())
    return seed.seed_products(raw_products)


def test_seeding_creates_the_real_catalogue(monkeypatch, db_session, raw_products):
    categories, products, ambiguities = _seed_into(monkeypatch, db_session, raw_products)
    assert ambiguities == []
    assert (categories, products) == (4, 20)

    names = {p.name for p in db_session.query(Product)}
    assert "Vegan Chilli Basil Garlic Hummus" in names
    assert "Garlicy Green Olives" in names
    assert {c.name for c in db_session.query(Category)} == {
        "Hummus",
        "Pesto",
        "Olives",
        "Sweet Pepper Drops",
    }


def test_everything_is_seeded_as_a_draft(monkeypatch, db_session, raw_products):
    _seed_into(monkeypatch, db_session, raw_products)
    products = db_session.query(Product).all()
    assert all(product.status is ProductStatus.draft for product in products)
    assert all(product.allergen_status.value == "unconfirmed" for product in products)
    assert all(product.variants == [] for product in products)


def test_seeding_is_idempotent(monkeypatch, db_session, raw_products):
    _seed_into(monkeypatch, db_session, raw_products)
    categories, products, _ = _seed_into(monkeypatch, db_session, raw_products)
    assert (categories, products) == (0, 0)
    assert db_session.query(Product).count() == 20


def test_ambiguous_notes_seed_nothing(monkeypatch, db_session):
    categories, products, ambiguities = _seed_into(monkeypatch, db_session, "- Orphan Olives\n")
    assert (categories, products) == (0, 0)
    assert ambiguities
    assert db_session.query(Product).count() == 0


def test_legacy_redirects_are_seeded(monkeypatch, db_session):
    class _SessionProxy:
        def __enter__(self):
            return db_session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(seed, "SessionLocal", lambda: _SessionProxy())
    created = seed.seed_legacy_paths()
    assert created == len(seed.LEGACY_PATHS)

    paths = {row.path: row.redirect_to for row in db_session.query(LegacyPath)}
    assert paths["/pages/retail"] == "/trade"
    assert paths["/pages/events"] == "/markets"
    assert "/collections/italian-cheese" in paths


def test_redirects_needing_a_decision_are_flagged(monkeypatch, db_session):
    """Cheese collections have no live equivalent yet; that is marked, not hidden."""
    flagged = [path for path, _, note in seed.LEGACY_PATHS if note and note.startswith("REVIEW")]
    assert "/collections/spanish-cheese" in flagged


def test_the_shipped_notes_file_is_the_real_list():
    raw = (Path(seed.RAW_PRODUCTS)).read_text(encoding="utf-8")
    assert "Garlicy Green Olives" in raw
    assert "Lyness Basil" in raw
    assert raw.count("\n-") + raw.count("\n -") == 20
