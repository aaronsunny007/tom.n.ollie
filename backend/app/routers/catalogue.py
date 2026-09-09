"""Public catalogue: categories, products, search and legacy URL resolution."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Category, LegacyPath, Product, ProductStatus, Temperature, Variant
from ..schemas import CategoryOut, ProductDetail, ProductPage, ProductSummary

router = APIRouter(prefix="/api", tags=["catalogue"])


def _summary(product: Product) -> ProductSummary:
    prices = [v.price_pence for v in product.variants if v.price_pence is not None]
    return ProductSummary(
        slug=product.slug,
        name=product.name,
        category=CategoryOut.model_validate(product.category),
        status=product.status,
        temperature=product.temperature,
        is_vegan=product.is_vegan,
        is_vegetarian=product.is_vegetarian,
        from_price_pence=min(prices) if prices else None,
        in_stock=any(v.in_stock for v in product.variants),
    )


def _loaded(statement):
    return statement.options(
        selectinload(Product.variants),
        selectinload(Product.category),
        selectinload(Product.allergens),
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.position, Category.name)))


@router.get("/categories/{slug}", response_model=CategoryOut)
def get_category(slug: str, db: Session = Depends(get_db)) -> Category:
    category = db.scalar(select(Category).where(Category.slug == slug))
    if category is None:
        raise HTTPException(status_code=404, detail=f"No category {slug!r}.")
    return category


@router.get("/products", response_model=ProductPage)
def list_products(
    db: Session = Depends(get_db),
    category: str | None = Query(default=None, description="Category slug"),
    q: str | None = Query(default=None, description="Free-text search"),
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    temperature: Temperature | None = None,
    in_stock: bool | None = None,
    include_drafts: bool = Query(
        default=False,
        description="Include products that are not yet published. Drafts are never buyable.",
    ),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProductPage:
    statement = select(Product).join(Category)
    if not include_drafts:
        statement = statement.where(Product.status == ProductStatus.active)
    if category:
        statement = statement.where(Category.slug == category)
    if vegan is not None:
        statement = statement.where(Product.is_vegan.is_(vegan))
    if vegetarian is not None:
        statement = statement.where(Product.is_vegetarian.is_(vegetarian))
    if temperature is not None:
        statement = statement.where(Product.temperature == temperature)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Product.name.ilike(pattern),
                Product.producer.ilike(pattern),
                Product.description.ilike(pattern),
                Category.name.ilike(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = statement.order_by(Category.position, Product.position, Product.name)
    products = list(db.scalars(_loaded(statement).limit(limit).offset(offset)).unique())

    if in_stock is not None:
        products = [p for p in products if any(v.in_stock for v in p.variants) is in_stock]

    return ProductPage(
        total=total, limit=limit, offset=offset, items=[_summary(p) for p in products]
    )


@router.get("/products/{slug}", response_model=ProductDetail)
def get_product(
    slug: str, include_drafts: bool = False, db: Session = Depends(get_db)
) -> ProductDetail:
    product = db.scalar(_loaded(select(Product).where(Product.slug == slug)))
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product {slug!r}.")
    if product.status is not ProductStatus.active and not include_drafts:
        raise HTTPException(status_code=404, detail=f"Product {slug!r} is not published.")

    summary = _summary(product)
    return ProductDetail(
        **summary.model_dump(),
        description=product.description,
        ingredients=product.ingredients,
        storage=product.storage,
        producer=product.producer,
        origin=product.origin,
        milk_type=product.milk_type,
        pasteurised=product.pasteurised,
        vegetarian_rennet=product.vegetarian_rennet,
        allergen_status=product.allergen_status,
        allergen_note=product.allergen_note,
        allergens=product.allergens,
        variants=product.variants,
    )


@router.get("/legacy-path", tags=["seo"])
def resolve_legacy_path(path: str, db: Session = Depends(get_db)) -> dict:
    """Where an old Shopify URL should now point.

    Legacy collection and page URLs still hold ranking equity, so the front end
    resolves them here and issues a 301 rather than serving a 404.
    """
    normalised = "/" + path.strip("/")
    row = db.scalar(select(LegacyPath).where(LegacyPath.path == normalised))
    if row is None:
        raise HTTPException(status_code=404, detail=f"No redirect mapped for {normalised!r}.")
    return {"path": row.path, "redirect_to": row.redirect_to, "status": 301, "note": row.note}


@router.get("/legacy-paths", tags=["seo"], response_model=list[dict])
def list_legacy_paths(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(LegacyPath).order_by(LegacyPath.path))
    return [{"path": r.path, "redirect_to": r.redirect_to, "note": r.note} for r in rows]
