"""Launch gates for a product.

The requirements document treats incomplete allergen data as a legal blocker
rather than a content gap, so this is enforced in code: a product cannot reach
``active`` until a human has confirmed its allergens. Nothing here infers or
generates allergen or dietary data — that has to come from the product spec.

The same gate covers the things that quietly cost money if they are missing:
a price, and a weight the shipping rates depend on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import AllergenStatus, Product, ProductStatus


@dataclass
class Readiness:
    slug: str
    name: str
    category: str
    status: ProductStatus
    ready: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assess(product: Product) -> Readiness:
    blockers: list[str] = []
    warnings: list[str] = []

    if product.allergen_status is not AllergenStatus.confirmed:
        blockers.append(
            "Allergen data is not confirmed. UK law requires allergen information before "
            "purchase and again in the parcel; it cannot be estimated."
        )

    if not product.variants:
        blockers.append("No sellable variant. Add at least one size before publishing.")

    for variant in product.variants:
        if variant.price_pence is None:
            blockers.append(f"Variant {variant.label!r} has no price.")
        elif variant.price_pence <= 0:
            blockers.append(f"Variant {variant.label!r} has a price of zero or less.")
        if variant.weight_grams is None:
            blockers.append(
                f"Variant {variant.label!r} has no weight. Shipping rates are priced by "
                "weight band, so a missing weight is a loss-making parcel."
            )

    if not product.description:
        warnings.append("No product description.")
    if not product.ingredients:
        warnings.append("No ingredients list.")
    if product.is_vegan is None or product.is_vegetarian is None:
        warnings.append("Dietary flags are unset, so the product will not appear in filters.")
    if product.temperature is None:
        warnings.append("No temperature class set; the product will ship as ambient.")
    if product.source_is_ai:
        warnings.append("Name came from the AI extraction path and has not been reviewed.")

    return Readiness(
        slug=product.slug,
        name=product.name,
        category=product.category.name if product.category else "",
        status=product.status,
        ready=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


def summarise(reports: list[Readiness]) -> dict:
    total = len(reports)
    ready = sum(1 for report in reports if report.ready)
    live = sum(1 for report in reports if report.status is ProductStatus.active)
    return {
        "total_products": total,
        "ready_to_publish": ready,
        "blocked": total - ready,
        "currently_live": live,
        "launch_ready": total > 0 and ready == total,
    }
