# Tom & Ollie backend — plan

Companion to the requirements document (*Rebuilding the Tom & Ollie online
store*, draft v0.1). This covers what the backend does, what it deliberately
does not do, and what has to happen before it can take a real order.

## 1. A note on the platform recommendation

The requirements document recommends staying on Shopify and rebuilding the
theme in place (§05). That recommendation is sound, and if it is followed, a
custom backend is not needed for the storefront — Shopify supplies the
catalogue, checkout, payments and PCI compliance.

You asked for a backend, so this is built as a standalone service. It is useful
under either decision:

- **If the store goes custom**, this is the storefront API.
- **If the store stays on Shopify**, this is still the system of record for the
  product data — the import, review, readiness and export pipeline that gets a
  clean, allergen-complete catalogue *into* Shopify, which is the part the
  requirements document identifies as the actual critical path (§08, §18).

Either way, recovering the Shopify admin login stays the first task in the
project. Nothing here changes that.

## 2. What it does

| Area | Requirement | How it is met |
|---|---|---|
| Catalogue | FR-01, FR-02, FR-04 | Categories, products, weight variants, provenance fields |
| Allergens | FR-03, §10 | Structured per-product allergen records; publishing gated on human confirmation; the statement follows the order onto the dispatch note |
| Dietary filtering | FR-05 | Tri-state vegan / vegetarian flags — `NULL` means "nobody has said", not "no" |
| Stock | FR-06 | Per-variant stock, decremented at order time; out-of-stock surfaced, not hidden |
| Search | FR-07 | Free-text across name, producer, description and category |
| Gifting | FR-10, FR-11 | Gift message and a delivery address independent of the buyer; dispatch note carries the message and allergens and no prices |
| Delivery dates | FR-12 | Dates derived from the dispatch calendar, validated server-side at order time |
| Shipping zones | FR-16 | NI / ROI / GB / GB offshore, resolved from country and postcode |
| Chilled rules | FR-17, FR-18 | Any chilled line forces the whole parcel onto a chilled service; standard services are withdrawn, not warned about |
| Free delivery | FR-23 | Configurable threshold, never applied to chilled services |
| Market schedule | FR-24 | Staff-editable events, no developer involvement |
| Trade enquiries | FR-25, FR-14 | Trade, corporate and general enquiries into one queue |
| Email capture | FR-27 | Double opt-in; an unconfirmed address is not a subscriber |
| SEO migration | NFR-05, §07 | Legacy path table; every recovered URL resolves to a 301 target |

## 3. Design decisions worth knowing

**Products are imported, not authored.** The admin import takes the business's
own raw notes and transcribes them. It corrects nothing — not the `Garlicy`
spelling, not the bare `Red` under Sweet Pepper Drops. A wrong product name is a
wrong label, and a wrong label on food is a legal problem rather than a typo.
Anything the rules cannot resolve is reported with its line number for a human,
never guessed.

**Nothing about food safety is inferred.** Allergens, ingredients and dietary
flags are only ever set by a person. `POST /products/{slug}/publish` refuses a
product whose allergens are unconfirmed, and the basket refuses to price one
even if it somehow reached `active`.

**Money is calculated server-side.** The client sends SKUs and quantities. It
cannot send a price, a shipping cost or a total.

**Orders are immutable records.** Product name, price and allergen statement are
copied onto the order line at the point of sale. Later catalogue edits do not
rewrite what was in the parcel.

**Packaging weight counts.** An insulated liner and gel packs add ~600g and push
parcels into the next band. Not counting them is a quiet loss on every chilled
order.

## 4. What is deliberately out

- **Payments.** No card data touches this service (NFR-06). Shopify or Stripe
  owns checkout; orders land as `pending` for a payment webhook to confirm.
- **Email sending.** Signup returns a confirmation token for the marketing
  platform to send. Transactional templates belong there too.
- **An AI extraction path.** The deterministic parser handles the real notes
  with zero ambiguities. A model adds cost, latency and one failure mode the
  parser does not have — invention.
- **Hampers, build-your-own, subscriptions, reviews.** FR-09, FR-13, FR-15,
  FR-28, FR-30 are later phases. Fixed hampers are just products and need no new
  model; the bundle builder does.

## 5. Before this can take a real order

In priority order. The first two are blockers, not improvements.

1. **Replace the shipping rate card.** `data/shipping_rates.json` carries
   planning estimates from the requirements document, not quotes. It reports
   `"quoted": false` and the quote endpoint says so to the caller. Get written
   quotes from at least three carriers, including a Northern Ireland specialist
   and a chilled specialist.
2. **Supply the product data.** All 20 products are drafts. Each needs
   confirmed allergens, a price, a weight and at least one variant.
   `GET /api/admin/readiness` lists exactly what is missing per SKU.
3. **Decide the cheese redirects.** Four legacy collection URLs
   (`/collections/spanish-cheese`, `/collections/italian-cheese`,
   `/collections/meat-seafood`, `/collections/accompaniments`) are seeded
   pointing at `/shop` and flagged `REVIEW`. They hold real ranking equity and
   deserve better targets once the range going online is decided.
4. **Confirm the fulfilment rules.** Dispatch is configured Mon–Wed behind a
   12:00 cut-off, with 1-day chilled and 2-day ambient transit. Those are
   defaults from the requirements document; confirm them against how the
   Dunmurry unit actually works.
5. **Swap SQLite for Postgres** before production, and put the admin key behind
   a secret manager.
6. **Wire a payment provider** and move orders from `pending` to `paid` on the
   webhook.

## 6. Open questions this backend cannot answer

Carried forward from §19 of the requirements document, narrowed to the ones that
change the build:

- Is the online range these 20 own-production lines, or does the cheese
  catalogue go online too? The answer decides whether the category model needs
  sub-collections.
- Are any of these lines ambient rather than chilled? Every product currently
  defaults to ambient, and the chilled rules only bite once each product's
  temperature is set correctly.
- Is there an existing chilled carrier relationship, or does one need sourcing?
- Does the trade audience get a content page at launch, or an ordering portal
  later? Only the second needs backend work.
