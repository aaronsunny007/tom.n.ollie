"""Test fixtures: a fresh in-memory database per test, and an API client."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Settings are cached at first use, so the environment has to be set before the
# application modules are imported.
os.environ.setdefault("TANDO_DATABASE_URL", "sqlite://")
os.environ.setdefault("TANDO_ADMIN_API_KEY", "test-admin-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    AllergenPresence,
    AllergenStatus,
    Base,
    Category,
    Product,
    ProductAllergen,
    ProductStatus,
    Temperature,
    Variant,
)

ADMIN_HEADERS = {"X-Admin-Key": "test-admin-key"}
RAW_PRODUCTS_PATH = BACKEND_ROOT / "data" / "raw_products.txt"


@pytest.fixture
def raw_products() -> str:
    """The real Tom & Ollie notes, byte for byte."""
    return RAW_PRODUCTS_PATH.read_text(encoding="utf-8")


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_product(
    session,
    *,
    name: str = "Traditional Hummus",
    category_name: str = "Hummus",
    slug: str = "hummus-traditional-hummus",
    status: ProductStatus = ProductStatus.active,
    temperature: Temperature = Temperature.chilled,
    allergen_status: AllergenStatus = AllergenStatus.confirmed,
    allergens: tuple[str, ...] = ("sesame",),
    price_pence: int | None = 450,
    weight_grams: int | None = 200,
    stock: int = 10,
    sku: str = "HUM-TRADITIO-200G",
    is_vegan: bool | None = True,
) -> Product:
    """A fully specified product. Tests that care about gaps remove fields."""
    category = session.query(Category).filter_by(name=category_name).one_or_none()
    if category is None:
        category = Category(slug=category_name.lower().replace(" ", "-"), name=category_name)
        session.add(category)
        session.flush()

    product = Product(
        slug=slug,
        name=name,
        category_id=category.id,
        status=status,
        temperature=temperature,
        allergen_status=allergen_status,
        is_vegan=is_vegan,
        is_vegetarian=True,
    )
    for allergen in allergens:
        product.allergens.append(
            ProductAllergen(allergen=allergen, presence=AllergenPresence.contains)
        )
    product.variants.append(
        Variant(
            sku=sku,
            label="200g",
            price_pence=price_pence,
            weight_grams=weight_grams,
            stock=stock,
        )
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
