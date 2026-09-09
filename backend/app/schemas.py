"""Request and response shapes for the public and admin APIs."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import (
    AllergenPresence,
    AllergenStatus,
    EnquiryKind,
    OrderStatus,
    ProductStatus,
    Temperature,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


class AllergenOut(ORMModel):
    allergen: str
    presence: AllergenPresence


class VariantOut(ORMModel):
    id: int
    sku: str
    label: str
    price_pence: int | None
    weight_grams: int | None
    stock: int
    in_stock: bool


class CategoryOut(ORMModel):
    id: int
    slug: str
    name: str
    description: str | None
    position: int


class ProductSummary(ORMModel):
    slug: str
    name: str
    category: CategoryOut
    status: ProductStatus
    temperature: Temperature
    is_vegan: bool | None
    is_vegetarian: bool | None
    from_price_pence: int | None = None
    in_stock: bool = False


class ProductDetail(ProductSummary):
    description: str | None
    ingredients: str | None
    storage: str | None
    producer: str | None
    origin: str | None
    milk_type: str | None
    pasteurised: bool | None
    vegetarian_rennet: bool | None
    allergen_status: AllergenStatus
    allergen_note: str | None
    allergens: list[AllergenOut]
    variants: list[VariantOut]


class Page(BaseModel):
    total: int
    limit: int
    offset: int


class ProductPage(Page):
    items: list[ProductSummary]


# --------------------------------------------------------------------------
# Cart, shipping and orders
# --------------------------------------------------------------------------


class BasketLine(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=99)


class QuoteRequest(BaseModel):
    lines: list[BasketLine] = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2)
    postcode: str = Field(min_length=2, max_length=20)


class QuoteLine(BaseModel):
    sku: str
    product_name: str
    variant_label: str
    quantity: int
    unit_price_pence: int
    line_total_pence: int
    weight_grams: int
    temperature: Temperature
    allergen_summary: str


class ShippingOptionOut(BaseModel):
    service: str
    label: str
    zone: str
    price_pence: int
    chilled_capable: bool
    dispatch_date: date
    earliest_delivery: date
    delivery_dates: list[date]
    free_delivery_applied: bool


class QuoteResponse(BaseModel):
    lines: list[QuoteLine]
    subtotal_pence: int
    total_weight_grams: int
    requires_chilled: bool
    zone: str
    shipping_options: list[ShippingOptionOut]
    rates_are_quoted: bool
    notices: list[str] = []


class Address(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    postcode: str = Field(min_length=2, max_length=20)
    country: str = Field(min_length=2, max_length=2)


class OrderCreate(BaseModel):
    lines: list[BasketLine] = Field(min_length=1)
    email: EmailStr
    customer_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    delivery: Address
    shipping_service: str
    delivery_date: date
    is_gift: bool = False
    gift_message: str | None = Field(default=None, max_length=500)

    @field_validator("gift_message")
    @classmethod
    def strip_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrderLineOut(ORMModel):
    sku: str
    product_name: str
    variant_label: str
    quantity: int
    unit_price_pence: int
    line_total_pence: int
    allergen_summary: str


class OrderOut(ORMModel):
    number: str
    status: OrderStatus
    email: str
    customer_name: str
    zone: str
    shipping_service: str
    shipping_pence: int
    subtotal_pence: int
    total_pence: int
    requires_chilled: bool
    dispatch_date: date
    delivery_date: date
    is_gift: bool
    gift_message: str | None
    created_at: datetime
    lines: list[OrderLineOut]


class DispatchNote(BaseModel):
    """What goes in the parcel.

    Carries the gift message and the allergen sheet, and deliberately carries
    no prices: a gift recipient must not be shown what was paid.
    """

    order_number: str
    delivery_name: str
    delivery_address: list[str]
    dispatch_date: date
    delivery_date: date
    is_gift: bool
    gift_message: str | None
    items: list[dict]
    allergen_statement: str


# --------------------------------------------------------------------------
# Content and capture
# --------------------------------------------------------------------------


class MarketEventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    address: str | None = None
    starts_on: date
    ends_on: date | None = None
    opening_time: str | None = Field(default=None, max_length=60)
    notes: str | None = None
    published: bool = True


class MarketEventOut(ORMModel):
    id: int
    title: str
    location: str
    address: str | None
    starts_on: date
    ends_on: date | None
    opening_time: str | None
    notes: str | None
    published: bool


class EnquiryIn(BaseModel):
    kind: EnquiryKind = EnquiryKind.general
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=4000)


class EnquiryOut(ORMModel):
    id: int
    kind: EnquiryKind
    name: str
    email: str
    company: str | None
    phone: str | None
    message: str
    handled: bool
    created_at: datetime


class SubscribeIn(BaseModel):
    email: EmailStr
    source: str | None = Field(default=None, max_length=80)


# --------------------------------------------------------------------------
# Admin: import, readiness, product editing
# --------------------------------------------------------------------------


class ImportRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class ImportRecord(BaseModel):
    category: str
    product: str
    line: int


class ImportAmbiguity(BaseModel):
    line: int | None
    kind: str
    message: str


class ImportPreview(BaseModel):
    records: list[ImportRecord]
    ambiguities: list[ImportAmbiguity]
    categories: list[str]
    can_commit: bool


class ImportCommitRequest(ImportRequest):
    allow_ambiguous: bool = False


class ImportResult(BaseModel):
    created_categories: list[str]
    created_products: list[str]
    skipped_existing: list[str]
    ambiguities: list[ImportAmbiguity]


class AllergenIn(BaseModel):
    allergen: str
    presence: AllergenPresence = AllergenPresence.contains


class VariantIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    sku: str | None = Field(default=None, max_length=64)
    price_pence: int | None = Field(default=None, ge=0)
    weight_grams: int | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)
    track_stock: bool = True


class ProductUpdate(BaseModel):
    description: str | None = None
    ingredients: str | None = None
    storage: str | None = None
    producer: str | None = None
    origin: str | None = None
    milk_type: str | None = None
    pasteurised: bool | None = None
    vegetarian_rennet: bool | None = None
    is_vegan: bool | None = None
    is_vegetarian: bool | None = None
    temperature: Temperature | None = None
    allergen_status: AllergenStatus | None = None
    allergen_note: str | None = None
    allergens: list[AllergenIn] | None = None
    variants: list[VariantIn] | None = None


class ReadinessOut(BaseModel):
    slug: str
    name: str
    category: str
    status: ProductStatus
    ready: bool
    blockers: list[str]
    warnings: list[str]


class ReadinessReport(BaseModel):
    summary: dict
    products: list[ReadinessOut]
