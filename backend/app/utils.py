"""Small shared helpers."""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import datetime, timezone


def slugify(value: str) -> str:
    """URL-safe slug. Only ever used for URLs — never to rewrite a product name."""
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return cleaned or "item"


def unique_slug(base: str, taken: set[str]) -> str:
    slug = slugify(base)
    if slug not in taken:
        return slug
    for suffix in range(2, 1000):
        candidate = f"{slug}-{suffix}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"Could not build a unique slug from {base!r}")


def make_sku(category: str, product: str, label: str) -> str:
    parts = [slugify(category)[:3].upper(), slugify(product)[:8].upper(), slugify(label).upper()]
    return "-".join(part for part in parts if part)


def order_number(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"TO-{now:%y%m%d}-{secrets.token_hex(3).upper()}"


def new_token() -> str:
    return secrets.token_urlsafe(32)
