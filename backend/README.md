# Tom & Ollie — storefront backend

A FastAPI service for the Tom & Ollie relaunch: catalogue, chilled-aware
checkout, orders, market schedule, trade enquiries, and an admin surface that
imports the business's own product notes.

Two rules are enforced in code rather than left to process, because both are
places where a food business gets hurt:

1. **Allergen data gates publishing.** A product cannot be sold until a human
   has confirmed its allergens, and that statement follows the order onto the
   dispatch note that goes in the parcel — the two points at which the FSA
   requires it for distance selling.
2. **Chilled goods drive the whole order.** Any chilled line puts the whole
   parcel on a chilled service, dispatched only on a dispatch day, and only to
   a delivery date the warehouse can actually hit.

## Run it

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env          # set TANDO_ADMIN_API_KEY
python -m app.seed            # create tables, load the real product list
uvicorn app.main:app --reload
```

Interactive docs at <http://localhost:8000/docs>.

```bash
pytest                        # 153 tests
```

## What seeding gives you

`data/raw_products.txt` holds the product notes exactly as the business wrote
them — trailing spaces, double space, `Garlicy` spelling and all. Seeding
transcribes them into 20 draft products across 4 categories:

| Category | Products |
|---|---|
| Hummus | Traditional, Beetroot, Chilli Basil Garlic, Vegan Chilli Basil Garlic, Caramelised Onion, Red Pepper |
| Pesto | Smoked Tomato Pesto, Vegan Basil, Basil, Lyness Basil |
| Olives | Pitted Green, Pitted Kalamata, Italian Mixed, House Mix, Global Mix, Chilli Basil Garlic Green, Garlicy Green |
| Sweet Pepper Drops | Red, Mixed, Yellow |

Every one lands as a **draft** with no price, weight, allergens or description.
That is deliberate: those are the business's to supply, and allergen data in
particular is legally regulated information that must never be generated or
guessed. Ask the API what is still missing:

```bash
curl -H "X-Admin-Key: $KEY" localhost:8000/api/admin/readiness
```

## Endpoints

### Public

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Service state, including whether shipping rates are real quotes |
| GET | `/api/categories` · `/api/categories/{slug}` | Browsable collections |
| GET | `/api/products` | Filter by category, vegan, vegetarian, temperature, stock; free-text `q`; paginated |
| GET | `/api/products/{slug}` | Provenance, allergens and variants |
| GET | `/api/legacy-path?path=` | Where an old Shopify URL should 301 to |
| GET | `/api/shipping/zones` · `/api/shipping/zone` | Zone rules and lookup |
| POST | `/api/cart/quote` | Price a basket; list every service that can legitimately carry it |
| POST | `/api/orders` | Place an order (re-priced server-side) |
| GET | `/api/orders/{number}?email=` | Order lookup |
| GET | `/api/orders/{number}/dispatch-note` | Parcel paperwork: gift message + allergens, no prices |
| GET | `/api/events` | Market schedule |
| POST | `/api/enquiries` | Trade, corporate and general enquiries |
| POST | `/api/newsletter/subscribe` · GET `/api/newsletter/confirm` | Double opt-in capture |

### Admin — `X-Admin-Key` required

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/admin/import/preview` | Parse raw notes, report ambiguities, write nothing |
| POST | `/api/admin/import/commit` | Create draft products from notes |
| GET | `/api/admin/export.xlsx` | `Category \| Product` workbook, verified cell by cell |
| GET | `/api/admin/readiness` | What each product still needs before it can go live |
| GET | `/api/admin/allergens` | The 14 regulated allergens |
| PATCH | `/api/admin/products/{slug}` | Prices, weights, allergens, provenance, dietary flags |
| POST | `/api/admin/products/{slug}/publish` · `/unpublish` | Publishing, gated on readiness |
| POST/PATCH/DELETE | `/api/admin/events[/{id}]` | Market schedule, staff-editable |
| GET | `/api/admin/orders` · `/api/admin/enquiries` | Queues |

## Shipping zones

`NI` (BT postcodes) · `ROI` · `GB` mainland · `GB_OFFSHORE` (Highlands, Islands,
Isle of Man, Channel Islands) · `COLLECTION`.

The rate card in `data/shipping_rates.json` is **a placeholder**, carried over
from the planning estimates in the requirements document. It reports
`"quoted": false`, and `/api/cart/quote` tells the caller so. Replace every band
with a written carrier quote before taking real orders.

## Deliberate non-goals

No payment capture (Shopify or Stripe handles PCI; no card data touches this
service), no email sending (the marketing platform owns that — signup returns a
token to hand over), and no AI extraction path. The deterministic parser handles
the real notes with zero ambiguities, so there is nothing for a model to add and
a whole failure mode — invention — to avoid.
