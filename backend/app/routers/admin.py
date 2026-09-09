"""Admin surface: product notes import, catalogue editing, launch readiness.

Everything here sits behind ``X-Admin-Key``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import (
    UK_ALLERGENS,
    AllergenStatus,
    Category,
    Enquiry,
    MarketEvent,
    Order,
    Product,
    ProductAllergen,
    ProductStatus,
    Variant,
)
from ..parser import parse
from ..schemas import (
    EnquiryOut,
    ImportAmbiguity,
    ImportCommitRequest,
    ImportPreview,
    ImportRecord,
    ImportRequest,
    ImportResult,
    MarketEventIn,
    MarketEventOut,
    OrderOut,
    ProductDetail,
    ProductUpdate,
    ReadinessOut,
    ReadinessReport,
)
from ..security import require_admin
from ..services import readiness
from ..services.xlsx import build_workbook_bytes
from ..utils import make_sku, slugify, unique_slug

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _loaded_product(db: Session, slug: str) -> Product:
    product = db.scalar(
        select(Product)
        .where(Product.slug == slug)
        .options(
            selectinload(Product.variants),
            selectinload(Product.allergens),
            selectinload(Product.category),
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product {slug!r}.")
    return product


# --------------------------------------------------------------------------
# Import from raw product notes
# --------------------------------------------------------------------------


@router.post("/import/preview", response_model=ImportPreview)
def import_preview(payload: ImportRequest) -> ImportPreview:
    """Parse raw notes without touching the catalogue.

    Ambiguities are reported with their line numbers for a human to resolve.
    Nothing is guessed and nothing is invented.
    """
    records, ambiguities = parse(payload.raw_text)
    return ImportPreview(
        records=[ImportRecord(category=r.category, product=r.product, line=r.line) for r in records],
        ambiguities=[
            ImportAmbiguity(line=a.line, kind=a.kind, message=a.message) for a in ambiguities
        ],
        categories=list(dict.fromkeys(r.category for r in records)),
        can_commit=bool(records) and not ambiguities,
    )


@router.post("/import/commit", response_model=ImportResult)
def import_commit(payload: ImportCommitRequest, db: Session = Depends(get_db)) -> ImportResult:
    """Create draft products from raw notes.

    Products land as ``draft`` with no price, weight or allergen data. That is
    deliberate: those fields are supplied by the business, not inferred here.
    """
    records, ambiguities = parse(payload.raw_text)
    if not records:
        raise HTTPException(status_code=400, detail="No product records found in the input.")
    if ambiguities and not payload.allow_ambiguous:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Ambiguities found; nothing was written. Resolve them, or re-send "
                "with allow_ambiguous once a human has approved.",
                "ambiguities": [
                    {"line": a.line, "kind": a.kind, "message": a.message} for a in ambiguities
                ],
            },
        )

    existing_categories = {c.slug: c for c in db.scalars(select(Category))}
    taken_product_slugs = set(db.scalars(select(Product.slug)))

    created_categories: list[str] = []
    created_products: list[str] = []
    skipped: list[str] = []

    for record in records:
        category_slug = slugify(record.category)
        category = existing_categories.get(category_slug)
        if category is None:
            category = Category(
                slug=category_slug,
                name=record.category,
                position=len(existing_categories),
            )
            db.add(category)
            db.flush()
            existing_categories[category_slug] = category
            created_categories.append(record.category)

        candidate_slug = slugify(f"{record.category} {record.product}")
        if candidate_slug in taken_product_slugs:
            skipped.append(record.product)
            continue

        slug = unique_slug(candidate_slug, taken_product_slugs)
        taken_product_slugs.add(slug)
        db.add(
            Product(
                slug=slug,
                name=record.product,
                category_id=category.id,
                position=len(created_products),
                status=ProductStatus.draft,
                allergen_status=AllergenStatus.unconfirmed,
                source_line=record.line,
            )
        )
        created_products.append(record.product)

    db.commit()
    return ImportResult(
        created_categories=created_categories,
        created_products=created_products,
        skipped_existing=skipped,
        ambiguities=[
            ImportAmbiguity(line=a.line, kind=a.kind, message=a.message) for a in ambiguities
        ],
    )


@router.get("/export.xlsx")
def export_xlsx(db: Session = Depends(get_db)) -> Response:
    """The catalogue as a two-column `Category | Product` workbook.

    A genuine .xlsx, read back and checked cell by cell before it is returned.
    """
    products = list(
        db.scalars(
            select(Product)
            .join(Category)
            .options(selectinload(Product.category))
            .order_by(Category.position, Product.position, Product.id)
        )
    )
    rows = [(product.category.name, product.name) for product in products]
    if not rows:
        raise HTTPException(status_code=404, detail="The catalogue is empty; nothing to export.")

    data = build_workbook_bytes(rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="products.xlsx"'},
    )


# --------------------------------------------------------------------------
# Product editing and publishing
# --------------------------------------------------------------------------


@router.get("/allergens", response_model=list[str])
def list_allergens() -> list[str]:
    """The 14 allergens UK law requires a food business to declare."""
    return list(UK_ALLERGENS)


@router.patch("/products/{slug}", response_model=ProductDetail)
def update_product(slug: str, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = _loaded_product(db, slug)
    # Only fields the caller actually sent are touched; the nested collections
    # are handled as models so their defaults survive.
    scalar_fields = payload.model_fields_set - {"allergens", "variants"}
    for field in scalar_fields:
        setattr(product, field, getattr(payload, field))

    if payload.allergens is not None:
        unknown = sorted({a.allergen for a in payload.allergens} - set(UK_ALLERGENS))
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Not a regulated allergen: {', '.join(unknown)}. "
                f"Allowed: {', '.join(UK_ALLERGENS)}.",
            )
        product.allergens.clear()
        db.flush()
        for entry in payload.allergens:
            product.allergens.append(
                ProductAllergen(allergen=entry.allergen, presence=entry.presence)
            )

    if payload.variants is not None:
        product.variants.clear()
        db.flush()
        for position, entry in enumerate(payload.variants):
            product.variants.append(
                Variant(
                    sku=entry.sku
                    or make_sku(product.category.name, product.name, entry.label),
                    label=entry.label,
                    price_pence=entry.price_pence,
                    weight_grams=entry.weight_grams,
                    stock=entry.stock,
                    track_stock=entry.track_stock,
                    position=position,
                )
            )

    db.commit()
    db.refresh(product)
    from .catalogue import get_product  # local import avoids a cycle at module load

    return get_product(slug=product.slug, include_drafts=True, db=db)


@router.post("/products/{slug}/publish", response_model=ReadinessOut)
def publish_product(slug: str, db: Session = Depends(get_db)) -> ReadinessOut:
    """Publish a product, if it passes the launch gates.

    A product with unconfirmed allergen data is refused here. That is a legal
    requirement, not a policy this endpoint can be talked out of.
    """
    product = _loaded_product(db, slug)
    report = readiness.assess(product)
    if not report.ready:
        raise HTTPException(
            status_code=409,
            detail={"message": f"{product.name!r} is not ready to publish.", "blockers": report.blockers},
        )
    product.status = ProductStatus.active
    db.commit()
    db.refresh(product)
    return ReadinessOut(**vars(readiness.assess(product)))


@router.post("/products/{slug}/unpublish", response_model=ReadinessOut)
def unpublish_product(slug: str, db: Session = Depends(get_db)) -> ReadinessOut:
    product = _loaded_product(db, slug)
    product.status = ProductStatus.draft
    db.commit()
    db.refresh(product)
    return ReadinessOut(**vars(readiness.assess(product)))


@router.get("/readiness", response_model=ReadinessReport)
def readiness_report(db: Session = Depends(get_db)) -> ReadinessReport:
    """What is still missing before each product can go on sale."""
    products = list(
        db.scalars(
            select(Product)
            .join(Category)
            .options(selectinload(Product.variants), selectinload(Product.category))
            .order_by(Category.position, Product.position, Product.id)
        )
    )
    reports = [readiness.assess(product) for product in products]
    return ReadinessReport(
        summary=readiness.summarise(reports),
        products=[ReadinessOut(**vars(report)) for report in reports],
    )


# --------------------------------------------------------------------------
# Content and queues
# --------------------------------------------------------------------------


@router.post("/events", response_model=MarketEventOut, status_code=201)
def create_event(payload: MarketEventIn, db: Session = Depends(get_db)) -> MarketEvent:
    event = MarketEvent(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=MarketEventOut)
def update_event(event_id: int, payload: MarketEventIn, db: Session = Depends(get_db)):
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No event {event_id}.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> Response:
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No event {event_id}.")
    db.delete(event)
    db.commit()
    return Response(status_code=204)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(limit: int = 50, db: Session = Depends(get_db)) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .options(selectinload(Order.lines))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    )


@router.get("/enquiries", response_model=list[EnquiryOut])
def list_enquiries(
    handled: bool | None = None, limit: int = 50, db: Session = Depends(get_db)
) -> list[Enquiry]:
    statement = select(Enquiry)
    if handled is not None:
        statement = statement.where(Enquiry.handled.is_(handled))
    return list(db.scalars(statement.order_by(Enquiry.created_at.desc()).limit(limit)))
