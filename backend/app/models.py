"""SQLAlchemy models for the Tom & Ollie storefront backend."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProductStatus(str, enum.Enum):
    """A product is only buyable once it is ``active``.

    Publishing is gated on the launch checks in ``services.readiness`` — most
    importantly on allergen data, which is a legal requirement and cannot be
    inferred.
    """

    draft = "draft"
    active = "active"
    archived = "archived"


class Temperature(str, enum.Enum):
    """Drives the shipping rules: chilled goods need a named/next-day service."""

    ambient = "ambient"
    chilled = "chilled"
    frozen = "frozen"


class AllergenStatus(str, enum.Enum):
    """Whether a human has signed off the allergen data for this product."""

    unconfirmed = "unconfirmed"
    confirmed = "confirmed"


class AllergenPresence(str, enum.Enum):
    contains = "contains"
    may_contain = "may_contain"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    dispatched = "dispatched"
    cancelled = "cancelled"


class EnquiryKind(str, enum.Enum):
    trade = "trade"
    corporate = "corporate"
    general = "general"


# The 14 allergens that UK law requires a food business to declare.
UK_ALLERGENS: tuple[str, ...] = (
    "celery",
    "cereals_containing_gluten",
    "crustaceans",
    "eggs",
    "fish",
    "lupin",
    "milk",
    "molluscs",
    "mustard",
    "peanuts",
    "sesame",
    "soybeans",
    "sulphur_dioxide",
    "tree_nuts",
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    products: Mapped[list["Product"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="Product.position"
    )
    legacy_paths: Mapped[list["LegacyPath"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class LegacyPath(Base):
    """A legacy Shopify URL that must keep resolving (PRD §07).

    Every indexed path either maps to a category here or gets an explicit
    redirect target — never a 404.
    """

    __tablename__ = "legacy_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    redirect_to: Mapped[str] = mapped_column(String(255))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)

    category: Mapped[Category | None] = relationship(back_populates="legacy_paths")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    # Preserved byte-for-byte from the source notes. Never normalised.
    name: Mapped[str] = mapped_column(String(200), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False), default=ProductStatus.draft, index=True
    )
    temperature: Mapped[Temperature] = mapped_column(
        Enum(Temperature, native_enum=False), default=Temperature.ambient
    )

    description: Mapped[str | None] = mapped_column(Text, default=None)
    ingredients: Mapped[str | None] = mapped_column(Text, default=None)
    storage: Mapped[str | None] = mapped_column(Text, default=None)

    # Provenance (FR-02) — optional, but surfaced on the product page when set.
    producer: Mapped[str | None] = mapped_column(String(160), default=None)
    origin: Mapped[str | None] = mapped_column(String(160), default=None)
    milk_type: Mapped[str | None] = mapped_column(String(80), default=None)
    pasteurised: Mapped[bool | None] = mapped_column(Boolean, default=None)
    vegetarian_rennet: Mapped[bool | None] = mapped_column(Boolean, default=None)

    # Dietary flags are tri-state on purpose: NULL means "nobody has said yet",
    # which is different from "no".
    is_vegan: Mapped[bool | None] = mapped_column(Boolean, default=None)
    is_vegetarian: Mapped[bool | None] = mapped_column(Boolean, default=None)

    allergen_status: Mapped[AllergenStatus] = mapped_column(
        Enum(AllergenStatus, native_enum=False), default=AllergenStatus.unconfirmed
    )
    allergen_note: Mapped[str | None] = mapped_column(Text, default=None)

    source_line: Mapped[int | None] = mapped_column(Integer, default=None)
    source_is_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list["Variant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="Variant.position"
    )
    allergens: Mapped[list["ProductAllergen"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Variant(Base):
    """A sellable size of a product — cheese and mezze are sold by weight (FR-04)."""

    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("product_id", "label", name="uq_variant_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(80))
    price_pence: Mapped[int | None] = mapped_column(Integer, default=None)
    weight_grams: Mapped[int | None] = mapped_column(Integer, default=None)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    track_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def in_stock(self) -> bool:
        return (not self.track_stock) or self.stock > 0


class ProductAllergen(Base):
    __tablename__ = "product_allergens"
    __table_args__ = (UniqueConstraint("product_id", "allergen", name="uq_product_allergen"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    allergen: Mapped[str] = mapped_column(String(40))
    presence: Mapped[AllergenPresence] = mapped_column(
        Enum(AllergenPresence, native_enum=False), default=AllergenPresence.contains
    )

    product: Mapped[Product] = relationship(back_populates="allergens")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False), default=OrderStatus.pending, index=True
    )

    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    customer_name: Mapped[str] = mapped_column(String(160))

    # Delivery address is separate from billing so a hamper can be sent as a
    # gift without the buyer's paperwork following it (FR-11).
    delivery_name: Mapped[str] = mapped_column(String(160))
    delivery_line1: Mapped[str] = mapped_column(String(200))
    delivery_line2: Mapped[str | None] = mapped_column(String(200), default=None)
    delivery_city: Mapped[str] = mapped_column(String(120))
    delivery_postcode: Mapped[str] = mapped_column(String(20))
    delivery_country: Mapped[str] = mapped_column(String(2))
    zone: Mapped[str] = mapped_column(String(20))

    shipping_service: Mapped[str] = mapped_column(String(40))
    shipping_pence: Mapped[int] = mapped_column(Integer)
    subtotal_pence: Mapped[int] = mapped_column(Integer)
    total_pence: Mapped[int] = mapped_column(Integer)

    requires_chilled: Mapped[bool] = mapped_column(Boolean, default=False)
    dispatch_date: Mapped[date] = mapped_column(Date)
    delivery_date: Mapped[date] = mapped_column(Date)

    # Gift message prints on the dispatch note, never on the invoice (FR-10).
    gift_message: Mapped[str | None] = mapped_column(Text, default=None)
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderLine(Base):
    """Names, prices and allergens are copied in at order time.

    An order is a record of what was actually sold. Later edits to the
    catalogue must not rewrite history — especially not the allergen text,
    which has to match what went in the parcel.
    """

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"))
    sku: Mapped[str] = mapped_column(String(64))
    product_name: Mapped[str] = mapped_column(String(200))
    variant_label: Mapped[str] = mapped_column(String(80))
    unit_price_pence: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total_pence: Mapped[int] = mapped_column(Integer)
    weight_grams: Mapped[int] = mapped_column(Integer, default=0)
    temperature: Mapped[str] = mapped_column(String(20))
    allergen_summary: Mapped[str] = mapped_column(Text, default="")

    order: Mapped[Order] = relationship(back_populates="lines")


class MarketEvent(Base):
    """The market schedule — live content staff edit themselves (FR-24)."""

    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text, default=None)
    starts_on: Mapped[date] = mapped_column(Date, index=True)
    ends_on: Mapped[date | None] = mapped_column(Date, default=None)
    opening_time: Mapped[str | None] = mapped_column(String(60), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Enquiry(Base):
    """Trade, corporate gifting and general contact enquiries (FR-25, FR-14)."""

    __tablename__ = "enquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[EnquiryKind] = mapped_column(Enum(EnquiryKind, native_enum=False), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(200), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    message: Mapped[str] = mapped_column(Text)
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscriber(Base):
    """Double opt-in email capture (FR-27). Unconfirmed rows are not a list."""

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    source: Mapped[str | None] = mapped_column(String(80), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
