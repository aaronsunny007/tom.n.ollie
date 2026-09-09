"""Turn a list of SKUs into a priced, weighed, allergen-labelled basket."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import AllergenStatus, Product, ProductStatus, Temperature, Variant


class BasketError(ValueError):
    """A basket that cannot be sold as submitted."""


@dataclass
class PricedLine:
    variant: Variant
    product: Product
    quantity: int
    unit_price_pence: int
    line_total_pence: int
    weight_grams: int
    allergen_summary: str


@dataclass
class PricedBasket:
    lines: list[PricedLine]
    subtotal_pence: int
    total_weight_grams: int
    requires_chilled: bool


def allergen_summary(product: Product) -> str:
    """The allergen line that follows this product onto the dispatch note.

    Only ever built from data a human confirmed. Products without confirmed
    allergens cannot be published, so they cannot reach this code.
    """
    contains = sorted(
        a.allergen.replace("_", " ") for a in product.allergens if a.presence.value == "contains"
    )
    may = sorted(
        a.allergen.replace("_", " ") for a in product.allergens if a.presence.value == "may_contain"
    )
    parts: list[str] = []
    if contains:
        parts.append("Contains: " + ", ".join(contains))
    if may:
        parts.append("May contain: " + ", ".join(may))
    if not parts:
        parts.append("Contains none of the 14 regulated allergens")
    if product.allergen_note:
        parts.append(product.allergen_note.strip())
    return ". ".join(parts)


def price_basket(db: Session, lines: list[tuple[str, int]]) -> PricedBasket:
    """Price a basket of ``(sku, quantity)`` pairs.

    Every failure mode is explicit rather than silently dropped: an unknown
    SKU, an unpublished product, a missing price and insufficient stock all
    raise, because each of them would otherwise take money for something that
    cannot be shipped.
    """
    if not lines:
        raise BasketError("The basket is empty.")

    merged: dict[str, int] = {}
    for sku, quantity in lines:
        if quantity < 1:
            raise BasketError(f"Quantity for {sku!r} must be at least 1.")
        merged[sku] = merged.get(sku, 0) + quantity

    variants = list(
        db.scalars(
            select(Variant)
            .where(Variant.sku.in_(merged))
            .options(
                selectinload(Variant.product).selectinload(Product.allergens),
                selectinload(Variant.product).selectinload(Product.category),
            )
        )
    )
    found = {variant.sku: variant for variant in variants}
    missing = sorted(set(merged) - set(found))
    if missing:
        raise BasketError(f"Unknown SKU(s): {', '.join(missing)}")

    priced: list[PricedLine] = []
    subtotal = 0
    weight = 0
    requires_chilled = False

    for sku, quantity in merged.items():
        variant = found[sku]
        product = variant.product

        if product.status is not ProductStatus.active:
            raise BasketError(f"{product.name!r} is not currently on sale.")
        if product.allergen_status is not AllergenStatus.confirmed:
            raise BasketError(
                f"{product.name!r} has no confirmed allergen data and cannot be sold."
            )
        if variant.price_pence is None:
            raise BasketError(f"{product.name!r} ({variant.label}) has no price.")
        if variant.weight_grams is None:
            raise BasketError(f"{product.name!r} ({variant.label}) has no weight.")
        if variant.track_stock and variant.stock < quantity:
            raise BasketError(
                f"Only {variant.stock} of {product.name!r} ({variant.label}) left in stock."
            )

        line_total = variant.price_pence * quantity
        subtotal += line_total
        weight += variant.weight_grams * quantity
        if product.temperature in (Temperature.chilled, Temperature.frozen):
            requires_chilled = True

        priced.append(
            PricedLine(
                variant=variant,
                product=product,
                quantity=quantity,
                unit_price_pence=variant.price_pence,
                line_total_pence=line_total,
                weight_grams=variant.weight_grams * quantity,
                allergen_summary=allergen_summary(product),
            )
        )

    # Packaging allowance: insulated liner and gel packs are real weight and
    # push parcels into higher bands if they are not counted.
    weight += 600 if requires_chilled else 200

    return PricedBasket(
        lines=priced,
        subtotal_pence=subtotal,
        total_weight_grams=weight,
        requires_chilled=requires_chilled,
    )
