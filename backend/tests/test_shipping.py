"""Shipping zones, chilled rules and the dispatch calendar."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services import shipping
from app.services.shipping import ShippingError

# 2026-09-07 is a Monday.
MONDAY_MORNING = datetime(2026, 9, 7, 9, 0)
MONDAY_AFTERNOON = datetime(2026, 9, 7, 15, 0)
THURSDAY = datetime(2026, 9, 10, 9, 0)
SATURDAY = datetime(2026, 9, 12, 9, 0)


class TestZones:
    def test_belfast_postcode_is_northern_ireland(self):
        assert shipping.resolve_zone("GB", "BT17 0QL") == "NI"

    def test_lowercase_and_unspaced_postcodes_work(self):
        assert shipping.resolve_zone("gb", "bt170ql") == "NI"

    def test_republic_of_ireland_by_country_code(self):
        assert shipping.resolve_zone("IE", "D02 XY45") == "ROI"

    def test_gb_mainland(self):
        assert shipping.resolve_zone("GB", "SW1A 1AA") == "GB"

    @pytest.mark.parametrize("postcode", ["IV3 5AA", "KW1 4YT", "HS1 2AA", "ZE1 0AA", "IM1 1AA"])
    def test_whole_area_offshore_postcodes(self, postcode):
        assert shipping.resolve_zone("GB", postcode) == "GB_OFFSHORE"

    def test_offshore_ranges_are_bounded(self):
        """PA20-78 is offshore; PA1 (Paisley) is mainland."""
        assert shipping.resolve_zone("GB", "PA34 4AB") == "GB_OFFSHORE"
        assert shipping.resolve_zone("GB", "PA1 1AA") == "GB"

    def test_unsupported_country_is_rejected(self):
        with pytest.raises(ShippingError, match="do not currently ship"):
            shipping.resolve_zone("FR", "75001")

    def test_missing_postcode_is_rejected(self):
        with pytest.raises(ShippingError, match="postcode is required"):
            shipping.resolve_zone("GB", "")


class TestRates:
    def test_price_comes_from_the_weight_band(self):
        light = shipping.rate_for("GB", "standard", 500)
        heavy = shipping.rate_for("GB", "standard", 9000)
        assert 0 < light < heavy

    def test_band_boundary_is_inclusive(self):
        assert shipping.rate_for("GB", "standard", 2000) == shipping.rate_for("GB", "standard", 1)

    def test_overweight_parcel_is_refused_not_guessed(self):
        with pytest.raises(ShippingError, match="exceeds the heaviest band"):
            shipping.rate_for("GB", "standard", 500_000)

    def test_unknown_service_for_zone_is_refused(self):
        with pytest.raises(ShippingError, match="not available"):
            shipping.rate_for("GB_OFFSHORE", "next_day", 1000)

    def test_rate_card_is_flagged_as_unquoted(self):
        """The placeholder card must announce itself until real quotes replace it."""
        assert shipping.rate_card()["quoted"] is False


class TestDispatchCalendar:
    def test_before_cutoff_on_a_dispatch_day_goes_out_today(self):
        assert shipping.next_dispatch_date(MONDAY_MORNING) == date(2026, 9, 7)

    def test_after_cutoff_rolls_to_the_next_dispatch_day(self):
        assert shipping.next_dispatch_date(MONDAY_AFTERNOON) == date(2026, 9, 8)

    def test_thursday_waits_for_monday(self):
        """Dispatch is Mon-Wed, so nothing leaves late in the week."""
        assert shipping.next_dispatch_date(THURSDAY) == date(2026, 9, 14)

    def test_weekend_waits_for_monday(self):
        assert shipping.next_dispatch_date(SATURDAY) == date(2026, 9, 14)


class TestDeliveryDates:
    def test_chilled_delivery_never_lands_on_a_sunday(self):
        _, dates = shipping.delivery_dates("GB", "next_day", True, now=MONDAY_MORNING)
        assert dates
        assert all(day.weekday() != 6 for day in dates)

    def test_chilled_dates_come_only_from_dispatch_days(self):
        """Every chilled delivery date is one working day after a Mon-Wed dispatch."""
        _, dates = shipping.delivery_dates("GB", "next_day", True, now=MONDAY_MORNING)
        assert all(day.weekday() in {1, 2, 3} for day in dates)

    def test_chilled_goods_are_refused_on_a_standard_service(self):
        with pytest.raises(ShippingError, match="cannot carry chilled goods"):
            shipping.delivery_dates("GB", "standard", True, now=MONDAY_MORNING)

    def test_ambient_dates_start_after_the_longer_transit(self):
        _, chilled = shipping.delivery_dates("GB", "next_day", True, now=MONDAY_MORNING)
        _, ambient = shipping.delivery_dates("GB", "standard", False, now=MONDAY_MORNING)
        assert ambient[0] > chilled[0]


class TestBasketOptions:
    def test_chilled_basket_gets_no_standard_service(self):
        options = shipping.options_for_basket("GB", 1500, True, 2000, now=MONDAY_MORNING)
        assert {option.service for option in options} == {"next_day", "named_day"}

    def test_ambient_basket_can_use_standard(self):
        options = shipping.options_for_basket("GB", 1500, False, 2000, now=MONDAY_MORNING)
        assert "standard" in {option.service for option in options}

    def test_options_are_cheapest_first(self):
        options = shipping.options_for_basket("GB", 1500, False, 2000, now=MONDAY_MORNING)
        prices = [option.price_pence for option in options]
        assert prices == sorted(prices)

    def test_free_delivery_applies_over_the_threshold(self):
        options = shipping.options_for_basket("GB", 1500, False, 10_000, now=MONDAY_MORNING)
        standard = next(o for o in options if o.service == "standard")
        assert standard.price_pence == 0
        assert standard.free_delivery_applied is True

    def test_free_delivery_never_applies_to_chilled(self):
        """A chilled service costs real money; giving it away silently loses margin."""
        options = shipping.options_for_basket("GB", 1500, True, 10_000, now=MONDAY_MORNING)
        assert all(option.price_pence > 0 for option in options)
        assert all(option.free_delivery_applied is False for option in options)

    def test_free_delivery_does_not_apply_to_roi(self):
        options = shipping.options_for_basket("ROI", 1500, False, 10_000, now=MONDAY_MORNING)
        standard = next(o for o in options if o.service == "standard")
        assert standard.price_pence > 0

    def test_offshore_chilled_falls_back_to_named_day_only(self):
        options = shipping.options_for_basket("GB_OFFSHORE", 1500, True, 2000, now=MONDAY_MORNING)
        assert {option.service for option in options} == {"named_day"}

    def test_a_basket_with_no_viable_service_raises(self):
        with pytest.raises(ShippingError, match="No shipping service"):
            shipping.options_for_basket("GB", 500_000, True, 2000, now=MONDAY_MORNING)
