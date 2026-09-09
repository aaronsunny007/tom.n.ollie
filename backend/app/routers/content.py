"""Market schedule, enquiries and email capture."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Enquiry, MarketEvent, Subscriber
from ..schemas import EnquiryIn, EnquiryOut, MarketEventOut, SubscribeIn
from ..utils import new_token

router = APIRouter(prefix="/api", tags=["content"])


@router.get("/events", response_model=list[MarketEventOut])
def list_events(
    upcoming_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MarketEvent]:
    """The market schedule. Live content, not a static page."""
    statement = select(MarketEvent).where(MarketEvent.published.is_(True))
    if upcoming_only:
        today = date.today()
        statement = statement.where(
            (MarketEvent.ends_on >= today) | (MarketEvent.starts_on >= today)
        )
    return list(db.scalars(statement.order_by(MarketEvent.starts_on).limit(limit)))


@router.post("/enquiries", response_model=EnquiryOut, status_code=201)
def create_enquiry(payload: EnquiryIn, db: Session = Depends(get_db)) -> Enquiry:
    """Trade, corporate gifting and general contact, into one monitored queue."""
    enquiry = Enquiry(
        kind=payload.kind,
        name=payload.name.strip(),
        email=str(payload.email),
        company=payload.company,
        phone=payload.phone,
        message=payload.message.strip(),
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)
    return enquiry


@router.post("/newsletter/subscribe", status_code=202)
def subscribe(payload: SubscribeIn, db: Session = Depends(get_db)) -> dict:
    """Start a double opt-in signup.

    The row is created unconfirmed and stays out of the mailing list until the
    token is used. An unconfirmed address is not consent.
    """
    email = str(payload.email).strip().lower()
    existing = db.scalar(select(Subscriber).where(Subscriber.email == email))
    if existing is not None:
        if existing.confirmed:
            return {"status": "already_subscribed", "email": email}
        token = existing.token
    else:
        token = new_token()
        db.add(Subscriber(email=email, token=token, source=payload.source))
        db.commit()

    # The confirmation email is sent by the marketing platform; the token is
    # returned only so a caller can wire that up.
    return {"status": "confirmation_required", "email": email, "confirm_token": token}


@router.get("/newsletter/confirm")
def confirm(token: str, db: Session = Depends(get_db)) -> dict:
    subscriber = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Unknown or expired confirmation token.")
    if not subscriber.confirmed:
        subscriber.confirmed = True
        subscriber.confirmed_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "confirmed", "email": subscriber.email}
