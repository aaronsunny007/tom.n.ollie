# Tom & Ollie

Backend for the [Tom & Ollie](https://www.tomandollie.com) storefront relaunch —
Belfast artisan cheesemongers, mezze producers and hamper specialists.

- **[`backend/`](backend/README.md)** — FastAPI service: catalogue,
  chilled-aware checkout, orders, market schedule, trade enquiries, and an admin
  surface that imports the business's own product notes.
- **[`docs/BACKEND_PLAN.md`](docs/BACKEND_PLAN.md)** — what it does, what it
  deliberately does not, and what must happen before it can take a real order.

```bash
cd backend
pip install -r requirements-dev.txt
cp .env.example .env          # set TANDO_ADMIN_API_KEY
python -m app.seed            # 20 draft products across 4 categories
uvicorn app.main:app --reload # docs at localhost:8000/docs
pytest -q                     # 153 tests
```

## Two rules the code enforces

**Allergen data gates publishing.** A product cannot be sold until a human has
confirmed its allergens, and that statement follows the order onto the dispatch
note in the parcel — the two points at which the FSA requires it for distance
selling. Nothing in this repository generates allergen or dietary data.

**Chilled goods drive the whole order.** Any chilled line puts the whole parcel
on a chilled service, dispatched only on a dispatch day, and only to a delivery
date the warehouse can actually hit.

## Before it takes a real order

Everything ships as a draft, on purpose. The shipping rate card is a planning
placeholder that reports `"quoted": false` until real carrier quotes replace it,
and all 20 products need prices, weights and confirmed allergens from the
business. `GET /api/admin/readiness` lists exactly what is missing.
