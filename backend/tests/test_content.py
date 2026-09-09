"""Market schedule, enquiries and double opt-in email capture."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import MarketEvent
from tests.conftest import ADMIN_HEADERS


class TestMarketSchedule:
    def test_upcoming_events_are_listed(self, client, db_session):
        db_session.add(
            MarketEvent(
                title="St George's Market",
                location="Belfast",
                starts_on=date.today() + timedelta(days=3),
            )
        )
        db_session.commit()
        body = client.get("/api/events").json()
        assert [event["title"] for event in body] == ["St George's Market"]

    def test_past_events_are_hidden_by_default(self, client, db_session):
        db_session.add(
            MarketEvent(
                title="Old Market", location="Comber", starts_on=date.today() - timedelta(days=30)
            )
        )
        db_session.commit()
        assert client.get("/api/events").json() == []
        assert len(client.get("/api/events", params={"upcoming_only": False}).json()) == 1

    def test_unpublished_events_are_hidden(self, client, db_session):
        db_session.add(
            MarketEvent(
                title="Draft Market",
                location="Belfast",
                starts_on=date.today() + timedelta(days=3),
                published=False,
            )
        )
        db_session.commit()
        assert client.get("/api/events").json() == []

    def test_staff_can_add_edit_and_remove_events(self, client):
        created = client.post(
            "/api/admin/events",
            headers=ADMIN_HEADERS,
            json={
                "title": "St George's Market",
                "location": "Belfast",
                "starts_on": str(date.today() + timedelta(days=2)),
                "opening_time": "8am - 2pm",
            },
        ).json()
        assert created["opening_time"] == "8am - 2pm"

        updated = client.patch(
            f"/api/admin/events/{created['id']}",
            headers=ADMIN_HEADERS,
            json={
                "title": "St George's Market",
                "location": "Belfast",
                "starts_on": str(date.today() + timedelta(days=2)),
                "opening_time": "9am - 3pm",
            },
        ).json()
        assert updated["opening_time"] == "9am - 3pm"

        assert (
            client.delete(f"/api/admin/events/{created['id']}", headers=ADMIN_HEADERS).status_code
            == 204
        )
        assert client.get("/api/events").json() == []

    def test_events_need_a_key_to_edit(self, client):
        response = client.post(
            "/api/admin/events",
            json={"title": "X", "location": "Y", "starts_on": str(date.today())},
        )
        assert response.status_code == 401


class TestEnquiries:
    def test_a_trade_enquiry_is_captured(self, client):
        response = client.post(
            "/api/enquiries",
            json={
                "kind": "trade",
                "name": "Buyer",
                "email": "buyer@wholesaler.example",
                "company": "Wholesaler Ltd",
                "message": "Please send your trade list.",
            },
        )
        assert response.status_code == 201
        assert response.json()["kind"] == "trade"

    def test_enquiries_appear_in_the_admin_queue(self, client):
        client.post(
            "/api/enquiries",
            json={"name": "A", "email": "a@example.com", "message": "Hello"},
        )
        body = client.get("/api/admin/enquiries", headers=ADMIN_HEADERS).json()
        assert len(body) == 1
        assert body[0]["handled"] is False

    def test_an_invalid_email_is_rejected(self, client):
        response = client.post(
            "/api/enquiries", json={"name": "A", "email": "not-an-email", "message": "Hi"}
        )
        assert response.status_code == 422

    def test_an_empty_message_is_rejected(self, client):
        response = client.post(
            "/api/enquiries", json={"name": "A", "email": "a@example.com", "message": ""}
        )
        assert response.status_code == 422


class TestNewsletter:
    def test_signup_starts_unconfirmed(self, client):
        response = client.post("/api/newsletter/subscribe", json={"email": "a@example.com"})
        assert response.status_code == 202
        assert response.json()["status"] == "confirmation_required"

    def test_confirming_the_token_completes_the_signup(self, client):
        token = client.post(
            "/api/newsletter/subscribe", json={"email": "a@example.com"}
        ).json()["confirm_token"]
        body = client.get("/api/newsletter/confirm", params={"token": token}).json()
        assert body["status"] == "confirmed"

    def test_signing_up_twice_reuses_the_pending_token(self, client):
        first = client.post("/api/newsletter/subscribe", json={"email": "a@example.com"}).json()
        second = client.post("/api/newsletter/subscribe", json={"email": "a@example.com"}).json()
        assert first["confirm_token"] == second["confirm_token"]

    def test_a_confirmed_address_is_not_re_prompted(self, client):
        token = client.post(
            "/api/newsletter/subscribe", json={"email": "a@example.com"}
        ).json()["confirm_token"]
        client.get("/api/newsletter/confirm", params={"token": token})
        again = client.post("/api/newsletter/subscribe", json={"email": "a@example.com"}).json()
        assert again["status"] == "already_subscribed"
        assert "confirm_token" not in again

    def test_email_is_normalised_to_lowercase(self, client):
        body = client.post("/api/newsletter/subscribe", json={"email": "A@Example.COM"}).json()
        assert body["email"] == "a@example.com"

    def test_an_unknown_token_is_rejected(self, client):
        assert client.get("/api/newsletter/confirm", params={"token": "nope"}).status_code == 404
