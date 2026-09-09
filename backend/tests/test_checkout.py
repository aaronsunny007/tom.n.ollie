"""Quoting, ordering, and the rules that protect a chilled food order."""

from __future__ import annotations

from app.models import AllergenStatus, ProductStatus, Temperature
from tests.conftest import make_product


def address(country="GB", postcode="BT17 0QL"):
    return {
        "name": "Aoife Quinn",
        "line1": "1 Market Street",
        "city": "Belfast",
        "postcode": postcode,
        "country": country,
    }


def quote(client, sku="HUM-TRADITIO-200G", quantity=1, country="GB", postcode="BT17 0QL"):
    return client.post(
        "/api/cart/quote",
        json={
            "lines": [{"sku": sku, "quantity": quantity}],
            "country": country,
            "postcode": postcode,
        },
    )


class TestQuoting:
    def test_a_basket_is_priced_with_shipping_options(self, client, db_session):
        make_product(db_session)
        body = quote(client, quantity=2).json()
        assert body["subtotal_pence"] == 900
        assert body["zone"] == "NI"
        assert body["shipping_options"]

    def test_the_allergen_statement_travels_with_the_line(self, client, db_session):
        make_product(db_session, allergens=("sesame",))
        line = quote(client).json()["lines"][0]
        assert line["allergen_summary"] == "Contains: sesame"

    def test_a_product_with_no_allergens_says_so_explicitly(self, client, db_session):
        make_product(db_session, allergens=())
        line = quote(client).json()["lines"][0]
        assert "none of the 14 regulated allergens" in line["allergen_summary"]

    def test_a_chilled_line_makes_the_whole_basket_chilled(self, client, db_session):
        make_product(db_session, temperature=Temperature.chilled)
        make_product(
            db_session,
            name="House Mix",
            category_name="Olives",
            slug="olives-house-mix",
            sku="OLI-HOUSEMIX-200G",
            temperature=Temperature.ambient,
        )
        body = client.post(
            "/api/cart/quote",
            json={
                "lines": [
                    {"sku": "HUM-TRADITIO-200G", "quantity": 1},
                    {"sku": "OLI-HOUSEMIX-200G", "quantity": 1},
                ],
                "country": "GB",
                "postcode": "SW1A 1AA",
            },
        ).json()
        assert body["requires_chilled"] is True
        assert "standard" not in {option["service"] for option in body["shipping_options"]}

    def test_packaging_weight_is_counted(self, client, db_session):
        """Insulated liners and gel packs are real weight and push parcels up a band."""
        make_product(db_session, weight_grams=200, temperature=Temperature.chilled)
        body = quote(client).json()
        assert body["total_weight_grams"] == 800

    def test_provisional_rates_are_declared_to_the_caller(self, client, db_session):
        make_product(db_session)
        body = quote(client).json()
        assert body["rates_are_quoted"] is False
        assert any("provisional planning rates" in notice for notice in body["notices"])

    def test_an_unknown_sku_is_rejected(self, client, db_session):
        make_product(db_session)
        response = quote(client, sku="NOPE-1")
        assert response.status_code == 400
        assert "Unknown SKU" in response.json()["detail"]

    def test_a_draft_product_cannot_be_quoted(self, client, db_session):
        make_product(db_session, status=ProductStatus.draft)
        response = quote(client)
        assert response.status_code == 400
        assert "not currently on sale" in response.json()["detail"]

    def test_a_product_without_confirmed_allergens_cannot_be_sold(self, client, db_session):
        """Even if it were somehow published, the sale is refused."""
        product = make_product(db_session)
        product.allergen_status = AllergenStatus.unconfirmed
        db_session.commit()
        response = quote(client)
        assert response.status_code == 400
        assert "no confirmed allergen data" in response.json()["detail"]

    def test_insufficient_stock_is_rejected(self, client, db_session):
        make_product(db_session, stock=2)
        response = quote(client, quantity=3)
        assert response.status_code == 400
        assert "left in stock" in response.json()["detail"]

    def test_repeated_skus_are_merged_before_the_stock_check(self, client, db_session):
        make_product(db_session, stock=2)
        response = client.post(
            "/api/cart/quote",
            json={
                "lines": [
                    {"sku": "HUM-TRADITIO-200G", "quantity": 2},
                    {"sku": "HUM-TRADITIO-200G", "quantity": 2},
                ],
                "country": "GB",
                "postcode": "BT17 0QL",
            },
        )
        assert response.status_code == 400
        assert "left in stock" in response.json()["detail"]

    def test_an_unshippable_country_is_rejected(self, client, db_session):
        make_product(db_session)
        response = quote(client, country="FR", postcode="75001")
        assert response.status_code == 400


class TestOrdering:
    def _order_payload(self, client, db_session, **overrides):
        body = quote(client).json()
        option = body["shipping_options"][0]
        payload = {
            "lines": [{"sku": "HUM-TRADITIO-200G", "quantity": 1}],
            "email": "aoife@example.com",
            "customer_name": "Aoife Quinn",
            "delivery": address(),
            "shipping_service": option["service"],
            "delivery_date": option["delivery_dates"][0],
        }
        payload.update(overrides)
        return payload

    def test_an_order_is_placed_and_totalled(self, client, db_session):
        make_product(db_session)
        payload = self._order_payload(client, db_session)
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["subtotal_pence"] == 450
        assert body["total_pence"] == body["subtotal_pence"] + body["shipping_pence"]
        assert body["number"].startswith("TO-")

    def test_stock_is_decremented(self, client, db_session):
        product = make_product(db_session, stock=5)
        client.post("/api/orders", json=self._order_payload(client, db_session))
        db_session.refresh(product)
        assert product.variants[0].stock == 4

    def test_a_delivery_date_we_cannot_hit_is_refused(self, client, db_session):
        make_product(db_session)
        payload = self._order_payload(client, db_session, delivery_date="2026-12-25")
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 400
        assert "not a delivery date we can hit" in response.json()["detail"]

    def test_a_service_that_cannot_carry_the_basket_is_refused(self, client, db_session):
        make_product(db_session, temperature=Temperature.chilled)
        payload = self._order_payload(client, db_session, shipping_service="standard")
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 400
        assert "not available for this basket" in response.json()["detail"]

    def test_prices_are_recalculated_server_side(self, client, db_session):
        """The client sends SKUs and quantities only. It cannot send a price."""
        make_product(db_session, price_pence=450)
        payload = self._order_payload(client, db_session)
        payload["subtotal_pence"] = 1
        body = client.post("/api/orders", json=payload).json()
        assert body["subtotal_pence"] == 450

    def test_order_lines_snapshot_the_name_and_allergens(self, client, db_session):
        product = make_product(db_session, allergens=("sesame",))
        body = client.post("/api/orders", json=self._order_payload(client, db_session)).json()
        product.name = "Renamed After The Sale"
        db_session.commit()

        looked_up = client.get(
            f"/api/orders/{body['number']}", params={"email": "aoife@example.com"}
        ).json()
        assert looked_up["lines"][0]["product_name"] == "Traditional Hummus"
        assert looked_up["lines"][0]["allergen_summary"] == "Contains: sesame"

    def test_an_order_needs_the_matching_email_to_look_up(self, client, db_session):
        make_product(db_session)
        body = client.post("/api/orders", json=self._order_payload(client, db_session)).json()
        wrong = client.get(f"/api/orders/{body['number']}", params={"email": "someone@else.com"})
        assert wrong.status_code == 404

    def test_email_lookup_is_case_insensitive(self, client, db_session):
        make_product(db_session)
        body = client.post("/api/orders", json=self._order_payload(client, db_session)).json()
        response = client.get(
            f"/api/orders/{body['number']}", params={"email": "AOIFE@EXAMPLE.COM"}
        )
        assert response.status_code == 200


class TestGifting:
    def _gift_order(self, client, db_session):
        quoted = quote(client).json()
        option = quoted["shipping_options"][0]
        return client.post(
            "/api/orders",
            json={
                "lines": [{"sku": "HUM-TRADITIO-200G", "quantity": 1}],
                "email": "buyer@example.com",
                "customer_name": "Buyer",
                "delivery": {
                    "name": "Recipient",
                    "line1": "2 Other Street",
                    "city": "Belfast",
                    "postcode": "BT1 1AA",
                    "country": "GB",
                },
                "shipping_service": option["service"],
                "delivery_date": option["delivery_dates"][0],
                "is_gift": True,
                "gift_message": "  Happy Christmas  ",
            },
        ).json()

    def test_gift_message_is_trimmed_and_stored(self, client, db_session):
        make_product(db_session)
        body = self._gift_order(client, db_session)
        assert body["gift_message"] == "Happy Christmas"
        assert body["is_gift"] is True

    def test_dispatch_note_carries_the_message_and_allergens(self, client, db_session):
        make_product(db_session, allergens=("sesame",))
        order = self._gift_order(client, db_session)
        note = client.get(
            f"/api/orders/{order['number']}/dispatch-note",
            params={"email": "buyer@example.com"},
        ).json()
        assert note["gift_message"] == "Happy Christmas"
        assert note["items"][0]["allergens"] == "Contains: sesame"
        assert "Allergen information for every item" in note["allergen_statement"]

    def test_dispatch_note_shows_no_prices(self, client, db_session):
        """FR-11: the recipient must never see what the buyer paid."""
        make_product(db_session)
        order = self._gift_order(client, db_session)
        note = client.get(
            f"/api/orders/{order['number']}/dispatch-note",
            params={"email": "buyer@example.com"},
        ).json()
        serialised = str(note)
        assert "price" not in serialised
        assert "pence" not in serialised
        assert note["delivery_name"] == "Recipient"

    def test_delivery_address_is_independent_of_the_buyer(self, client, db_session):
        make_product(db_session)
        order = self._gift_order(client, db_session)
        assert order["customer_name"] == "Buyer"
        note = client.get(
            f"/api/orders/{order['number']}/dispatch-note",
            params={"email": "buyer@example.com"},
        ).json()
        assert note["delivery_name"] == "Recipient"
        assert "2 Other Street" in note["delivery_address"]
