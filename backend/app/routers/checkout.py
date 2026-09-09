"""Basket quoting, shipping options and order placement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import get_settings
from ..db import get_db
from ..models import Order, OrderLine, OrderStatus
from ..schemas import (
    DispatchNote,
    OrderCreate,
    OrderOut,
    QuoteLine,
    QuoteRequest,
    QuoteResponse,
    ShippingOptionOut,
)
from ..services import shipping
from ..services.basket import BasketError, price_basket
from ..utils import order_number

router = APIRouter(prefix="/api", tags=["checkout"])


def _quote_lines(basket) -> list[QuoteLine]:
    return [
        QuoteLine(
            sku=line.variant.sku,
            product_name=line.product.name,
            variant_label=line.variant.label,
            quantity=line.quantity,
            unit_price_pence=line.unit_price_pence,
            line_total_pence=line.line_total_pence,
            weight_grams=line.weight_grams,
            temperature=line.product.temperature,
            allergen_summary=line.allergen_summary,
        )
        for line in basket.lines
    ]


@router.get("/shipping/zones")
def shipping_zones() -> dict:
    card = shipping.rate_card()
    return {
        "quoted": card.get("quoted", False),
        "currency": card.get("currency", "GBP"),
        "zones": {
            zone: {
                "label": data["label"],
                "services": {
                    service: {"label": s["label"], "chilled": s["chilled"]}
                    for service, s in data["services"].items()
                },
            }
            for zone, data in card["zones"].items()
        },
        "free_delivery_threshold_pence": get_settings().free_delivery_threshold_pence,
    }


@router.get("/shipping/zone")
def zone_for_address(country: str = Query(min_length=2, max_length=2), postcode: str = "") -> dict:
    try:
        zone = shipping.resolve_zone(country, postcode)
    except shipping.ShippingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"zone": zone, "label": shipping.rate_card()["zones"][zone]["label"]}


@router.post("/cart/quote", response_model=QuoteResponse)
def quote(payload: QuoteRequest, db: Session = Depends(get_db)) -> QuoteResponse:
    """Price a basket and list every service that can legitimately carry it."""
    try:
        basket = price_basket(db, [(line.sku, line.quantity) for line in payload.lines])
        zone = shipping.resolve_zone(payload.country, payload.postcode)
        options = shipping.options_for_basket(
            zone=zone,
            weight_grams=basket.total_weight_grams,
            requires_chilled=basket.requires_chilled,
            subtotal_pence=basket.subtotal_pence,
        )
    except (BasketError, shipping.ShippingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    card = shipping.rate_card()
    notices: list[str] = []
    if basket.requires_chilled:
        notices.append(
            "This order contains chilled goods, so the whole parcel ships on a "
            "next-day or named-day service and can only leave on a dispatch day."
        )
    if not card.get("quoted", False):
        notices.append(
            "Delivery prices are provisional planning rates, not carrier quotes."
        )

    return QuoteResponse(
        lines=_quote_lines(basket),
        subtotal_pence=basket.subtotal_pence,
        total_weight_grams=basket.total_weight_grams,
        requires_chilled=basket.requires_chilled,
        zone=zone,
        shipping_options=[ShippingOptionOut(**vars(option)) for option in options],
        rates_are_quoted=card.get("quoted", False),
        notices=notices,
    )


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> Order:
    """Place an order.

    The basket is re-priced server-side and the chosen delivery date is checked
    against the dispatch calendar. A date the warehouse cannot hit is rejected
    here rather than discovered when a chilled parcel is already late.
    """
    try:
        basket = price_basket(db, [(line.sku, line.quantity) for line in payload.lines])
        zone = shipping.resolve_zone(payload.delivery.country, payload.delivery.postcode)
        options = shipping.options_for_basket(
            zone=zone,
            weight_grams=basket.total_weight_grams,
            requires_chilled=basket.requires_chilled,
            subtotal_pence=basket.subtotal_pence,
        )
    except (BasketError, shipping.ShippingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chosen = next((o for o in options if o.service == payload.shipping_service), None)
    if chosen is None:
        available = ", ".join(o.service for o in options)
        raise HTTPException(
            status_code=400,
            detail=f"Service {payload.shipping_service!r} is not available for this basket. "
            f"Available: {available}.",
        )

    if payload.delivery_date not in chosen.delivery_dates:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{payload.delivery_date.isoformat()} is not a delivery date we can hit on "
                f"{chosen.label}. Choose one of the offered dates."
            ),
        )

    order = Order(
        number=order_number(),
        status=OrderStatus.pending,
        email=str(payload.email),
        phone=payload.phone,
        customer_name=payload.customer_name,
        delivery_name=payload.delivery.name,
        delivery_line1=payload.delivery.line1,
        delivery_line2=payload.delivery.line2,
        delivery_city=payload.delivery.city,
        delivery_postcode=payload.delivery.postcode,
        delivery_country=payload.delivery.country.upper(),
        zone=zone,
        shipping_service=chosen.service,
        shipping_pence=chosen.price_pence,
        subtotal_pence=basket.subtotal_pence,
        total_pence=basket.subtotal_pence + chosen.price_pence,
        requires_chilled=basket.requires_chilled,
        dispatch_date=chosen.dispatch_date,
        delivery_date=payload.delivery_date,
        is_gift=payload.is_gift,
        gift_message=payload.gift_message,
    )

    for line in basket.lines:
        order.lines.append(
            OrderLine(
                variant_id=line.variant.id,
                sku=line.variant.sku,
                product_name=line.product.name,
                variant_label=line.variant.label,
                unit_price_pence=line.unit_price_pence,
                quantity=line.quantity,
                line_total_pence=line.line_total_pence,
                weight_grams=line.weight_grams,
                temperature=line.product.temperature.value,
                allergen_summary=line.allergen_summary,
            )
        )
        if line.variant.track_stock:
            line.variant.stock -= line.quantity

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/{number}", response_model=OrderOut)
def get_order(number: str, email: str = Query(...), db: Session = Depends(get_db)) -> Order:
    """Look up an order. The email must match — there are no order accounts."""
    order = db.scalar(
        select(Order).where(Order.number == number).options(selectinload(Order.lines))
    )
    if order is None or order.email.lower() != email.strip().lower():
        raise HTTPException(status_code=404, detail="No order found for that number and email.")
    return order


@router.get("/orders/{number}/dispatch-note", response_model=DispatchNote)
def dispatch_note(number: str, email: str = Query(...), db: Session = Depends(get_db)):
    """The paperwork that goes in the parcel.

    Carries the gift message and the written allergen statement the FSA
    requires on delivery, and deliberately carries no prices.
    """
    order = get_order(number=number, email=email, db=db)
    address = [order.delivery_line1]
    if order.delivery_line2:
        address.append(order.delivery_line2)
    address += [order.delivery_city, order.delivery_postcode, order.delivery_country]

    return DispatchNote(
        order_number=order.number,
        delivery_name=order.delivery_name,
        delivery_address=address,
        dispatch_date=order.dispatch_date,
        delivery_date=order.delivery_date,
        is_gift=order.is_gift,
        gift_message=order.gift_message,
        items=[
            {
                "product": line.product_name,
                "size": line.variant_label,
                "quantity": line.quantity,
                "allergens": line.allergen_summary,
            }
            for line in order.lines
        ],
        allergen_statement=(
            "Allergen information for every item in this parcel is listed above. "
            "Tom and Ollie (NI) Ltd, Unit 55/56 Glenwood Business Centre, Springbank Road, "
            "Dunmurry, Belfast BT17 0QL."
        ),
    )
