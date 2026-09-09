"""Shipping zones, rates and dispatch scheduling.

Two rules drive everything here:

1. **A mixed basket ships chilled.** If any line needs refrigeration, the whole
   parcel goes on a chilled service. Splitting the order is a fulfilment
   decision, not something to silently assume at checkout.
2. **Chilled goods never sit in transit over a weekend.** Dispatch is limited
   to the configured weekdays behind a same-day cut-off, and delivery dates are
   derived from that rather than offered freely.

The rate card in ``data/shipping_rates.json`` is a planning placeholder. It
reports ``quoted: false`` through the API until real carrier quotes replace it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

RATE_CARD_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shipping_rates.json"

NI_POSTCODE_RE = re.compile(r"^BT\d", re.IGNORECASE)

# Postcode areas that carriers surcharge as offshore or Highlands. Kept
# explicit rather than clever: a missed area is a loss-making parcel.
OFFSHORE_AREAS = {"IM", "JE", "GY", "HS", "ZE", "KW", "IV", "PA", "PH", "KA", "TR", "PO", "AB"}
OFFSHORE_RANGES = {
    "PA": (20, 78),
    "PH": (17, 50),
    "KA": (27, 28),
    "TR": (21, 25),
    "PO": (30, 41),
    "AB": (30, 56),
}
# These areas are offshore/Highland for their whole range.
OFFSHORE_WHOLE_AREA = {"IM", "JE", "GY", "HS", "ZE", "KW", "IV"}

# Deliveries do not run on Sunday.
NO_DELIVERY_WEEKDAYS = {6}


class ShippingError(ValueError):
    """Raised when a basket cannot be shipped as requested."""


@dataclass(frozen=True)
class ShippingOption:
    service: str
    label: str
    zone: str
    price_pence: int
    chilled_capable: bool
    dispatch_date: date
    earliest_delivery: date
    delivery_dates: list[date]
    free_delivery_applied: bool


@lru_cache
def rate_card() -> dict:
    with RATE_CARD_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalise_postcode(postcode: str) -> str:
    return re.sub(r"\s+", "", postcode or "").upper()


def _postcode_area_and_district(postcode: str) -> tuple[str, int | None]:
    compact = normalise_postcode(postcode)
    match = re.match(r"^([A-Z]{1,2})(\d{1,2})", compact)
    if not match:
        return compact[:2], None
    return match.group(1), int(match.group(2))


def resolve_zone(country: str, postcode: str) -> str:
    """Map a destination to a shipping zone.

    ``country`` is an ISO 3166-1 alpha-2 code. Northern Ireland is separated
    from the rest of the UK by its BT postcode area.
    """
    code = (country or "").strip().upper()
    if code == "IE":
        return "ROI"
    if code not in {"GB", "UK", "IM", "JE", "GG"}:
        raise ShippingError(f"We do not currently ship to country code {code!r}.")
    if code in {"IM", "JE", "GG"}:
        return "GB_OFFSHORE"

    compact = normalise_postcode(postcode)
    if not compact:
        raise ShippingError("A postcode is required to work out a delivery zone.")
    if NI_POSTCODE_RE.match(compact):
        return "NI"

    area, district = _postcode_area_and_district(compact)
    if area in OFFSHORE_WHOLE_AREA:
        return "GB_OFFSHORE"
    if area in OFFSHORE_RANGES and district is not None:
        low, high = OFFSHORE_RANGES[area]
        if low <= district <= high:
            return "GB_OFFSHORE"
    return "GB"


def rate_for(zone: str, service: str, weight_grams: int) -> int:
    """Price a parcel from the weight bands. Raises if it is over the top band."""
    card = rate_card()
    zone_card = card["zones"].get(zone)
    if zone_card is None:
        raise ShippingError(f"No rates configured for zone {zone!r}.")
    service_card = zone_card["services"].get(service)
    if service_card is None:
        raise ShippingError(f"Service {service!r} is not available for zone {zone!r}.")
    for max_grams, price_pence in service_card["bands"]:
        if weight_grams <= max_grams:
            return price_pence
    raise ShippingError(
        f"Parcel weight {weight_grams}g exceeds the heaviest band for {service!r} in {zone!r}. "
        "Split the order or arrange a pallet rate."
    )


def next_dispatch_date(now: datetime | None = None) -> date:
    """First day the parcel can leave, honouring the dispatch-day cut-off."""
    settings = get_settings()
    now = now or datetime.now()
    dispatch_days = settings.dispatch_weekday_set
    if not dispatch_days:
        raise ShippingError("No dispatch weekdays are configured.")

    candidate = now.date()
    # Today only counts if it is a dispatch day and we are still before cut-off.
    if candidate.weekday() in dispatch_days and now.hour < settings.dispatch_cutoff_hour:
        return candidate
    for offset in range(1, 15):
        candidate = now.date() + timedelta(days=offset)
        if candidate.weekday() in dispatch_days:
            return candidate
    raise ShippingError("Could not find a dispatch day in the next fortnight.")


def _add_transit_days(start: date, transit_days: int) -> date:
    """Advance by working delivery days, skipping days carriers do not deliver."""
    current = start
    remaining = max(transit_days, 1)
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() not in NO_DELIVERY_WEEKDAYS:
            remaining -= 1
    return current


def delivery_dates(
    zone: str, service: str, requires_chilled: bool, now: datetime | None = None
) -> tuple[date, list[date]]:
    """Return (dispatch_date, selectable delivery dates) for a service.

    Chilled orders get named-day precision only where the service supports it;
    every returned date is one the warehouse can actually hit.
    """
    settings = get_settings()
    card = rate_card()
    service_card = card["zones"][zone]["services"][service]
    if requires_chilled and not service_card["chilled"]:
        raise ShippingError(
            f"{service_card['label']} cannot carry chilled goods. "
            "Choose a next-day or named-day service."
        )

    if service == "collection":
        dispatch = next_dispatch_date(now)
        dates = [
            dispatch + timedelta(days=offset)
            for offset in range(0, 14)
            if (dispatch + timedelta(days=offset)).weekday() not in NO_DELIVERY_WEEKDAYS
        ]
        return dispatch, dates

    transit = settings.chilled_transit_days if requires_chilled else settings.ambient_transit_days
    dispatch = next_dispatch_date(now)
    earliest = _add_transit_days(dispatch, transit)

    if requires_chilled:
        # Chilled parcels are only offered on days we actually dispatch, so the
        # selectable dates are derived from future dispatch days, not a range.
        dates: list[date] = []
        cursor = dispatch
        while len(dates) < 8 and (cursor - dispatch).days <= settings.delivery_window_days:
            if cursor.weekday() in settings.dispatch_weekday_set:
                candidate = _add_transit_days(cursor, transit)
                if candidate not in dates:
                    dates.append(candidate)
            cursor += timedelta(days=1)
    else:
        dates = []
        cursor = earliest
        while len(dates) < 21 and (cursor - earliest).days <= settings.delivery_window_days:
            if cursor.weekday() not in NO_DELIVERY_WEEKDAYS:
                dates.append(cursor)
            cursor += timedelta(days=1)

    return dispatch, dates


def options_for_basket(
    zone: str,
    weight_grams: int,
    requires_chilled: bool,
    subtotal_pence: int,
    now: datetime | None = None,
) -> list[ShippingOption]:
    """Every service that can legitimately carry this basket, priced."""
    settings = get_settings()
    card = rate_card()
    zone_card = card["zones"].get(zone)
    if zone_card is None:
        raise ShippingError(f"No rates configured for zone {zone!r}.")

    options: list[ShippingOption] = []
    for service, service_card in zone_card["services"].items():
        if requires_chilled and not service_card["chilled"]:
            continue
        try:
            price = rate_for(zone, service, weight_grams)
            dispatch, dates = delivery_dates(zone, service, requires_chilled, now=now)
        except ShippingError:
            continue

        free_applied = False
        threshold = settings.free_delivery_threshold_pence
        if (
            threshold
            and subtotal_pence >= threshold
            and zone in card.get("free_delivery_zones", [])
            and not requires_chilled
            and service == "standard"
        ):
            price = 0
            free_applied = True

        options.append(
            ShippingOption(
                service=service,
                label=service_card["label"],
                zone=zone,
                price_pence=price,
                chilled_capable=service_card["chilled"],
                dispatch_date=dispatch,
                earliest_delivery=dates[0] if dates else dispatch,
                delivery_dates=dates,
                free_delivery_applied=free_applied,
            )
        )

    if not options:
        raise ShippingError(
            "No shipping service can carry this basket to that address. "
            "Chilled goods need a next-day or named-day service."
        )
    return sorted(options, key=lambda option: option.price_pence)
