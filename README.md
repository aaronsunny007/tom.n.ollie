# Tom & Ollie

Storefront relaunch for [Tom & Ollie](https://www.tomandollie.com) — Belfast
artisan cheesemongers, mezze producers and hamper specialists.

- **[`backend/`](backend/README.md)** — FastAPI service: catalogue,
  chilled-aware checkout, orders, market schedule, trade enquiries, and an admin
  surface that imports the business's own product notes.
- **[`frontend/`](frontend/README.md)** — the storefront itself: a responsive,
  no-build HTML/CSS/JS site that renders the live catalogue, a working basket
  and checkout, and the market schedule, all pulled from the backend API.
- **[`docs/BACKEND_PLAN.md`](docs/BACKEND_PLAN.md)** — what it does, what it
  deliberately does not, and what must happen before it can take a real order.

```bash
cd backend
pip install -r requirements-dev.txt
cp .env.example .env          # set TANDO_ADMIN_API_KEY
python -m app.seed            # 20 draft products across 4 categories
uvicorn app.main:app --reload # site at localhost:8000, API docs at /docs
pytest -q                     # 153 tests
```

The front end is served from the same process — the command above is
everything you need. It's plain HTML/CSS/JS with no Node/build step, so it
also opens fine as a static site (see `frontend/README.md`) against any host
serving the API.

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
