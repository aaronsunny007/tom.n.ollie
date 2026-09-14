// Tom & Ollie storefront — vanilla JS, no build step. Talks to the FastAPI
// backend's public endpoints only (never the admin API, never a key).
"use strict";

// Same-origin by default (the backend mounts this directory itself). A
// separate static deployment can set window.TANDO_API_BASE in its own
// <script> before this file loads. This is deliberately NOT settable from
// the URL (e.g. ?api=) or any other visitor-controlled input: a query
// param here would let an attacker craft a link that silently sends every
// API call — including a checkout with the customer's name, email and
// address — to a server of their choosing while the address bar still
// shows the real site.
const API_BASE = window.TANDO_API_BASE || "";

const CATEGORY_COLORS = {
  hummus: "var(--hummus)",
  pesto: "var(--pesto)",
  olives: "var(--olives)",
  "sweet-pepper-drops": "var(--peppers)",
};
const FALLBACK_COLORS = ["var(--forest)", "var(--orange)", "var(--lime-dark)"];

const pence = (n) => `£${(n / 100).toFixed(2)}`;

function accentFor(slug, index) {
  return CATEGORY_COLORS[slug] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

// Product photography (design_handoff_shop_redesign): first-party pack shots
// supplied by the business owner, mapped by product slug. The backend has no
// image field — presentation-only per the handoff's own stated scope — so
// this map is the source of truth for "which photo," never the API.
const PRODUCT_IMAGES = {
  "hummus-traditional-hummus": "assets/products/hummus-traditional.png",
  "hummus-beetroot-hummus": "assets/products/hummus-beetroot.png",
  "hummus-chilli-basil-garlic-hummus": "assets/products/hummus-chilli.png",
  "hummus-vegan-chilli-basil-garlic-hummus": "assets/products/pesto-chilli-hummus.png",
  "hummus-caramelised-onion-hummus": "assets/products/hummus-onion.png",
  "hummus-red-pepper-hummus": "assets/products/hummus-redpepper.png",
  "pesto-smoked-tomato-pesto": "assets/products/pesto-smoked.png",
  "pesto-vegan-basil": "assets/products/pesto-basil.png",
  "pesto-basil": "assets/products/pesto-basil.png",
  "pesto-lyness-basil": "assets/products/pesto-basil.png",
  "olives-pitted-green-olives": "assets/products/olives-lemon.png",
  "olives-pitted-kalamata": "assets/products/black-olives.png",
  "olives-italian-mixed": "assets/products/olives-mixed.png",
  "olives-house-mix": "assets/products/olives-house-mix.png",
  "olives-global-mix": "assets/products/olives-herb.png",
  "olives-chilli-basil-garlic-green-olives": "assets/products/olives-herb.png",
  "olives-garlicy-green-olives": "assets/products/olives-lemon.png",
  "sweet-pepper-drops-red": "assets/products/drops-red.png",
  "sweet-pepper-drops-mixed": "assets/products/drops-mixed.png",
  "sweet-pepper-drops-yellow": "assets/products/yellow-drops.png",
};
// A product not yet in the map above (a new line the business adds before
// its own pack shot exists) falls back to its category photo rather than an
// empty well.
const CATEGORY_FALLBACK_IMAGES = {
  hummus: "assets/hummus-collection.png",
  pesto: "assets/pesto-range.png",
  olives: "assets/olives-tapenades.png",
  "sweet-pepper-drops": "assets/products/drops-mixed.png",
};
function imageFor(product) {
  return PRODUCT_IMAGES[product.slug] || CATEGORY_FALLBACK_IMAGES[product.category.slug] || null;
}

const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Shared pointer-tilt used by product cards and the market photo: normalise
// the pointer position within the element to -0.5..0.5 and turn it into a
// small rotate + lift. Skipped entirely under reduced motion rather than
// just softened, since it's a motion effect tied to pointer movement, not
// content.
function wireTilt(el, { rotateMax = 12, translateY = -8, scale = 1.02 } = {}) {
  if (!el || REDUCE_MOTION) return;
  el.addEventListener("mousemove", (e) => {
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `translateY(${translateY}px) rotateY(${(x * rotateMax).toFixed(2)}deg) rotateX(${(-y * rotateMax).toFixed(2)}deg) scale(${scale})`;
  });
  el.addEventListener("mouseleave", () => { el.style.transform = ""; });
}

// Hero stage tilts more (16°/12°) and doesn't lift/scale — it's a whole
// floating stage, not a single card. Listener sits on the wider visual
// column (matching the design reference) so the tilt still engages when the
// pointer is over the gaps between the three flip cards, not just on them.
function wireHeroTilt() {
  const zone = document.querySelector(".hero-visual");
  const stage = document.getElementById("heroStage");
  if (!zone || !stage || REDUCE_MOTION) return;
  zone.addEventListener("mousemove", (e) => {
    const r = zone.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    stage.style.transform = `rotateY(${(x * 16).toFixed(2)}deg) rotateX(${(-y * 12).toFixed(2)}deg)`;
  });
  zone.addEventListener("mouseleave", () => { stage.style.transform = ""; });
}

// Each flip card's open/closed state lives in its own aria-pressed attribute
// — a real <button> per the handoff's explicit accessibility requirement,
// not a clickable <div>, so it's reachable and operable by keyboard with no
// extra wiring beyond the click handler itself.
function wireFlipCards() {
  document.querySelectorAll(".flip-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pressed = btn.getAttribute("aria-pressed") === "true";
      btn.setAttribute("aria-pressed", String(!pressed));
      const hint = btn.querySelector("[data-hint]");
      if (hint) hint.textContent = pressed ? "Tap to reveal" : "Tap to hide";
    });
  });
}

// FastAPI validation errors (422) return `detail` as an array of
// {loc, msg, type} objects, not a string. Left unhandled, that array gets
// JSON.stringify'd and shown to the customer verbatim (raw field paths,
// pydantic type names). Fold it into one readable sentence instead.
function friendlyErrorMessage(detail, path, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const msgs = detail
      .map((item) => (item && typeof item.msg === "string" ? item.msg : null))
      .filter(Boolean);
    if (msgs.length > 0) return msgs.join(" ");
  }
  return `Something went wrong (${status}). Please try again.`;
}

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error("Couldn't reach the server — check your connection and try again.");
  }

  let body = null;
  const text = await res.text();
  if (text) {
    try { body = JSON.parse(text); } catch { body = null; }
  }
  if (!res.ok) {
    throw new Error(friendlyErrorMessage(body && body.detail, path, res.status));
  }
  return body;
}

// ---------------------------------------------------------------- state ---

const state = {
  categories: [],
  products: [],
  filtered: [],
  filters: { category: "", q: "", vegan: false, vegetarian: false, available: false },
  basket: loadBasket(),
  quote: null,
};

// A malformed value here (a stale schema from a previous version, a hand
// edit in devtools, a corrupted write) must never crash the page — every
// basket operation downstream (.map/.reduce/.find) assumes a clean array
// of well-shaped lines, so sanitize on the way in rather than trusting
// storage.
function sanitizeBasketLine(line) {
  if (!line || typeof line !== "object") return null;
  const sku = typeof line.sku === "string" && line.sku.trim() ? line.sku : null;
  const name = typeof line.name === "string" ? line.name : "";
  const variantLabel = typeof line.variantLabel === "string" ? line.variantLabel : "";
  const unitPricePence = Number.isFinite(line.unitPricePence) && line.unitPricePence >= 0
    ? Math.round(line.unitPricePence)
    : null;
  const qty = Number.isFinite(line.qty) ? Math.min(99, Math.max(1, Math.round(line.qty))) : null;
  if (!sku || unitPricePence === null || qty === null) return null;
  return { sku, name, variantLabel, unitPricePence, qty };
}

function loadBasket() {
  try {
    const raw = localStorage.getItem("tando_basket");
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.map(sanitizeBasketLine).filter(Boolean);
  } catch {
    return [];
  }
}
function saveBasket() {
  try { localStorage.setItem("tando_basket", JSON.stringify(state.basket)); } catch { /* private mode etc. */ }
}

// ------------------------------------------------------------- toast ------

let toastTimer = null;
function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2600);
}

// --------------------------------------------------------- catalogue ------

async function loadCatalogue() {
  const heroStatus = document.getElementById("heroStatus");
  try {
    const [categories, page] = await Promise.all([
      api("/api/categories"),
      api("/api/products?include_drafts=true&limit=100"),
    ]);
    state.categories = categories;
    state.products = page.items;
    renderCategoryPills();
    applyFilters();

    heroStatus.textContent = `${state.products.length} lines across four ranges, all made in Belfast.`;
  } catch (err) {
    heroStatus.textContent = "Couldn't reach the shop just now — please refresh.";
    console.error(err);
  }
}

function renderCategoryPills() {
  const wrap = document.getElementById("categoryPills");
  const buttons = [`<button class="pill is-active" data-category="" role="tab" aria-selected="true">All</button>`];
  state.categories.forEach((c) => {
    buttons.push(`<button class="pill" data-category="${c.slug}" role="tab" aria-selected="false">${escapeHtml(c.name)}</button>`);
  });
  wrap.innerHTML = buttons.join("");
  wrap.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      wrap.querySelectorAll(".pill").forEach((b) => { b.classList.remove("is-active"); b.setAttribute("aria-selected", "false"); });
      btn.classList.add("is-active");
      btn.setAttribute("aria-selected", "true");
      state.filters.category = btn.dataset.category;
      applyFilters();
    });
  });
}

function applyFilters() {
  const { category, q, vegan, vegetarian, available } = state.filters;
  const needle = q.trim().toLowerCase();

  state.filtered = state.products.filter((p) => {
    if (category && p.category.slug !== category) return false;
    if (vegan && p.is_vegan !== true) return false;
    if (vegetarian && p.is_vegetarian !== true) return false;
    if (available && p.status !== "active") return false;
    if (needle && !(`${p.name} ${p.category.name}`.toLowerCase().includes(needle))) return false;
    return true;
  });

  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById("productGrid");
  const empty = document.getElementById("emptyState");
  const count = document.getElementById("resultCount");

  count.textContent = state.filtered.length === state.products.length
    ? `Showing all ${state.products.length} lines.`
    : `Showing ${state.filtered.length} of ${state.products.length} lines.`;

  if (state.filtered.length === 0) {
    grid.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  grid.innerHTML = state.filtered.map((p, i) => productCard(p, i)).join("");

  grid.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".add-btn")) return;
      openProductModal(card.dataset.slug);
    });
    card.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && !e.target.closest(".add-btn")) {
        e.preventDefault();
        openProductModal(card.dataset.slug);
      }
    });
    wireTilt(card);
  });
  grid.querySelectorAll(".add-btn").forEach((btn) => {
    const handler = withPending(btn, () => quickAdd(btn.dataset.slug));
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      handler();
    });
  });
}

function productCard(p, index) {
  const accent = accentFor(p.category.slug, index);
  const isLive = p.status === "active";
  const canAdd = isLive && p.in_stock;
  const priceText = p.from_price_pence != null ? `from ${pence(p.from_price_pence)}` : "Price coming soon";
  const img = imageFor(p);

  // One badge slot: dietary flag takes priority (it's the more specific,
  // less-often-true fact), falling back to a live-availability flag.
  const badge = p.is_vegan ? "Vegan" : p.is_vegetarian ? "Vegetarian" : (canAdd ? "Available now" : null);

  return `
    <article class="card cat-${escapeHtml(p.category.slug)}" data-slug="${escapeHtml(p.slug)}" tabindex="0" style="animation-delay:${Math.min(index * 40, 400)}ms">
      <div class="card-top"></div>
      <div class="card-image-well">
        ${img ? `<img src="${escapeHtml(img)}" alt="${escapeHtml(p.name)}" loading="lazy" />` : ""}
        <span class="card-cat" style="background:${accent}">${escapeHtml(p.category.name)}</span>
        ${badge ? `<span class="card-badge">${escapeHtml(badge)}</span>` : ""}
      </div>
      <div class="card-body">
        <h3 class="card-name">${escapeHtml(p.name)}</h3>
        <div class="card-spacer"></div>
        <div class="status-row">
          <span class="price">${priceText}</span>
          <button class="add-btn" data-slug="${escapeHtml(p.slug)}" ${canAdd ? "" : "disabled"}>
            ${canAdd ? "Add to basket" : (isLive ? "Out of stock" : "Coming soon")}
          </button>
        </div>
      </div>
    </article>`;
}

// ------------------------------------------------------------- modal ------

async function openProductModal(slug) {
  const backdrop = document.getElementById("modalBackdrop");
  const modal = document.getElementById("productModal");
  const body = document.getElementById("modalBody");
  body.innerHTML = `<p class="muted">Loading…</p>`;
  backdrop.hidden = false;
  modal.hidden = false;

  try {
    const p = await api(`/api/products/${encodeURIComponent(slug)}?include_drafts=true`);
    body.innerHTML = modalContent(p);
    wireModalActions(p);
  } catch (err) {
    body.innerHTML = `<p class="muted">Couldn't load this product right now.</p>`;
  }
}

function modalContent(p) {
  const isLive = p.status === "active";
  const accent = accentFor(p.category.slug, 0);
  const diet = [];
  if (p.is_vegan) diet.push("Vegan");
  else if (p.is_vegetarian) diet.push("Vegetarian");

  const variantOptions = (p.variants || [])
    .filter((v) => v.price_pence != null)
    .map((v) => `<option value="${v.sku}" ${!v.in_stock ? "disabled" : ""}>${escapeHtml(v.label)} — ${pence(v.price_pence)}${v.in_stock ? "" : " (out of stock)"}</option>`)
    .join("");

  return `
    <span class="card-cat modal-cat" style="background:${accent}">${escapeHtml(p.category.name)}</span>
    <h2 class="modal-title">${escapeHtml(p.name)}</h2>
    ${diet.length ? `<div class="diet-row">${diet.map((d) => `<span class="diet-tag">${d}</span>`).join("")}</div>` : ""}

    ${p.description ? `<div class="modal-section"><p>${escapeHtml(p.description)}</p></div>` : `<p class="muted">Full details are being finalised by Tom &amp; Ollie.</p>`}

    ${p.ingredients ? `<div class="modal-section"><h4>Ingredients</h4><p>${escapeHtml(p.ingredients)}</p></div>` : ""}

    <div class="modal-section">
      <h4>Allergens</h4>
      <div class="allergen-box">
        ${p.allergen_status === "confirmed"
          ? escapeHtml(p.allergen_note || allergenListText(p.allergens))
          : "Not yet confirmed by Tom &amp; Ollie — this line can't be ordered until it is."}
      </div>
    </div>

    <div class="modal-section">
      ${isLive
        ? (variantOptions
            ? `
              <label>Size
                <select id="modalVariant">${variantOptions}</select>
              </label>
              <div class="qty-stepper" style="margin:10px 0;">
                <button type="button" id="modalQtyDown" aria-label="Decrease quantity">−</button>
                <span id="modalQty">1</span>
                <button type="button" id="modalQtyUp" aria-label="Increase quantity">+</button>
              </div>
              <button class="btn btn-primary btn-block" id="modalAddBtn">Add to basket</button>`
            : `<p class="muted">No sizes are in stock right now.</p>`)
        : `<p class="muted">This line isn't open for order yet — check back after relaunch.</p>`}
    </div>`;
}

function allergenListText(allergens) {
  if (!allergens || allergens.length === 0) return "Contains no listed allergens.";
  return `Contains: ${allergens.map((a) => a.allergen).join(", ")}.`;
}

function wireModalActions(p) {
  const qtyEl = document.getElementById("modalQty");
  const up = document.getElementById("modalQtyUp");
  const down = document.getElementById("modalQtyDown");
  const addBtn = document.getElementById("modalAddBtn");
  let qty = 1;

  up?.addEventListener("click", () => { qty = Math.min(99, qty + 1); qtyEl.textContent = qty; });
  down?.addEventListener("click", () => { qty = Math.max(1, qty - 1); qtyEl.textContent = qty; });

  addBtn?.addEventListener("click", withPending(addBtn, async () => {
    const select = document.getElementById("modalVariant");
    const sku = select ? select.value : null;
    const variant = (p.variants || []).find((v) => v.sku === sku);
    if (!variant) return;
    addToBasket({
      sku: variant.sku,
      name: p.name,
      variantLabel: variant.label,
      unitPricePence: variant.price_pence,
      qty,
    });
    closeModal();
  }));
}

function closeModal() {
  document.getElementById("modalBackdrop").hidden = true;
  document.getElementById("productModal").hidden = true;
}

async function quickAdd(slug) {
  try {
    const p = await api(`/api/products/${encodeURIComponent(slug)}?include_drafts=true`);
    const variants = (p.variants || []).filter((v) => v.price_pence != null && v.in_stock);
    if (variants.length === 0) { toast("That line isn't available to order right now."); return; }
    if (variants.length > 1) { openProductModal(slug); return; }
    const v = variants[0];
    addToBasket({ sku: v.sku, name: p.name, variantLabel: v.label, unitPricePence: v.price_pence, qty: 1 });
  } catch {
    toast("Couldn't add that item — please try again.");
  }
}

// ------------------------------------------------------------ basket ------

function addToBasket({ sku, name, variantLabel, unitPricePence, qty }) {
  const existing = state.basket.find((l) => l.sku === sku);
  if (existing) existing.qty = Math.min(99, existing.qty + qty);
  else state.basket.push({ sku, name, variantLabel, unitPricePence, qty });
  saveBasket();
  state.quote = null;
  renderBasket();
  toast(`Added ${name} to your basket.`);
}

function renderBasket() {
  const count = state.basket.reduce((sum, l) => sum + l.qty, 0);
  const countEl = document.getElementById("basketCount");
  countEl.textContent = count;
  countEl.hidden = count === 0;

  const linesEl = document.getElementById("basketLines");
  const emptyEl = document.getElementById("basketEmpty");
  const totalsEl = document.getElementById("basketTotals");
  const quoteForm = document.getElementById("quoteForm");
  const checkoutForm = document.getElementById("checkoutForm");

  if (state.basket.length === 0) {
    linesEl.innerHTML = "";
    emptyEl.hidden = false;
    totalsEl.hidden = true;
    quoteForm.hidden = true;
    checkoutForm.hidden = true;
    return;
  }
  emptyEl.hidden = true;
  totalsEl.hidden = false;
  quoteForm.hidden = false;

  linesEl.innerHTML = state.basket.map((l) => `
    <li class="basket-line" data-sku="${l.sku}">
      <div>
        <div class="basket-line-name">${escapeHtml(l.name)}</div>
        <div class="basket-line-meta">${escapeHtml(l.variantLabel)} · ${pence(l.unitPricePence)} each</div>
      </div>
      <div class="qty-stepper">
        <button type="button" class="qty-down" aria-label="Decrease quantity">−</button>
        <span>${l.qty}</span>
        <button type="button" class="qty-up" aria-label="Increase quantity">+</button>
      </div>
    </li>`).join("");

  linesEl.querySelectorAll(".basket-line").forEach((row) => {
    const sku = row.dataset.sku;
    row.querySelector(".qty-up").addEventListener("click", () => changeQty(sku, 1));
    row.querySelector(".qty-down").addEventListener("click", () => changeQty(sku, -1));
  });

  const subtotal = state.basket.reduce((sum, l) => sum + l.unitPricePence * l.qty, 0);
  document.getElementById("basketSubtotal").textContent = pence(subtotal);

  document.getElementById("quoteResult").innerHTML = "";
  checkoutForm.hidden = true;
}

function changeQty(sku, delta) {
  const line = state.basket.find((l) => l.sku === sku);
  if (!line) return;
  line.qty = Math.min(99, line.qty + delta);
  if (line.qty <= 0) state.basket = state.basket.filter((l) => l.sku !== sku);
  saveBasket();
  state.quote = null;
  renderBasket();
}

function openBasket() {
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("basketDrawer").hidden = false;
}
function closeBasket() {
  document.getElementById("drawerBackdrop").hidden = true;
  document.getElementById("basketDrawer").hidden = true;
}

// ------------------------------------------------------------- quote ------

async function getQuote() {
  const country = document.getElementById("quoteCountry").value;
  const postcode = document.getElementById("quotePostcode").value.trim();
  const resultEl = document.getElementById("quoteResult");
  if (!postcode) { resultEl.innerHTML = `<p class="form-note err">Enter a postcode to get a quote.</p>`; return; }

  resultEl.innerHTML = `<p class="muted">Getting delivery options…</p>`;
  try {
    const payload = {
      lines: state.basket.map((l) => ({ sku: l.sku, quantity: l.qty })),
      country, postcode,
    };
    const quote = await api("/api/cart/quote", { method: "POST", body: JSON.stringify(payload) });
    state.quote = { ...quote, country, postcode };
    renderQuote(quote);
  } catch (err) {
    resultEl.innerHTML = `<p class="form-note err">${escapeHtml(err.message)}</p>`;
  }
}

function renderQuote(quote) {
  const resultEl = document.getElementById("quoteResult");
  const notices = quote.notices.map((n) => `<div class="notice-banner">${escapeHtml(n)}</div>`).join("");
  const options = quote.shipping_options.map((o) => `
    <label class="ship-option">
      <span>
        <strong>${escapeHtml(o.label)}</strong>
        Delivery by ${o.earliest_delivery}${o.free_delivery_applied ? " · Free delivery" : ""}
      </span>
      <span style="display:flex; align-items:center; gap:8px;">
        ${pence(o.price_pence)}
        <input type="radio" name="shipOption" value="${escapeHtml(o.service)}" data-dates='${JSON.stringify(o.delivery_dates)}' ${quote.shipping_options[0] === o ? "checked" : ""} />
      </span>
    </label>`).join("");

  resultEl.innerHTML = `${notices}${options || '<p class="muted">No delivery service can carry this basket to that address.</p>'}`;

  if (quote.shipping_options.length > 0) {
    document.getElementById("checkoutForm").hidden = false;
  }
}

function selectedShipOption() {
  const radio = document.querySelector('input[name="shipOption"]:checked');
  if (!radio) return null;
  return { service: radio.value, dates: JSON.parse(radio.dataset.dates) };
}

// ----------------------------------------------------------- checkout -----

async function placeOrder() {
  const note = document.getElementById("orderNote");
  note.className = "form-note";
  note.textContent = "";

  const opt = selectedShipOption();
  if (!state.quote || !opt) { note.textContent = "Get a delivery quote first."; note.className = "form-note err"; return; }

  const email = document.getElementById("ckEmail").value.trim();
  const name = document.getElementById("ckName").value.trim();
  const line1 = document.getElementById("ckLine1").value.trim();
  const city = document.getElementById("ckCity").value.trim();
  const postcode = document.getElementById("ckPostcode").value.trim();
  const isGift = document.getElementById("ckGift").checked;

  if (!email || !name || !line1 || !city || !postcode) {
    note.textContent = "Fill in your name, email and full address.";
    note.className = "form-note err";
    return;
  }

  const payload = {
    lines: state.basket.map((l) => ({ sku: l.sku, quantity: l.qty })),
    email, customer_name: name,
    delivery: {
      name, line1,
      line2: document.getElementById("ckLine2").value.trim() || null,
      city, postcode,
      country: state.quote.country,
    },
    shipping_service: opt.service,
    delivery_date: opt.dates[0],
    is_gift: isGift,
    gift_message: isGift ? (document.getElementById("ckGiftMsg").value.trim() || null) : null,
  };

  try {
    const order = await api("/api/orders", { method: "POST", body: JSON.stringify(payload) });
    note.textContent = `Order placed — ${order.number}. Dispatching ${order.dispatch_date}, arriving ${order.delivery_date}.`;
    note.className = "form-note ok";
    state.basket = [];
    saveBasket();
    state.quote = null;
    renderBasket();
  } catch (err) {
    note.textContent = err.message;
    note.className = "form-note err";
  }
}

// -------------------------------------------------------------- market ----

function formatEventMeta(e) {
  const short = (iso) => {
    const d = new Date(`${iso}T00:00:00`);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  };
  let range = short(e.starts_on);
  if (e.ends_on && e.ends_on !== e.starts_on) range += `–${short(e.ends_on)}`;
  return e.opening_time ? `${range} · ${e.opening_time}` : range;
}

async function loadEvents() {
  const listEl = document.getElementById("eventList");
  const emptyEl = document.getElementById("eventEmpty");
  try {
    const events = await api("/api/events");
    if (events.length === 0) { emptyEl.hidden = false; return; }
    listEl.innerHTML = events.map((e) => `
      <div class="event-card">
        <span class="event-title">${escapeHtml(e.title)}${e.location ? ` · ${escapeHtml(e.location)}` : ""}</span>
        <span class="event-loc">${escapeHtml(formatEventMeta(e))}</span>
      </div>`).join("");
  } catch {
    emptyEl.hidden = false;
  }
}

// ------------------------------------------------------------- forms ------

function wireEnquiryForm() {
  const form = document.getElementById("enquiryForm");
  const note = document.getElementById("enquiryNote");
  const submitBtn = form.querySelector('button[type="submit"]');
  form.addEventListener("submit", withPending(submitBtn, async (e) => {
    e.preventDefault();
    note.textContent = "Sending…";
    note.className = "form-note";
    const data = Object.fromEntries(new FormData(form).entries());
    // Empty optional fields still arrive as "" from FormData; store as
    // absent rather than an empty string so it reads the same as never
    // having been filled in.
    if (typeof data.company === "string" && data.company.trim() === "") delete data.company;
    try {
      await api("/api/enquiries", { method: "POST", body: JSON.stringify(data) });
      note.textContent = "Thanks — we'll be in touch shortly.";
      note.className = "form-note ok";
      form.reset();
    } catch (err) {
      note.textContent = err.message;
      note.className = "form-note err";
    }
  }));
}

function wireNewsletterForm() {
  const form = document.getElementById("newsletterForm");
  const note = document.getElementById("newsletterNote");
  const submitBtn = form.querySelector('button[type="submit"]');
  form.addEventListener("submit", withPending(submitBtn, async (e) => {
    e.preventDefault();
    note.textContent = "Subscribing…";
    note.className = "form-note";
    const email = document.getElementById("newsletterEmail").value.trim();
    try {
      const res = await api("/api/newsletter/subscribe", { method: "POST", body: JSON.stringify({ email, source: "website" }) });
      note.textContent = res.status === "already_subscribed"
        ? "You're already on the list."
        : "Almost there — check your email to confirm.";
      note.className = "form-note ok";
      form.reset();
    } catch (err) {
      note.textContent = err.message;
      note.className = "form-note err";
    }
  }));
}

// -------------------------------------------------------------- misc ------

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// Guards a button against double-submit: a fast double click or double tap
// otherwise fires two concurrent requests (two orders, two enquiries, two
// basket lines added) before the first one's response disables anything.
function withPending(button, fn) {
  return async (...args) => {
    if (!button || button.disabled) return;
    const original = button.textContent;
    button.disabled = true;
    try {
      await fn(...args);
    } finally {
      button.disabled = false;
      if (original !== undefined) button.textContent = original;
    }
  };
}

// ------------------------------------------------------------- init -------

function wireStaticUI() {
  document.getElementById("year").textContent = new Date().getFullYear();

  const navToggle = document.getElementById("navToggle");
  const nav = document.getElementById("mainNav");
  navToggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
  nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => {
    nav.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
  }));

  document.getElementById("basketToggle").addEventListener("click", openBasket);
  document.getElementById("basketClose").addEventListener("click", closeBasket);
  document.getElementById("drawerBackdrop").addEventListener("click", closeBasket);

  document.getElementById("modalClose").addEventListener("click", closeModal);
  document.getElementById("modalBackdrop").addEventListener("click", closeModal);
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeModal();
    closeBasket();
  });

  document.getElementById("searchInput").addEventListener("input", debounce((e) => {
    state.filters.q = e.target.value;
    applyFilters();
  }, 150));

  ["veganChip", "vegChip", "availableChip"].forEach((id) => {
    const chip = document.getElementById(id);
    chip.addEventListener("click", () => {
      const pressed = chip.getAttribute("aria-pressed") === "true";
      chip.setAttribute("aria-pressed", String(!pressed));
      state.filters[chip.dataset.flag] = !pressed;
      applyFilters();
    });
  });

  const quoteBtn = document.getElementById("getQuoteBtn");
  quoteBtn.addEventListener("click", withPending(quoteBtn, getQuote));
  const orderBtn = document.getElementById("placeOrderBtn");
  orderBtn.addEventListener("click", withPending(orderBtn, placeOrder));
  document.getElementById("ckGift").addEventListener("change", (e) => {
    document.getElementById("ckGiftMsgWrap").hidden = !e.target.checked;
  });

  wireEnquiryForm();
  wireNewsletterForm();

  wireFlipCards();
  wireHeroTilt();
  wireTilt(document.getElementById("marketPhoto"));
}

// A last-resort net: an uncaught error anywhere in the boot sequence used
// to abort every statement after it (that's how a single corrupted
// localStorage value could take down the whole page — see loadBasket
// above). These handlers stop that class of bug from ever going silent,
// and the try/catch keeps one failed boot step (e.g. a wiring bug) from
// blocking the others.
window.addEventListener("error", (e) => {
  console.error("Unhandled error:", e.error || e.message);
  toast("Something went wrong loading part of the page — please refresh.");
});
window.addEventListener("unhandledrejection", (e) => {
  console.error("Unhandled promise rejection:", e.reason);
});

try { wireStaticUI(); } catch (err) { console.error("wireStaticUI failed:", err); }
try { renderBasket(); } catch (err) { console.error("renderBasket failed:", err); }
loadCatalogue();
loadEvents();
