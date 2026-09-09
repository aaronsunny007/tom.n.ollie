"""The launch gates, especially the allergen one."""

from __future__ import annotations

from app.models import AllergenStatus, ProductStatus
from app.services import readiness
from tests.conftest import make_product


def test_a_fully_specified_product_is_ready(db_session):
    product = make_product(db_session)
    report = readiness.assess(product)
    assert report.ready is True
    assert report.blockers == []


def test_unconfirmed_allergens_block_publishing(db_session):
    product = make_product(db_session, allergen_status=AllergenStatus.unconfirmed)
    report = readiness.assess(product)
    assert report.ready is False
    assert any("Allergen data is not confirmed" in blocker for blocker in report.blockers)


def test_missing_price_blocks_publishing(db_session):
    product = make_product(db_session, price_pence=None)
    report = readiness.assess(product)
    assert report.ready is False
    assert any("no price" in blocker for blocker in report.blockers)


def test_missing_weight_blocks_publishing(db_session):
    """Shipping is priced by weight band, so a missing weight is a loss-making parcel."""
    product = make_product(db_session, weight_grams=None)
    report = readiness.assess(product)
    assert report.ready is False
    assert any("no weight" in blocker for blocker in report.blockers)


def test_a_product_with_no_variant_cannot_be_published(db_session):
    product = make_product(db_session)
    product.variants.clear()
    db_session.commit()
    report = readiness.assess(product)
    assert report.ready is False
    assert any("No sellable variant" in blocker for blocker in report.blockers)


def test_missing_description_is_a_warning_not_a_blocker(db_session):
    product = make_product(db_session)
    report = readiness.assess(product)
    assert report.ready is True
    assert any("No product description" in warning for warning in report.warnings)


def test_unset_dietary_flags_warn_about_filters(db_session):
    product = make_product(db_session, is_vegan=None)
    report = readiness.assess(product)
    assert any("Dietary flags are unset" in warning for warning in report.warnings)


def test_summary_counts_blocked_and_live(db_session):
    ready = make_product(db_session)
    blocked = make_product(
        db_session,
        name="Beetroot Hummus",
        slug="hummus-beetroot-hummus",
        sku="HUM-BEETROOT-200G",
        status=ProductStatus.draft,
        allergen_status=AllergenStatus.unconfirmed,
    )
    summary = readiness.summarise([readiness.assess(ready), readiness.assess(blocked)])
    assert summary == {
        "total_products": 2,
        "ready_to_publish": 1,
        "blocked": 1,
        "currently_live": 1,
        "launch_ready": False,
    }
