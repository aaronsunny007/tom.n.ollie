"""Public catalogue endpoints."""

from __future__ import annotations

from app.models import LegacyPath, ProductStatus, Temperature
from tests.conftest import make_product


def test_health_reports_rate_card_state(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["shipping_rates_quoted"] is False


def test_categories_are_listed(client, db_session):
    make_product(db_session)
    body = client.get("/api/categories").json()
    assert [category["name"] for category in body] == ["Hummus"]


def test_unknown_category_is_a_404(client):
    assert client.get("/api/categories/nope").status_code == 404


def test_only_active_products_are_listed(client, db_session):
    make_product(db_session)
    make_product(
        db_session,
        name="Beetroot Hummus",
        slug="hummus-beetroot-hummus",
        sku="HUM-BEETROOT-200G",
        status=ProductStatus.draft,
    )
    body = client.get("/api/products").json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Traditional Hummus"


def test_drafts_can_be_listed_explicitly(client, db_session):
    make_product(db_session, status=ProductStatus.draft)
    assert client.get("/api/products").json()["total"] == 0
    assert client.get("/api/products", params={"include_drafts": True}).json()["total"] == 1


def test_product_summary_carries_from_price_and_stock(client, db_session):
    make_product(db_session, price_pence=450, stock=3)
    item = client.get("/api/products").json()["items"][0]
    assert item["from_price_pence"] == 450
    assert item["in_stock"] is True


def test_out_of_stock_is_reported(client, db_session):
    make_product(db_session, stock=0)
    assert client.get("/api/products").json()["items"][0]["in_stock"] is False


def test_filter_by_category(client, db_session):
    make_product(db_session)
    make_product(
        db_session,
        name="Basil",
        category_name="Pesto",
        slug="pesto-basil",
        sku="PES-BASIL-200G",
    )
    body = client.get("/api/products", params={"category": "pesto"}).json()
    assert [item["name"] for item in body["items"]] == ["Basil"]


def test_filter_by_vegan(client, db_session):
    make_product(db_session, is_vegan=True)
    make_product(
        db_session,
        name="Basil",
        category_name="Pesto",
        slug="pesto-basil",
        sku="PES-BASIL-200G",
        is_vegan=False,
    )
    body = client.get("/api/products", params={"vegan": True}).json()
    assert [item["name"] for item in body["items"]] == ["Traditional Hummus"]


def test_filter_by_temperature(client, db_session):
    make_product(db_session, temperature=Temperature.chilled)
    make_product(
        db_session,
        name="House Mix",
        category_name="Olives",
        slug="olives-house-mix",
        sku="OLI-HOUSEMIX-200G",
        temperature=Temperature.ambient,
    )
    body = client.get("/api/products", params={"temperature": "ambient"}).json()
    assert [item["name"] for item in body["items"]] == ["House Mix"]


def test_search_matches_name_and_category(client, db_session):
    make_product(db_session)
    make_product(
        db_session,
        name="House Mix",
        category_name="Olives",
        slug="olives-house-mix",
        sku="OLI-HOUSEMIX-200G",
    )
    assert client.get("/api/products", params={"q": "hummus"}).json()["total"] == 1
    assert client.get("/api/products", params={"q": "Olives"}).json()["total"] == 1


def test_pagination_reports_the_full_total(client, db_session):
    for index in range(5):
        make_product(
            db_session,
            name=f"Product {index}",
            slug=f"hummus-product-{index}",
            sku=f"HUM-P{index}-200G",
        )
    body = client.get("/api/products", params={"limit": 2, "offset": 2}).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_product_detail_shows_allergens_before_add_to_basket(client, db_session):
    """FR-03: allergen information must be on the product page, not a policy page."""
    make_product(db_session, allergens=("sesame", "milk"))
    body = client.get("/api/products/hummus-traditional-hummus").json()
    assert {entry["allergen"] for entry in body["allergens"]} == {"sesame", "milk"}
    assert body["allergen_status"] == "confirmed"


def test_draft_product_detail_is_hidden_from_the_public(client, db_session):
    make_product(db_session, status=ProductStatus.draft)
    assert client.get("/api/products/hummus-traditional-hummus").status_code == 404


def test_legacy_path_returns_a_redirect_target(client, db_session):
    db_session.add(LegacyPath(path="/pages/retail", redirect_to="/trade", note="Trade"))
    db_session.commit()
    body = client.get("/api/legacy-path", params={"path": "/pages/retail"}).json()
    assert body["redirect_to"] == "/trade"
    assert body["status"] == 301


def test_unmapped_legacy_path_is_reported(client):
    assert client.get("/api/legacy-path", params={"path": "/pages/nope"}).status_code == 404
