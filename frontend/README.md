# Tom & Ollie — front end

A responsive, interactive storefront in plain HTML/CSS/JS — no framework, no
build step, no `node_modules`. It talks only to the backend's public
`/api/*` endpoints (never the admin API, never an admin key) and renders
whatever is actually there: live prices for published products, honest
"coming soon" states for drafts, and no invented descriptions or allergen
text.

## Running it

The backend serves this directory directly, so the normal way to run it is
just running the backend:

```bash
cd ../backend
uvicorn app.main:app --reload
# open http://localhost:8000/
```

`app/main.py` mounts `frontend/` at `/`, after the `/api/*` routes, so API
calls and static assets share one origin and one process — no CORS
configuration needed for local use.

To point the page at a different API host (e.g. serving these static files
from somewhere else), set `window.TANDO_API_BASE` in a `<script>` before
`js/app.js` loads. This is deliberately **not** readable from the URL (no
`?api=` param) — that would let anyone craft a link that quietly redirects
every API call, checkout included, to a server of their choosing while the
address bar still showed the real domain.

## What's on the page

- **Catalogue** (`#shop`) — all 20 products, grouped into the four real
  categories, with live category filters, free-text search, and vegan/
  vegetarian/available-now toggles. Every field — price, stock, status,
  dietary flags — comes from `GET /api/products?include_drafts=true`, so
  publishing a product in the backend changes what the page shows with no
  front-end change required.
- **Product detail** (click any card) — fetches `GET /api/products/{slug}`
  for description, ingredients and the allergen statement. A product with
  unconfirmed allergens says so, rather than showing nothing or guessing.
- **Basket & checkout** — a basket held in `localStorage`, a delivery quote
  via `POST /api/cart/quote` (surfaces the chilled-goods and
  provisional-rates notices verbatim), and order placement via
  `POST /api/orders`.
- **Market dates** (`#market`) — `GET /api/events`.
- **Trade/gifting enquiry** and **newsletter signup** — post straight to
  `/api/enquiries` and `/api/newsletter/subscribe` (double opt-in; nothing is
  added to a mailing list until the confirmation link is used).

## Design

Colours are drawn from the Tom & Ollie market stall, flyer and packaging: a
deep forest green (`--forest`) for the header/hero/footer, the orange/lime
split-circle mark as the primary accent pair, and a warm cream (`--cream`)
body. Category tags use a pastel echoing the packaging range (hummus pink,
pesto green, olives teal, sweet pepper drops mustard) without copying any
specific pack design. All values are CSS custom properties at the top of
`css/style.css` — change them there to re-theme the whole site.

No product photography is used. Nothing here was scraped from search
results or the business's Instagram/Sainsbury's listings — those are useful
references for colour, not assets this repo has rights to serve.
