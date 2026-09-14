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

Implemented from a Claude Design handoff (`design_handoff_shop_redesign/` —
a `.dc.html` design reference, an asset pack, and a written spec covering
tokens, copy, animation and accessibility down to the pixel). The result: a
green→black→maroon hero gradient, a photographic page background tinted
cream, real pack-shot photography on every catalogue card, and three
click-to-flip product cards floating in the hero.

**Colour** — `--forest` (`#12251b`) grounds the header, market section and
footer; `--cream` (`#f9f0e4`) is the page ground; `--orange` (`#e0522c`) is
the primary action colour; `--lime` (`#b8d44f`) is the secondary accent.
Category accents (hummus pink, pesto green, olives teal, sweet pepper drops
mustard) mark each card's top bar and category tag. Full palette — including
the alpha values used for body copy, borders and text-on-dark — is at the
top of `css/style.css`. **`--lime` on the light `--cream` ground fails
contrast for text** (documented in the handoff); use `--lime-dark` there
instead — it's only safe as a fill (badges, buttons) or as text on the dark
`--forest` ground.

**Type** — Young Serif (headings, always weight 400 — never bold it) and
Hanken Grotesk (body/UI). Both are **self-hosted**: the actual `.woff2`
files live in `assets/fonts/`, referenced by `@font-face` at the top of
`css/style.css`. No Google Fonts `<link>`, no third-party font request at
all — this was a deliberate choice to match the backend's
`Content-Security-Policy` (`script-src`/`style-src` locked to `'self'`)
without having to reopen it for `fonts.googleapis.com` and
`fonts.gstatic.com`.

**Motion** — pointer-tilt on the hero stage, product cards and the market
photo; three independently-flippable hero cards (real `<button>`s with
`aria-pressed`, not clickable `<div>`s); a looping ticker strip. Every
animation and transition is disabled under `prefers-reduced-motion: reduce`
(`css/style.css`, bottom) — not softened, switched off.

**Photography** — the pack shots in `assets/products/` and the category/
hero photos in `assets/` are **first-party images supplied by the business
owner** (screenshots of their own packaging, cropped and upscaled for the
page — see `design_handoff_shop_redesign/README.md` for the exact
provenance). They are mapped to products by slug in `js/app.js`
(`PRODUCT_IMAGES`), not served by the API — the backend's product model has
no image field, and adding one was explicitly out of scope for this
redesign (presentation-only; no `/api/*` contract changes). A product not in
that map falls back to its category photo (`CATEGORY_FALLBACK_IMAGES`)
rather than an empty image well.
